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
    bool exit_requested;
    int32_t exit_status;
    char *current_record;
    size_t current_record_capacity;
    char *field_buffer;
    char **fields;
    size_t field_count;
    size_t field_capacity;
    char *field_separator;
    double nr;
    double fnr;
    char *current_filename;
    char *scratch_buffer;
    size_t scratch_capacity;
    struct qk_scalar_entry *scalars;
    struct qk_array *arrays;
};

enum qk_scalar_kind {
    QK_SCALAR_UNSET = 0,
    QK_SCALAR_NUMBER = 1,
    QK_SCALAR_STRING = 2,
};

struct qk_scalar_entry {
    char *name;
    enum qk_scalar_kind kind;
    double number;
    char *string;
    struct qk_scalar_entry *next;
};

struct qk_array_entry {
    char *key;
    char *value;
    struct qk_array_entry *next;
};

struct qk_array {
    char *name;
    struct qk_array_entry *entries;
    struct qk_array *next;
};

static const char QK_EMPTY_FIELD[] = "";
static const char QK_DEFAULT_OFMT[] = "%.6g";
static const char QK_DEFAULT_CONVFMT[] = "%.6g";

static const char *qk_output_variable_text(qk_runtime *runtime, const char *name, const char *fallback);

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

static void qk_set_current_filename(qk_runtime *runtime, const char *path)
{
    free(runtime->current_filename);
    runtime->current_filename = qk_strdup_or_null(path);
}

static void qk_close_current_handle(qk_runtime *runtime)
{
    if ((runtime->current_handle != NULL) && !runtime->current_handle_is_stdin) {
        fclose(runtime->current_handle);
    }
    runtime->current_handle = NULL;
    runtime->current_handle_is_stdin = false;
}

static void qk_free_array_entries(struct qk_array_entry *entry)
{
    while (entry != NULL) {
        struct qk_array_entry *next = entry->next;
        free(entry->key);
        free(entry->value);
        free(entry);
        entry = next;
    }
}

static void qk_free_scalars(struct qk_scalar_entry *entry)
{
    while (entry != NULL) {
        struct qk_scalar_entry *next = entry->next;
        free(entry->name);
        free(entry->string);
        free(entry);
        entry = next;
    }
}

static void qk_invalidate_numeric_string_cache(qk_runtime *runtime)
{
    struct qk_scalar_entry *entry;

    if (runtime == NULL) {
        return;
    }

    entry = runtime->scalars;
    while (entry != NULL) {
        if (entry->kind == QK_SCALAR_NUMBER) {
            free(entry->string);
            entry->string = NULL;
        }
        entry = entry->next;
    }
}

static void qk_free_arrays(struct qk_array *array)
{
    while (array != NULL) {
        struct qk_array *next = array->next;
        free(array->name);
        qk_free_array_entries(array->entries);
        free(array);
        array = next;
    }
}

static struct qk_scalar_entry *qk_find_scalar(qk_runtime *runtime, const char *name, bool create)
{
    struct qk_scalar_entry *entry = runtime->scalars;
    while (entry != NULL) {
        if ((entry->name != NULL) && (name != NULL) && (strcmp(entry->name, name) == 0)) {
            return entry;
        }
        entry = entry->next;
    }

    if (!create || (name == NULL)) {
        return NULL;
    }

    entry = calloc(1U, sizeof(*entry));
    if (entry == NULL) {
        return NULL;
    }
    entry->name = qk_strdup_or_null(name);
    if (entry->name == NULL) {
        free(entry);
        return NULL;
    }
    entry->kind = QK_SCALAR_UNSET;
    entry->next = runtime->scalars;
    runtime->scalars = entry;
    return entry;
}

static void qk_clear_scalar(struct qk_scalar_entry *entry)
{
    if (entry == NULL) {
        return;
    }
    entry->kind = QK_SCALAR_UNSET;
    entry->number = 0.0;
    free(entry->string);
    entry->string = NULL;
}

