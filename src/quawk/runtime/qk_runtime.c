/*
 * Streaming runtime support layer for record-driven AWK execution.
 *
 * This runtime is intentionally small and C-based so the compiler can target a
 * reusable ABI today and later link the same generated code into executables.
 */

#define _POSIX_C_SOURCE 200809L

#include "qk_runtime.h"

#include <ctype.h>
#include <errno.h>
#include <regex.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct qk_runtime {
    int argc;
    char **argv;
    int next_input_index;
    FILE *current_handle;
    bool current_handle_is_stdin;
    bool stdin_consumed;
    bool had_error;
    char *current_record;
    size_t current_record_capacity;
    char **fields;
    size_t field_count;
    size_t field_capacity;
    char *field_separator;
};

static const char QK_EMPTY_FIELD[] = "";

static char *qk_strdup_or_null(const char *text)
{
    if (text == NULL) {
        return NULL;
    }

    size_t text_length = strlen(text) + 1U;
    char *copy = malloc(text_length);
    if (copy == NULL) {
        return NULL;
    }
    memcpy(copy, text, text_length);
    return copy;
}

static void qk_close_current_handle(qk_runtime *runtime)
{
    if ((runtime->current_handle != NULL) && !runtime->current_handle_is_stdin) {
        fclose(runtime->current_handle);
    }
    runtime->current_handle = NULL;
    runtime->current_handle_is_stdin = false;
}

static bool qk_push_field(qk_runtime *runtime, char *field_text)
{
    if (runtime->field_count == runtime->field_capacity) {
        size_t next_capacity = runtime->field_capacity == 0U ? 8U : runtime->field_capacity * 2U;
        char **next_fields = realloc(runtime->fields, next_capacity * sizeof(*next_fields));
        if (next_fields == NULL) {
            return false;
        }
        runtime->fields = next_fields;
        runtime->field_capacity = next_capacity;
    }

    runtime->fields[runtime->field_count] = field_text;
    runtime->field_count += 1U;
    return true;
}

static bool qk_split_whitespace_fields(qk_runtime *runtime)
{
    char *cursor = runtime->current_record;

    while (*cursor != '\0') {
        while ((*cursor != '\0') && isspace((unsigned char)*cursor)) {
            cursor += 1;
        }
        if (*cursor == '\0') {
            break;
        }

        char *field_start = cursor;
        while ((*cursor != '\0') && !isspace((unsigned char)*cursor)) {
            cursor += 1;
        }
        if (*cursor != '\0') {
            *cursor = '\0';
            cursor += 1;
        }

        if (!qk_push_field(runtime, field_start)) {
            return false;
        }
    }

    return true;
}

static bool qk_split_literal_separator_fields(qk_runtime *runtime)
{
    size_t separator_length = strlen(runtime->field_separator);
    char *field_start = runtime->current_record;

    if (separator_length == 0U) {
        return qk_push_field(runtime, field_start);
    }

    for (;;) {
        char *match = strstr(field_start, runtime->field_separator);
        if (match == NULL) {
            return qk_push_field(runtime, field_start);
        }

        *match = '\0';
        if (!qk_push_field(runtime, field_start)) {
            return false;
        }
        field_start = match + separator_length;
    }
}

static bool qk_rebuild_fields(qk_runtime *runtime)
{
    runtime->field_count = 0U;

    if ((runtime->field_separator == NULL) || (*runtime->field_separator == '\0')) {
        return qk_split_whitespace_fields(runtime);
    }
    return qk_split_literal_separator_fields(runtime);
}

static bool qk_open_next_input(qk_runtime *runtime)
{
    if (runtime->argc == 0) {
        if (runtime->stdin_consumed) {
            return false;
        }
        runtime->current_handle = stdin;
        runtime->current_handle_is_stdin = true;
        runtime->stdin_consumed = true;
        return true;
    }

    while (runtime->next_input_index < runtime->argc) {
        const char *path = runtime->argv[runtime->next_input_index];
        runtime->next_input_index += 1;

        if (strcmp(path, "-") == 0) {
            runtime->current_handle = stdin;
            runtime->current_handle_is_stdin = true;
            return true;
        }

        runtime->current_handle = fopen(path, "r");
        if (runtime->current_handle != NULL) {
            runtime->current_handle_is_stdin = false;
            return true;
        }

        runtime->had_error = true;
        fprintf(stderr, "quawk runtime: %s: %s\n", path, strerror(errno));
        return false;
    }

    return false;
}

qk_runtime *qk_runtime_create(int argc, char **argv, const char *field_separator)
{
    qk_runtime *runtime = calloc(1U, sizeof(*runtime));
    if (runtime == NULL) {
        return NULL;
    }

    runtime->argc = argc;
    runtime->argv = argv;
    runtime->field_separator = qk_strdup_or_null(field_separator);
    if ((field_separator != NULL) && (runtime->field_separator == NULL)) {
        free(runtime);
        return NULL;
    }

    return runtime;
}

void qk_runtime_destroy(qk_runtime *runtime)
{
    if (runtime == NULL) {
        return;
    }

    qk_close_current_handle(runtime);
    free(runtime->current_record);
    free(runtime->fields);
    free(runtime->field_separator);
    free(runtime);
}

bool qk_next_record(qk_runtime *runtime)
{
    if (runtime == NULL) {
        return false;
    }

    for (;;) {
        if ((runtime->current_handle == NULL) && !qk_open_next_input(runtime)) {
            return false;
        }

        ssize_t line_length = getline(
            &runtime->current_record,
            &runtime->current_record_capacity,
            runtime->current_handle
        );
        if (line_length >= 0) {
            /*
             * Normalize the record in place so `$0` matches AWK's record text
             * rather than the raw line including its trailing newline.
             */
            while ((line_length > 0) &&
                   ((runtime->current_record[line_length - 1] == '\n') ||
                    (runtime->current_record[line_length - 1] == '\r'))) {
                runtime->current_record[line_length - 1] = '\0';
                line_length -= 1;
            }
            return qk_rebuild_fields(runtime);
        }

        qk_close_current_handle(runtime);
    }
}

const char *qk_get_field(qk_runtime *runtime, int64_t index)
{
    if ((runtime == NULL) || (runtime->current_record == NULL)) {
        return QK_EMPTY_FIELD;
    }

    if (index == 0) {
        return runtime->current_record;
    }
    if (index < 0) {
        return QK_EMPTY_FIELD;
    }

    size_t field_index = (size_t)index - 1U;
    if (field_index >= runtime->field_count) {
        return QK_EMPTY_FIELD;
    }
    return runtime->fields[field_index];
}

void qk_print_string(qk_runtime *runtime, const char *value)
{
    (void)runtime;
    puts(value == NULL ? "" : value);
}

void qk_print_number(qk_runtime *runtime, double value)
{
    (void)runtime;
    printf("%g\n", value);
}

bool qk_regex_match_current_record(qk_runtime *runtime, const char *pattern)
{
    if ((runtime == NULL) || (runtime->current_record == NULL) || (pattern == NULL)) {
        return false;
    }

    regex_t regex;
    if (regcomp(&regex, pattern, REG_EXTENDED) != 0) {
        return false;
    }

    int result = regexec(&regex, runtime->current_record, 0, NULL, 0);
    regfree(&regex);
    return result == 0;
}