static bool qk_scalar_set_string_value(qk_runtime *runtime, const char *name, const char *value)
{
    struct qk_scalar_entry *entry = qk_find_scalar(runtime, name, true);
    char *copy;

    if (entry == NULL) {
        return false;
    }

    copy = qk_strdup_or_null(value == NULL ? "" : value);
    if (copy == NULL) {
        return false;
    }

    free(entry->string);
    entry->string = copy;
    entry->number = 0.0;
    entry->kind = QK_SCALAR_STRING;
    if (strcmp(name, "CONVFMT") == 0) {
        qk_invalidate_numeric_string_cache(runtime);
    }
    return true;
}

static bool qk_scalar_set_number_value(qk_runtime *runtime, const char *name, double value)
{
    struct qk_scalar_entry *entry = qk_find_scalar(runtime, name, true);
    if (entry == NULL) {
        return false;
    }

    free(entry->string);
    entry->string = NULL;
    entry->number = value;
    entry->kind = QK_SCALAR_NUMBER;
    if (strcmp(name, "CONVFMT") == 0) {
        qk_invalidate_numeric_string_cache(runtime);
    }
    return true;
}

static struct qk_array *qk_find_array(qk_runtime *runtime, const char *name, bool create)
{
    struct qk_array *array = runtime->arrays;
    while (array != NULL) {
        if ((array->name != NULL) && (name != NULL) && (strcmp(array->name, name) == 0)) {
            return array;
        }
        array = array->next;
    }

    if (!create || (name == NULL)) {
        return NULL;
    }

    array = calloc(1U, sizeof(*array));
    if (array == NULL) {
        return NULL;
    }
    array->name = qk_strdup_or_null(name);
    if (array->name == NULL) {
        free(array);
        return NULL;
    }
    array->next = runtime->arrays;
    runtime->arrays = array;
    return array;
}

static void qk_clear_array(struct qk_array *array)
{
    if (array == NULL) {
        return;
    }
    qk_free_array_entries(array->entries);
    array->entries = NULL;
}

static bool qk_array_set(struct qk_runtime *runtime, const char *array_name, const char *key, const char *value)
{
    struct qk_array *array = qk_find_array(runtime, array_name, true);
    if (array == NULL) {
        return false;
    }

    struct qk_array_entry *entry = array->entries;
    while (entry != NULL) {
        if ((strcmp(entry->key, key) == 0)) {
            char *copy = qk_strdup_or_null(value);
            if (copy == NULL) {
                return false;
            }
            free(entry->value);
            entry->value = copy;
            return true;
        }
        entry = entry->next;
    }

    entry = calloc(1U, sizeof(*entry));
    if (entry == NULL) {
        return false;
    }
    entry->key = qk_strdup_or_null(key);
    entry->value = qk_strdup_or_null(value);
    if ((entry->key == NULL) || (entry->value == NULL)) {
        free(entry->key);
        free(entry->value);
        free(entry);
        return false;
    }
    entry->next = array->entries;
    array->entries = entry;
    return true;
}

static const char *qk_array_get_value(struct qk_runtime *runtime, const char *array_name, const char *key)
{
    struct qk_array *array = qk_find_array(runtime, array_name, false);
    if (array == NULL) {
        return QK_EMPTY_FIELD;
    }

    struct qk_array_entry *entry = array->entries;
    while (entry != NULL) {
        if (strcmp(entry->key, key) == 0) {
            return entry->value;
        }
        entry = entry->next;
    }
    return QK_EMPTY_FIELD;
}

static bool qk_array_delete_value(struct qk_runtime *runtime, const char *array_name, const char *key)
{
    struct qk_array *array = qk_find_array(runtime, array_name, false);
    if ((array == NULL) || (key == NULL)) {
        return false;
    }

    struct qk_array_entry *previous = NULL;
    struct qk_array_entry *entry = array->entries;
    while (entry != NULL) {
        if (strcmp(entry->key, key) == 0) {
            if (previous == NULL) {
                array->entries = entry->next;
            } else {
                previous->next = entry->next;
            }
            free(entry->key);
            free(entry->value);
            free(entry);
            return true;
        }
        previous = entry;
        entry = entry->next;
    }
    return false;
}

static bool qk_store_scratch(qk_runtime *runtime, const char *text, size_t length)
{
    size_t required = length + 1U;
    if (required > runtime->scratch_capacity) {
        char *next = realloc(runtime->scratch_buffer, required);
        if (next == NULL) {
            return false;
        }
        runtime->scratch_buffer = next;
        runtime->scratch_capacity = required;
    }
    memcpy(runtime->scratch_buffer, text, length);
    runtime->scratch_buffer[length] = '\0';
    return true;
}

static double qk_parse_awk_numeric_prefix(const char *text)
{
    char *end = NULL;
    double value;

    if (text == NULL) {
        return 0.0;
    }

    errno = 0;
    value = strtod(text, &end);
    if (end == text) {
        return 0.0;
    }
    return value;
}

static bool qk_pointer_aliases_scratch(const qk_runtime *runtime, const char *text)
{
    uintptr_t start;
    uintptr_t end;
    uintptr_t value;

    if ((runtime == NULL) || (runtime->scratch_buffer == NULL) || (text == NULL)) {
        return false;
    }

    start = (uintptr_t)runtime->scratch_buffer;
    end = start + runtime->scratch_capacity;
    value = (uintptr_t)text;
    return (value >= start) && (value < end);
}

static const char *qk_scalar_string_view(qk_runtime *runtime, struct qk_scalar_entry *entry)
{
    char *copy;

    if ((runtime == NULL) || (entry == NULL)) {
        return QK_EMPTY_FIELD;
    }

    if (entry->kind == QK_SCALAR_STRING) {
        return entry->string == NULL ? QK_EMPTY_FIELD : entry->string;
    }
    if (entry->kind != QK_SCALAR_NUMBER) {
        return QK_EMPTY_FIELD;
    }

    if (entry->string != NULL) {
        return entry->string;
    }

    copy = qk_strdup_or_null(qk_format_number(runtime, entry->number));
    if (copy == NULL) {
        return QK_EMPTY_FIELD;
    }
    entry->string = copy;
    return entry->string;
}

static const char *qk_output_variable_text(qk_runtime *runtime, const char *name, const char *fallback)
{
    struct qk_scalar_entry *entry;

    if ((runtime == NULL) || (name == NULL)) {
        return fallback == NULL ? QK_EMPTY_FIELD : fallback;
    }

    entry = qk_find_scalar(runtime, name, false);
    if (entry == NULL) {
        return fallback == NULL ? QK_EMPTY_FIELD : fallback;
    }
    if (entry->kind == QK_SCALAR_STRING) {
        return entry->string == NULL ? QK_EMPTY_FIELD : entry->string;
    }
    return fallback == NULL ? QK_EMPTY_FIELD : fallback;
}

static const char *qk_format_number_with_text(qk_runtime *runtime, double value, const char *format_text)
{
    char buffer[256];
    const char *effective_format = format_text;

    if (runtime == NULL) {
        return QK_EMPTY_FIELD;
    }
    if ((effective_format == NULL) || (*effective_format == '\0')) {
        effective_format = QK_DEFAULT_CONVFMT;
    }

    if (snprintf(buffer, sizeof(buffer), effective_format, value) < 0) {
        if (strcmp(effective_format, QK_DEFAULT_CONVFMT) != 0) {
            return qk_format_number_with_text(runtime, value, QK_DEFAULT_CONVFMT);
        }
        return QK_EMPTY_FIELD;
    }
    if (!qk_store_scratch(runtime, buffer, strlen(buffer))) {
        return QK_EMPTY_FIELD;
    }
    return runtime->scratch_buffer;
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
    char *cursor = runtime->field_buffer;

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
    char *field_start = runtime->field_buffer;

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
    free(runtime->field_buffer);
    runtime->field_buffer = qk_strdup_or_null(runtime->current_record);
    if ((runtime->current_record != NULL) && (runtime->field_buffer == NULL)) {
        return false;
    }

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
        runtime->fnr = 0.0;
        qk_set_current_filename(runtime, "-");
        return true;
    }

    while (runtime->next_input_index < runtime->argc) {
        const char *path = runtime->argv[runtime->next_input_index];
        runtime->next_input_index += 1;

        if (strcmp(path, "-") == 0) {
            runtime->current_handle = stdin;
            runtime->current_handle_is_stdin = true;
            runtime->fnr = 0.0;
            qk_set_current_filename(runtime, "-");
            return true;
        }

        runtime->current_handle = fopen(path, "r");
        if (runtime->current_handle != NULL) {
            runtime->current_handle_is_stdin = false;
            runtime->fnr = 0.0;
            qk_set_current_filename(runtime, path);
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

    if (!qk_scalar_set_string_value(runtime, "OFS", " ")) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_string_value(runtime, "ORS", "\n")) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_string_value(runtime, "OFMT", QK_DEFAULT_OFMT)) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_string_value(runtime, "CONVFMT", QK_DEFAULT_CONVFMT)) {
        qk_runtime_destroy(runtime);
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
    free(runtime->field_buffer);
    free(runtime->fields);
    free(runtime->field_separator);
    free(runtime->current_filename);
    free(runtime->scratch_buffer);
    qk_free_scalars(runtime->scalars);
    qk_free_arrays(runtime->arrays);
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
            runtime->nr += 1.0;
            runtime->fnr += 1.0;
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

static bool qk_rebuild_record_from_parts(qk_runtime *runtime, int64_t index, const char *value)
{
    if (index < 0) {
        return false;
    }
    if (index == 0) {
        free(runtime->current_record);
        runtime->current_record = qk_strdup_or_null(value);
        if ((value != NULL) && (runtime->current_record == NULL)) {
            return false;
        }
        return qk_rebuild_fields(runtime);
    }

    size_t target_fields = (size_t)index;
    if (target_fields < runtime->field_count) {
        target_fields = runtime->field_count;
    }

    size_t value_length = strlen(value == NULL ? "" : value);
    size_t total_length = 0U;
    for (size_t field_index = 0; field_index < target_fields; field_index += 1U) {
        const char *field_value = "";
        if ((int64_t)(field_index + 1U) == index) {
            field_value = value == NULL ? "" : value;
        } else if (field_index < runtime->field_count) {
            field_value = runtime->fields[field_index];
        }
        total_length += strlen(field_value);
        if (field_index + 1U < target_fields) {
            total_length += 1U;
        }
    }

    char *next_record = malloc(total_length + 1U);
    if (next_record == NULL) {
        return false;
    }

    char *cursor = next_record;
    for (size_t field_index = 0; field_index < target_fields; field_index += 1U) {
        const char *field_value = "";
        size_t field_length = 0U;
        if ((int64_t)(field_index + 1U) == index) {
            field_value = value == NULL ? "" : value;
            field_length = value_length;
        } else if (field_index < runtime->field_count) {
            field_value = runtime->fields[field_index];
            field_length = strlen(field_value);
        }
        memcpy(cursor, field_value, field_length);
        cursor += field_length;
        if (field_index + 1U < target_fields) {
            *cursor = ' ';
            cursor += 1U;
        }
    }
    *cursor = '\0';

    free(runtime->current_record);
    runtime->current_record = next_record;
    return qk_rebuild_fields(runtime);
}

void qk_set_field_string(qk_runtime *runtime, int64_t index, const char *value)
{
    if ((runtime == NULL) || !qk_rebuild_record_from_parts(runtime, index, value)) {
        return;
    }
}

void qk_set_field_number(qk_runtime *runtime, int64_t index, double value)
{
    qk_set_field_string(runtime, index, qk_format_number(runtime, value));
}

void qk_print_string(qk_runtime *runtime, const char *value)
{
    qk_print_string_fragment(runtime, value);
    qk_print_output_record_separator(runtime);
}

void qk_print_number(qk_runtime *runtime, double value)
{
    qk_print_number_fragment(runtime, value);
    qk_print_output_record_separator(runtime);
}

void qk_print_string_fragment(qk_runtime *runtime, const char *value)
{
    (void)runtime;
    fputs(value == NULL ? "" : value, stdout);
}

void qk_print_number_fragment(qk_runtime *runtime, double value)
{
    fputs(qk_format_number_with_text(runtime, value, qk_output_variable_text(runtime, "OFMT", QK_DEFAULT_OFMT)), stdout);
}

void qk_print_output_separator(qk_runtime *runtime)
{
    fputs(qk_output_variable_text(runtime, "OFS", " "), stdout);
}

void qk_print_output_record_separator(qk_runtime *runtime)
{
    fputs(qk_output_variable_text(runtime, "ORS", "\n"), stdout);
}

void qk_nextfile(qk_runtime *runtime)
{
    if (runtime == NULL) {
        return;
    }
    qk_close_current_handle(runtime);
}

void qk_request_exit(qk_runtime *runtime, int32_t status)
{
    if (runtime == NULL) {
        return;
    }
    runtime->exit_requested = true;
    runtime->exit_status = status;
}

bool qk_should_exit(qk_runtime *runtime)
{
    return (runtime != NULL) && runtime->exit_requested;
}

int32_t qk_exit_status(qk_runtime *runtime)
{
    if (runtime == NULL) {
        return 0;
    }
    return runtime->exit_requested ? runtime->exit_status : 0;
}

const char *qk_scalar_get(qk_runtime *runtime, const char *name)
{
    struct qk_scalar_entry *entry = qk_find_scalar(runtime, name, false);
    return qk_scalar_string_view(runtime, entry);
}

double qk_scalar_get_number(qk_runtime *runtime, const char *name)
{
    struct qk_scalar_entry *entry = qk_find_scalar(runtime, name, false);
    if (entry == NULL) {
        return 0.0;
    }
    if (entry->kind == QK_SCALAR_NUMBER) {
        return entry->number;
    }
    if (entry->kind == QK_SCALAR_STRING) {
        return qk_parse_awk_numeric_prefix(entry->string);
    }
    return 0.0;
}

bool qk_scalar_truthy(qk_runtime *runtime, const char *name)
{
    struct qk_scalar_entry *entry = qk_find_scalar(runtime, name, false);
    if (entry == NULL) {
        return false;
    }
    if (entry->kind == QK_SCALAR_NUMBER) {
        return entry->number != 0.0;
    }
    if (entry->kind == QK_SCALAR_STRING) {
        return (entry->string != NULL) && (entry->string[0] != '\0');
    }
    return false;
}

void qk_scalar_set_string(qk_runtime *runtime, const char *name, const char *value)
{
    if ((runtime == NULL) || (name == NULL)) {
        return;
    }
    (void)qk_scalar_set_string_value(runtime, name, value);
}

void qk_scalar_set_number(qk_runtime *runtime, const char *name, double value)
{
    if ((runtime == NULL) || (name == NULL)) {
        return;
    }
    (void)qk_scalar_set_number_value(runtime, name, value);
}

void qk_scalar_copy(qk_runtime *runtime, const char *target_name, const char *source_name)
{
    struct qk_scalar_entry *target;
    struct qk_scalar_entry *source;

    if ((runtime == NULL) || (target_name == NULL) || (source_name == NULL)) {
        return;
    }

    source = qk_find_scalar(runtime, source_name, false);
    target = qk_find_scalar(runtime, target_name, true);
    if (target == NULL) {
        return;
    }
    if (source == NULL) {
        qk_clear_scalar(target);
        return;
    }

    if (source->kind == QK_SCALAR_NUMBER) {
        (void)qk_scalar_set_number_value(runtime, target_name, source->number);
        return;
    }
    if (source->kind == QK_SCALAR_STRING) {
        (void)qk_scalar_set_string_value(runtime, target_name, source->string);
        return;
    }
    qk_clear_scalar(target);
}

const char *qk_format_number(qk_runtime *runtime, double value)
{
    return qk_format_number_with_text(runtime, value, qk_output_variable_text(runtime, "CONVFMT", QK_DEFAULT_CONVFMT));
}

const char *qk_concat(qk_runtime *runtime, const char *left, const char *right)
{
    char *left_copy = NULL;
    char *right_copy = NULL;
    size_t left_length;
    size_t right_length;

    if (runtime == NULL) {
        return QK_EMPTY_FIELD;
    }

    if (left == NULL) {
        left = "";
    }
    if (right == NULL) {
        right = "";
    }
    if (qk_pointer_aliases_scratch(runtime, left)) {
        left_copy = qk_strdup_or_null(left);
        if (left_copy == NULL) {
            return QK_EMPTY_FIELD;
        }
        left = left_copy;
    }
    if (qk_pointer_aliases_scratch(runtime, right)) {
        right_copy = qk_strdup_or_null(right);
        if (right_copy == NULL) {
            free(left_copy);
            return QK_EMPTY_FIELD;
        }
        right = right_copy;
    }

    left_length = strlen(left);
    right_length = strlen(right);
    if (!qk_store_scratch(runtime, left, left_length)) {
        free(left_copy);
        free(right_copy);
        return QK_EMPTY_FIELD;
    }
    if ((left_length + right_length + 1U) > runtime->scratch_capacity) {
        char *next = realloc(runtime->scratch_buffer, left_length + right_length + 1U);
        if (next == NULL) {
            free(left_copy);
            free(right_copy);
            return QK_EMPTY_FIELD;
        }
        runtime->scratch_buffer = next;
        runtime->scratch_capacity = left_length + right_length + 1U;
    }
    memcpy(runtime->scratch_buffer + left_length, right, right_length);
    runtime->scratch_buffer[left_length + right_length] = '\0';
    free(left_copy);
    free(right_copy);
    return runtime->scratch_buffer;
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

double qk_get_nr(qk_runtime *runtime)
{
    return runtime == NULL ? 0.0 : runtime->nr;
}

double qk_get_fnr(qk_runtime *runtime)
{
    return runtime == NULL ? 0.0 : runtime->fnr;
}

double qk_get_nf(qk_runtime *runtime)
{
    return runtime == NULL ? 0.0 : (double)runtime->field_count;
}

const char *qk_get_filename(qk_runtime *runtime)
{
    if ((runtime == NULL) || (runtime->current_filename == NULL)) {
        return "-";
    }
    return runtime->current_filename;
}

double qk_split_into_array(qk_runtime *runtime, const char *text, const char *array_name, const char *separator)
{
    if ((runtime == NULL) || (array_name == NULL) || (text == NULL)) {
        return 0.0;
    }

    struct qk_array *array = qk_find_array(runtime, array_name, true);
    if (array == NULL) {
        return 0.0;
    }
    qk_clear_array(array);

    char *buffer = qk_strdup_or_null(text);
    if (buffer == NULL) {
        return 0.0;
    }

    size_t count = 0U;
    if ((separator == NULL) || (*separator == '\0')) {
        char *cursor = buffer;
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
            count += 1U;
            char key[32];
            snprintf(key, sizeof(key), "%zu", count);
            if (!qk_array_set(runtime, array_name, key, field_start)) {
                free(buffer);
                return 0.0;
            }
        }
    } else {
        size_t separator_length = strlen(separator);
        char *field_start = buffer;
        if (separator_length == 0U) {
            (void)qk_array_set(runtime, array_name, "1", field_start);
            free(buffer);
            return 1.0;
        }
        for (;;) {
            char *match = strstr(field_start, separator);
            count += 1U;
            char key[32];
            snprintf(key, sizeof(key), "%zu", count);
            if (match == NULL) {
                if (!qk_array_set(runtime, array_name, key, field_start)) {
                    free(buffer);
                    return 0.0;
                }
                break;
            }
            *match = '\0';
            if (!qk_array_set(runtime, array_name, key, field_start)) {
                free(buffer);
                return 0.0;
            }
            field_start = match + separator_length;
        }
    }

    free(buffer);
    return (double)count;
}

const char *qk_array_get(qk_runtime *runtime, const char *array_name, const char *key)
{
    if ((runtime == NULL) || (array_name == NULL) || (key == NULL)) {
        return QK_EMPTY_FIELD;
    }
    return qk_array_get_value(runtime, array_name, key);
}

void qk_array_set_number(qk_runtime *runtime, const char *array_name, const char *key, double value)
{
    if ((runtime == NULL) || (array_name == NULL) || (key == NULL)) {
        return;
    }
    (void)qk_array_set(runtime, array_name, key, qk_format_number(runtime, value));
}

void qk_array_delete(qk_runtime *runtime, const char *array_name, const char *key)
{
    if ((runtime == NULL) || (array_name == NULL) || (key == NULL)) {
        return;
    }
    (void)qk_array_delete_value(runtime, array_name, key);
}

void qk_array_clear(qk_runtime *runtime, const char *array_name)
{
    if ((runtime == NULL) || (array_name == NULL)) {
        return;
    }
    qk_clear_array(qk_find_array(runtime, array_name, false));
}

double qk_array_length(qk_runtime *runtime, const char *array_name)
{
    struct qk_array *array = qk_find_array(runtime, array_name, false);
    if (array == NULL) {
        return 0.0;
    }

    size_t count = 0U;
    struct qk_array_entry *entry = array->entries;
    while (entry != NULL) {
        count += 1U;
        entry = entry->next;
    }
    return (double)count;
}

const char *qk_array_first_key(qk_runtime *runtime, const char *array_name)
{
    struct qk_array *array = qk_find_array(runtime, array_name, false);
    if ((array == NULL) || (array->entries == NULL)) {
        return NULL;
    }
    return array->entries->key;
}

const char *qk_array_next_key(qk_runtime *runtime, const char *array_name, const char *current_key)
{
    struct qk_array *array = qk_find_array(runtime, array_name, false);
    if ((array == NULL) || (current_key == NULL)) {
        return NULL;
    }

    struct qk_array_entry *entry = array->entries;
    while (entry != NULL) {
        if (strcmp(entry->key, current_key) == 0) {
            return entry->next == NULL ? NULL : entry->next->key;
        }
        entry = entry->next;
    }
    return NULL;
}

const char *qk_substr2(qk_runtime *runtime, const char *text, int64_t start)
{
    if ((runtime == NULL) || (text == NULL)) {
        return QK_EMPTY_FIELD;
    }
    size_t length = strlen(text);
    size_t start_index = start <= 1 ? 0U : (size_t)(start - 1);
    if (start_index > length) {
        start_index = length;
    }
    if (!qk_store_scratch(runtime, text + start_index, length - start_index)) {
        return QK_EMPTY_FIELD;
    }
    return runtime->scratch_buffer;
}

const char *qk_substr3(qk_runtime *runtime, const char *text, int64_t start, int64_t length)
{
    if ((runtime == NULL) || (text == NULL) || (length <= 0)) {
        return QK_EMPTY_FIELD;
    }
    size_t text_length = strlen(text);
    size_t start_index = start <= 1 ? 0U : (size_t)(start - 1);
    if (start_index > text_length) {
        start_index = text_length;
    }
    size_t slice_length = (size_t)length;
    if (slice_length > text_length - start_index) {
        slice_length = text_length - start_index;
    }
    if (!qk_store_scratch(runtime, text + start_index, slice_length)) {
        return QK_EMPTY_FIELD;
    }
    return runtime->scratch_buffer;
}
