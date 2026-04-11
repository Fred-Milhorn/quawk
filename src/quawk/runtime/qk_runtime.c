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
#include <math.h>
#include <regex.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>

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
    char record_separator[2];
    double nr;
    double fnr;
    char *current_filename;
    char *scratch_buffer;
    size_t scratch_capacity;
    char **temp_strings;
    size_t temp_string_count;
    size_t temp_string_capacity;
    int64_t random_seed;
    uint32_t random_state;
    struct qk_scalar_entry *scalars;
    struct qk_array *arrays;
    double *numeric_slots;
    size_t numeric_slot_count;
    char **string_slots;
    size_t string_slot_count;
    struct qk_cell *mixed_slots;
    size_t mixed_slot_count;
    struct qk_output_entry *outputs;
    struct qk_input_entry *inputs;
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

struct qk_output_entry {
    char *name;
    int32_t mode;
    bool is_pipe;
    FILE *handle;
    struct qk_output_entry *next;
};

struct qk_input_entry {
    char *name;
    FILE *handle;
    struct qk_input_entry *next;
};

struct qk_cell {
    double number;
    char *string;
    bool has_number;
    bool has_string;
};

static const char QK_EMPTY_FIELD[] = "";
static const char QK_DEFAULT_OFMT[] = "%.6g";
static const char QK_DEFAULT_CONVFMT[] = "%.6g";
static const double QK_RAND_MODULUS = 2147483648.0;
static const uint32_t QK_RAND_MASK = 0x7fffffffU;
static const uint32_t QK_RAND_MULTIPLIER = 1103515245U;
static const uint32_t QK_RAND_INCREMENT = 12345U;
static const int32_t QK_OUTPUT_WRITE = 1;
static const int32_t QK_OUTPUT_APPEND = 2;
static const int32_t QK_OUTPUT_PIPE = 3;
static const char QK_DEFAULT_SUBSEP[] = "\034";

enum qk_runtime_profile_function {
    QK_RUNTIME_PROFILE_NEXT_RECORD = 0,
    QK_RUNTIME_PROFILE_GET_FIELD,
    QK_RUNTIME_PROFILE_PRINT_STRING,
    QK_RUNTIME_PROFILE_PRINT_NUMBER,
    QK_RUNTIME_PROFILE_PRINT_STRING_FRAGMENT,
    QK_RUNTIME_PROFILE_PRINT_NUMBER_FRAGMENT,
    QK_RUNTIME_PROFILE_SCALAR_GET,
    QK_RUNTIME_PROFILE_SCALAR_GET_NUMBER,
    QK_RUNTIME_PROFILE_SCALAR_TRUTHY,
    QK_RUNTIME_PROFILE_SCALAR_SET_STRING,
    QK_RUNTIME_PROFILE_SCALAR_SET_NUMBER,
    QK_RUNTIME_PROFILE_SCALAR_COPY,
    QK_RUNTIME_PROFILE_COMPARE_VALUES,
    QK_RUNTIME_PROFILE_CAPTURE_STRING_ARG,
    QK_RUNTIME_PROFILE_FORMAT_NUMBER,
    QK_RUNTIME_PROFILE_GET_NR,
    QK_RUNTIME_PROFILE_GET_FNR,
    QK_RUNTIME_PROFILE_GET_NF,
    QK_RUNTIME_PROFILE_GET_FILENAME,
    QK_RUNTIME_PROFILE_GETLINE_MAIN_RECORD,
    QK_RUNTIME_PROFILE_GETLINE_MAIN_STRING,
    QK_RUNTIME_PROFILE_GETLINE_FILE_RECORD,
    QK_RUNTIME_PROFILE_GETLINE_FILE_STRING,
    QK_RUNTIME_PROFILE_NEXTFILE,
    QK_RUNTIME_PROFILE_FUNCTION_COUNT
};

static const char *const qk_runtime_profile_names[] = {
    [QK_RUNTIME_PROFILE_NEXT_RECORD] = "qk_next_record",
    [QK_RUNTIME_PROFILE_GET_FIELD] = "qk_get_field",
    [QK_RUNTIME_PROFILE_PRINT_STRING] = "qk_print_string",
    [QK_RUNTIME_PROFILE_PRINT_NUMBER] = "qk_print_number",
    [QK_RUNTIME_PROFILE_PRINT_STRING_FRAGMENT] = "qk_print_string_fragment",
    [QK_RUNTIME_PROFILE_PRINT_NUMBER_FRAGMENT] = "qk_print_number_fragment",
    [QK_RUNTIME_PROFILE_SCALAR_GET] = "qk_scalar_get",
    [QK_RUNTIME_PROFILE_SCALAR_GET_NUMBER] = "qk_scalar_get_number",
    [QK_RUNTIME_PROFILE_SCALAR_TRUTHY] = "qk_scalar_truthy",
    [QK_RUNTIME_PROFILE_SCALAR_SET_STRING] = "qk_scalar_set_string",
    [QK_RUNTIME_PROFILE_SCALAR_SET_NUMBER] = "qk_scalar_set_number",
    [QK_RUNTIME_PROFILE_SCALAR_COPY] = "qk_scalar_copy",
    [QK_RUNTIME_PROFILE_COMPARE_VALUES] = "qk_compare_values",
    [QK_RUNTIME_PROFILE_CAPTURE_STRING_ARG] = "qk_capture_string_arg",
    [QK_RUNTIME_PROFILE_FORMAT_NUMBER] = "qk_format_number",
    [QK_RUNTIME_PROFILE_GET_NR] = "qk_get_nr",
    [QK_RUNTIME_PROFILE_GET_FNR] = "qk_get_fnr",
    [QK_RUNTIME_PROFILE_GET_NF] = "qk_get_nf",
    [QK_RUNTIME_PROFILE_GET_FILENAME] = "qk_get_filename",
    [QK_RUNTIME_PROFILE_GETLINE_MAIN_RECORD] = "qk_getline_main_record",
    [QK_RUNTIME_PROFILE_GETLINE_MAIN_STRING] = "qk_getline_main_string",
    [QK_RUNTIME_PROFILE_GETLINE_FILE_RECORD] = "qk_getline_file_record",
    [QK_RUNTIME_PROFILE_GETLINE_FILE_STRING] = "qk_getline_file_string",
    [QK_RUNTIME_PROFILE_NEXTFILE] = "qk_nextfile",
};

static uint64_t qk_runtime_profile_counts[QK_RUNTIME_PROFILE_FUNCTION_COUNT];
static bool qk_runtime_profile_checked = false;
static bool qk_runtime_profile_enabled = false;

static void qk_runtime_profile_dump(void);
static void qk_runtime_profile_note(enum qk_runtime_profile_function function);
static bool qk_runtime_profile_is_enabled(void);
static void qk_runtime_profile_prepare(void);

static const char *qk_output_variable_text(qk_runtime *runtime, const char *name, const char *fallback);
static bool qk_rebuild_fields(qk_runtime *runtime);
static bool qk_rebuild_current_record(qk_runtime *runtime, size_t target_fields, int64_t index, const char *value);
static const char *qk_scalar_string_view(qk_runtime *runtime, struct qk_scalar_entry *entry);
static bool qk_update_field_separator(qk_runtime *runtime, const char *text);
static void qk_update_record_separator(qk_runtime *runtime, const char *text);
static bool qk_ensure_numeric_slot_capacity(qk_runtime *runtime, size_t required_count);
static bool qk_ensure_string_slot_capacity(qk_runtime *runtime, size_t required_count);
static bool qk_ensure_mixed_slot_capacity(qk_runtime *runtime, size_t required_count);
static void qk_free_slot_strings(qk_runtime *runtime);
static void qk_free_mixed_slot_strings(qk_runtime *runtime);
extern char **environ;

static bool qk_runtime_profile_is_enabled(void)
{
    const char *enabled_value;

    if (!qk_runtime_profile_checked) {
        enabled_value = getenv("QUAWK_RUNTIME_PROFILE");
        qk_runtime_profile_enabled = (enabled_value != NULL) && (enabled_value[0] != '\0') && (strcmp(enabled_value, "0") != 0);
        qk_runtime_profile_checked = true;
        if (qk_runtime_profile_enabled) {
            (void)atexit(qk_runtime_profile_dump);
        }
    }
    return qk_runtime_profile_enabled;
}

static void qk_runtime_profile_prepare(void)
{
    (void)qk_runtime_profile_is_enabled();
}

static void qk_runtime_profile_note(enum qk_runtime_profile_function function)
{
    if (qk_runtime_profile_is_enabled()) {
        qk_runtime_profile_counts[function] += 1U;
    }
}

static void qk_runtime_profile_dump(void)
{
    bool selected[QK_RUNTIME_PROFILE_FUNCTION_COUNT] = { false };
    size_t rank;

    if (!qk_runtime_profile_enabled) {
        return;
    }

    fprintf(stderr, "quawk-runtime-profile top=10\n");
    for (rank = 0U; rank < 10U; rank += 1U) {
        size_t best_index = QK_RUNTIME_PROFILE_FUNCTION_COUNT;
        uint64_t best_count = 0U;
        size_t index;

        for (index = 0U; index < QK_RUNTIME_PROFILE_FUNCTION_COUNT; index += 1U) {
            if (selected[index] || (qk_runtime_profile_names[index] == NULL)) {
                continue;
            }
            if ((best_index == QK_RUNTIME_PROFILE_FUNCTION_COUNT) || (qk_runtime_profile_counts[index] > best_count)) {
                best_index = index;
                best_count = qk_runtime_profile_counts[index];
            }
        }

        if ((best_index == QK_RUNTIME_PROFILE_FUNCTION_COUNT) || (best_count == 0U)) {
            break;
        }

        selected[best_index] = true;
        fprintf(
            stderr,
            "quawk-runtime-profile %zu %s %llu\n",
            rank + 1U,
            qk_runtime_profile_names[best_index],
            (unsigned long long)best_count
        );
    }
}

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

static bool qk_replace_current_record(qk_runtime *runtime, const char *text)
{
    size_t capacity = 0U;
    char *copy;

    if (runtime == NULL) {
        return false;
    }

    if (text != NULL) {
        capacity = strlen(text) + 1U;
    }
    copy = qk_strdup_or_null(text);
    if ((text != NULL) && (copy == NULL)) {
        return false;
    }

    free(runtime->current_record);
    runtime->current_record = copy;
    runtime->current_record_capacity = capacity;
    return true;
}

static bool qk_ensure_numeric_slot_capacity(qk_runtime *runtime, size_t required_count)
{
    size_t old_count;
    size_t new_count;
    double *resized;

    if ((runtime == NULL) || (required_count <= runtime->numeric_slot_count)) {
        return true;
    }

    old_count = runtime->numeric_slot_count;
    new_count = old_count == 0U ? 8U : old_count;
    while (new_count < required_count) {
        size_t next_count = new_count * 2U;
        if (next_count <= new_count) {
            new_count = required_count;
            break;
        }
        new_count = next_count;
    }

    resized = realloc(runtime->numeric_slots, new_count * sizeof(*resized));
    if (resized == NULL) {
        return false;
    }
    memset(resized + old_count, 0, (new_count - old_count) * sizeof(*resized));
    runtime->numeric_slots = resized;
    runtime->numeric_slot_count = new_count;
    return true;
}

static bool qk_ensure_string_slot_capacity(qk_runtime *runtime, size_t required_count)
{
    size_t old_count;
    size_t new_count;
    char **resized;

    if ((runtime == NULL) || (required_count <= runtime->string_slot_count)) {
        return true;
    }

    old_count = runtime->string_slot_count;
    new_count = old_count == 0U ? 8U : old_count;
    while (new_count < required_count) {
        size_t next_count = new_count * 2U;
        if (next_count <= new_count) {
            new_count = required_count;
            break;
        }
        new_count = next_count;
    }

    resized = realloc(runtime->string_slots, new_count * sizeof(*resized));
    if (resized == NULL) {
        return false;
    }
    memset(resized + old_count, 0, (new_count - old_count) * sizeof(*resized));
    runtime->string_slots = resized;
    runtime->string_slot_count = new_count;
    return true;
}

static bool qk_ensure_mixed_slot_capacity(qk_runtime *runtime, size_t required_count)
{
    size_t old_count;
    size_t new_count;
    struct qk_cell *resized;

    if ((runtime == NULL) || (required_count <= runtime->mixed_slot_count)) {
        return true;
    }

    old_count = runtime->mixed_slot_count;
    new_count = old_count == 0U ? 8U : old_count;
    while (new_count < required_count) {
        size_t next_count = new_count * 2U;
        if (next_count <= new_count) {
            new_count = required_count;
            break;
        }
        new_count = next_count;
    }

    resized = realloc(runtime->mixed_slots, new_count * sizeof(*resized));
    if (resized == NULL) {
        return false;
    }
    memset(resized + old_count, 0, (new_count - old_count) * sizeof(*resized));
    runtime->mixed_slots = resized;
    runtime->mixed_slot_count = new_count;
    return true;
}

static void qk_free_slot_strings(qk_runtime *runtime)
{
    size_t index;

    if ((runtime == NULL) || (runtime->string_slots == NULL)) {
        return;
    }

    for (index = 0U; index < runtime->string_slot_count; index += 1U) {
        free(runtime->string_slots[index]);
    }
}

static void qk_free_mixed_slot_strings(qk_runtime *runtime)
{
    size_t index;

    if ((runtime == NULL) || (runtime->mixed_slots == NULL)) {
        return;
    }

    for (index = 0U; index < runtime->mixed_slot_count; index += 1U) {
        free(runtime->mixed_slots[index].string);
        runtime->mixed_slots[index].string = NULL;
    }
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

static void qk_clear_temp_strings(qk_runtime *runtime)
{
    size_t index;

    if (runtime == NULL) {
        return;
    }

    for (index = 0U; index < runtime->temp_string_count; index += 1U) {
        free(runtime->temp_strings[index]);
    }
    runtime->temp_string_count = 0U;
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

static double qk_close_output_entry(struct qk_output_entry *entry)
{
    int close_result;

    if ((entry == NULL) || (entry->handle == NULL)) {
        return -1.0;
    }

    if (entry->is_pipe) {
        close_result = pclose(entry->handle);
    } else {
        close_result = fclose(entry->handle);
    }
    entry->handle = NULL;
    if (close_result < 0) {
        return -1.0;
    }
    return (double)close_result;
}

static void qk_free_outputs(struct qk_output_entry *entry)
{
    while (entry != NULL) {
        struct qk_output_entry *next = entry->next;
        (void)qk_close_output_entry(entry);
        free(entry->name);
        free(entry);
        entry = next;
    }
}

static double qk_close_input_entry(struct qk_input_entry *entry)
{
    int close_result;

    if ((entry == NULL) || (entry->handle == NULL)) {
        return -1.0;
    }

    close_result = fclose(entry->handle);
    entry->handle = NULL;
    if (close_result < 0) {
        return -1.0;
    }
    return (double)close_result;
}

static void qk_free_inputs(struct qk_input_entry *entry)
{
    while (entry != NULL) {
        struct qk_input_entry *next = entry->next;
        (void)qk_close_input_entry(entry);
        free(entry->name);
        free(entry);
        entry = next;
    }
}

static struct qk_input_entry *qk_find_input(qk_runtime *runtime, const char *name)
{
    struct qk_input_entry *entry;

    if ((runtime == NULL) || (name == NULL)) {
        return NULL;
    }

    entry = runtime->inputs;
    while (entry != NULL) {
        if ((entry->name != NULL) && (strcmp(entry->name, name) == 0)) {
            return entry;
        }
        entry = entry->next;
    }
    return NULL;
}

static struct qk_output_entry *qk_find_output(qk_runtime *runtime, const char *name, int32_t mode)
{
    struct qk_output_entry *entry;

    if ((runtime == NULL) || (name == NULL)) {
        return NULL;
    }

    entry = runtime->outputs;
    while (entry != NULL) {
        if ((entry->mode == mode) && (entry->name != NULL) && (strcmp(entry->name, name) == 0)) {
            return entry;
        }
        entry = entry->next;
    }
    return NULL;
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

static bool qk_apply_scalar_side_effects(qk_runtime *runtime, const char *name)
{
    struct qk_scalar_entry *entry;
    const char *text;
    int64_t target_fields;

    if ((runtime == NULL) || (name == NULL)) {
        return false;
    }

    entry = qk_find_scalar(runtime, name, false);
    if (entry == NULL) {
        return false;
    }

    if (strcmp(name, "FS") == 0) {
        text = qk_scalar_string_view(runtime, entry);
        return qk_update_field_separator(runtime, text);
    }
    if (strcmp(name, "RS") == 0) {
        text = qk_scalar_string_view(runtime, entry);
        qk_update_record_separator(runtime, text);
        return true;
    }
    if (strcmp(name, "NF") == 0) {
        target_fields = (int64_t)qk_scalar_get_number(runtime, "NF");
        if (target_fields < 0) {
            return false;
        }
        if (!qk_rebuild_current_record(runtime, (size_t)target_fields, -1, NULL)) {
            return false;
        }
        return qk_scalar_set_number_value(runtime, "NF", (double)runtime->field_count);
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

static bool qk_reserve_scratch(qk_runtime *runtime, size_t length)
{
    size_t required;
    char *next;

    if (runtime == NULL) {
        return false;
    }

    required = length + 1U;
    if (required <= runtime->scratch_capacity) {
        return true;
    }

    next = realloc(runtime->scratch_buffer, required);
    if (next == NULL) {
        return false;
    }
    runtime->scratch_buffer = next;
    runtime->scratch_capacity = required;
    return true;
}

static bool qk_append_scratch(qk_runtime *runtime, size_t *offset, const char *text, size_t length)
{
    size_t start;

    if ((runtime == NULL) || (offset == NULL)) {
        return false;
    }
    if ((text == NULL) && (length != 0U)) {
        return false;
    }

    start = *offset;
    if (!qk_reserve_scratch(runtime, start + length)) {
        return false;
    }
    if (length != 0U) {
        memcpy(runtime->scratch_buffer + start, text, length);
    }
    start += length;
    runtime->scratch_buffer[start] = '\0';
    *offset = start;
    return true;
}

static bool qk_append_char_scratch(qk_runtime *runtime, size_t *offset, char value)
{
    return qk_append_scratch(runtime, offset, &value, 1U);
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

static bool qk_is_full_numeric_string(const char *text)
{
    char *end = NULL;

    if (text == NULL) {
        return false;
    }

    while (isspace((unsigned char)*text)) {
        text += 1;
    }
    if (*text == '\0') {
        return false;
    }

    errno = 0;
    (void)strtod(text, &end);
    if (end == text) {
        return false;
    }
    while ((*end != '\0') && isspace((unsigned char)*end)) {
        end += 1;
    }
    return *end == '\0';
}

static bool qk_compare_numbers(double left, double right, int32_t op)
{
    switch (op) {
        case 0:
            return left < right;
        case 1:
            return left <= right;
        case 2:
            return left > right;
        case 3:
            return left >= right;
        case 4:
            return left == right;
        case 5:
            return left != right;
        default:
            return false;
    }
}

static bool qk_compare_strings(const char *left, const char *right, int32_t op)
{
    int cmp = strcmp(left == NULL ? "" : left, right == NULL ? "" : right);

    switch (op) {
        case 0:
            return cmp < 0;
        case 1:
            return cmp <= 0;
        case 2:
            return cmp > 0;
        case 3:
            return cmp >= 0;
        case 4:
            return cmp == 0;
        case 5:
            return cmp != 0;
        default:
            return false;
    }
}

static bool qk_regex_match_text_impl(const char *text, const char *pattern)
{
    regex_t regex;
    int result;

    if ((text == NULL) || (pattern == NULL)) {
        return false;
    }
    if (regcomp(&regex, pattern, REG_EXTENDED) != 0) {
        return false;
    }

    result = regexec(&regex, text, 0, NULL, 0);
    regfree(&regex);
    return result == 0;
}

static uint32_t qk_normalize_seed(double value)
{
    return ((uint32_t)((int64_t)trunc(value))) & QK_RAND_MASK;
}

static uint32_t qk_next_rand_state(uint32_t state)
{
    return (QK_RAND_MULTIPLIER * state + QK_RAND_INCREMENT) & QK_RAND_MASK;
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

static bool qk_update_field_separator(qk_runtime *runtime, const char *text)
{
    char *copy = NULL;

    if (runtime == NULL) {
        return false;
    }
    if ((text != NULL) && (*text != '\0') && !((text[0] == ' ') && (text[1] == '\0'))) {
        copy = qk_strdup_or_null(text);
        if (copy == NULL) {
            return false;
        }
    }

    free(runtime->field_separator);
    runtime->field_separator = copy;
    return true;
}

static void qk_update_record_separator(qk_runtime *runtime, const char *text)
{
    char separator = '\n';

    if ((runtime != NULL) && (text != NULL) && (*text != '\0')) {
        separator = text[0];
    }
    if (runtime == NULL) {
        return;
    }
    runtime->record_separator[0] = separator;
    runtime->record_separator[1] = '\0';
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
    bool ok;

    runtime->field_count = 0U;
    free(runtime->field_buffer);
    runtime->field_buffer = qk_strdup_or_null(runtime->current_record);
    if ((runtime->current_record != NULL) && (runtime->field_buffer == NULL)) {
        return false;
    }

    if ((runtime->field_separator == NULL) || (*runtime->field_separator == '\0')) {
        ok = qk_split_whitespace_fields(runtime);
    } else {
        ok = qk_split_literal_separator_fields(runtime);
    }
    if (!ok) {
        return false;
    }
    return qk_scalar_set_number_value(runtime, "NF", (double)runtime->field_count);
}

static bool qk_rebuild_current_record(
    qk_runtime *runtime,
    size_t target_fields,
    int64_t index,
    const char *value
)
{
    const char *separator;
    size_t separator_length;
    size_t total_length = 0U;
    size_t total_field_buffer_length = target_fields == 0U ? 1U : 0U;
    char *next_record;
    char *next_field_buffer;
    char *cursor;
    char *field_cursor;
    char **next_fields;

    if (runtime == NULL) {
        return false;
    }
    if (index == 0) {
        if (!qk_replace_current_record(runtime, value)) {
            return false;
        }
        return qk_rebuild_fields(runtime);
    }
    if (runtime->current_record == NULL) {
        return true;
    }

    if ((index > 0) && (target_fields < (size_t)index)) {
        target_fields = (size_t)index;
    }

    separator = qk_output_variable_text(runtime, "OFS", " ");
    separator_length = strlen(separator);

    for (size_t field_index = 0; field_index < target_fields; field_index += 1U) {
        const char *field_value = "";
        if ((index > 0) && ((int64_t)(field_index + 1U) == index)) {
            field_value = value == NULL ? "" : value;
        } else if (field_index < runtime->field_count) {
            field_value = runtime->fields[field_index];
        }
        total_length += strlen(field_value);
        total_field_buffer_length += strlen(field_value) + 1U;
        if (field_index + 1U < target_fields) {
            total_length += separator_length;
        }
    }

    next_record = malloc(total_length + 1U);
    if (next_record == NULL) {
        return false;
    }
    next_field_buffer = malloc(total_field_buffer_length);
    if (next_field_buffer == NULL) {
        free(next_record);
        return false;
    }
    if (target_fields > runtime->field_capacity) {
        next_fields = realloc(runtime->fields, target_fields * sizeof(*next_fields));
        if (next_fields == NULL) {
            free(next_record);
            free(next_field_buffer);
            return false;
        }
        runtime->fields = next_fields;
        runtime->field_capacity = target_fields;
    }

    cursor = next_record;
    field_cursor = next_field_buffer;
    for (size_t field_index = 0; field_index < target_fields; field_index += 1U) {
        const char *field_value = "";
        size_t field_length = 0U;
        if ((index > 0) && ((int64_t)(field_index + 1U) == index)) {
            field_value = value == NULL ? "" : value;
        } else if (field_index < runtime->field_count) {
            field_value = runtime->fields[field_index];
        }
        field_length = strlen(field_value);
        memcpy(cursor, field_value, field_length);
        cursor += field_length;
        memcpy(field_cursor, field_value, field_length + 1U);
        runtime->fields[field_index] = field_cursor;
        field_cursor += field_length + 1U;
        if (field_index + 1U < target_fields) {
            memcpy(cursor, separator, separator_length);
            cursor += separator_length;
        }
    }
    *cursor = '\0';
    if (target_fields == 0U) {
        next_field_buffer[0] = '\0';
    }

    free(runtime->current_record);
    free(runtime->field_buffer);
    runtime->current_record = next_record;
    runtime->current_record_capacity = total_length + 1U;
    runtime->field_buffer = next_field_buffer;
    runtime->field_count = target_fields;
    return qk_scalar_set_number_value(runtime, "NF", (double)runtime->field_count);
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

static ssize_t qk_read_record(
    qk_runtime *runtime,
    FILE *handle,
    char **buffer,
    size_t *capacity
)
{
    int next_char;
    size_t length = 0U;
    char separator;

    if ((runtime == NULL) || (handle == NULL) || (buffer == NULL) || (capacity == NULL)) {
        return -1;
    }

    separator = runtime->record_separator[0] == '\0' ? '\n' : runtime->record_separator[0];
    if ((*buffer == NULL) || (*capacity == 0U)) {
        *capacity = 128U;
        *buffer = calloc(*capacity, sizeof(**buffer));
        if (*buffer == NULL) {
            *capacity = 0U;
            return -1;
        }
    }

    for (;;) {
        next_char = fgetc(handle);
        if (next_char == EOF) {
            if (ferror(handle) || (length > 0U)) {
                break;
            }
            return -1;
        }
        if ((char)next_char == separator) {
            break;
        }
        if ((length + 1U) >= *capacity) {
            size_t next_capacity = *capacity * 2U;
            char *next_buffer = realloc(*buffer, next_capacity);
            if (next_buffer == NULL) {
                return -1;
            }
            *buffer = next_buffer;
            *capacity = next_capacity;
        }
        (*buffer)[length] = (char)next_char;
        length += 1U;
    }

    if ((separator == '\n') && (length > 0U) && ((*buffer)[length - 1U] == '\r')) {
        length -= 1U;
    }
    (*buffer)[length] = '\0';
    return (ssize_t)length;
}

static double qk_read_main_line(qk_runtime *runtime, bool update_record, const char **result_out)
{
    ssize_t line_length;
    char **line_buffer;
    size_t *line_capacity;

    if (result_out != NULL) {
        *result_out = QK_EMPTY_FIELD;
    }
    if (runtime == NULL) {
        return -1.0;
    }

    if (update_record) {
        line_buffer = &runtime->current_record;
        line_capacity = &runtime->current_record_capacity;
    } else {
        line_buffer = &runtime->scratch_buffer;
        line_capacity = &runtime->scratch_capacity;
    }

    for (;;) {
        if ((runtime->current_handle == NULL) && !qk_open_next_input(runtime)) {
            return runtime->had_error ? -1.0 : 0.0;
        }

        line_length = qk_read_record(runtime, runtime->current_handle, line_buffer, line_capacity);
        if (line_length >= 0) {
            runtime->nr += 1.0;
            runtime->fnr += 1.0;
            if (result_out != NULL) {
                *result_out = *line_buffer;
            }
            if (update_record) {
                return qk_rebuild_fields(runtime) ? 1.0 : -1.0;
            }
            return 1.0;
        }

        if (feof(runtime->current_handle)) {
            qk_close_current_handle(runtime);
            continue;
        }

        runtime->had_error = true;
        qk_close_current_handle(runtime);
        return -1.0;
    }
}

static FILE *qk_open_input(qk_runtime *runtime, const char *target)
{
    struct qk_input_entry *entry;

    if ((runtime == NULL) || (target == NULL)) {
        return NULL;
    }

    entry = qk_find_input(runtime, target);
    if (entry != NULL) {
        return entry->handle;
    }

    entry = calloc(1U, sizeof(*entry));
    if (entry == NULL) {
        return NULL;
    }
    entry->name = qk_strdup_or_null(target);
    if (entry->name == NULL) {
        free(entry);
        return NULL;
    }
    entry->handle = fopen(target, "r");
    if (entry->handle == NULL) {
        free(entry->name);
        free(entry);
        return NULL;
    }

    entry->next = runtime->inputs;
    runtime->inputs = entry;
    return entry->handle;
}

static double qk_close_input(qk_runtime *runtime, const char *target)
{
    struct qk_input_entry *entry;
    struct qk_input_entry *previous;

    if ((runtime == NULL) || (target == NULL)) {
        return -1.0;
    }

    previous = NULL;
    entry = runtime->inputs;
    while (entry != NULL) {
        struct qk_input_entry *next = entry->next;
        if ((entry->name != NULL) && (strcmp(entry->name, target) == 0)) {
            double result = qk_close_input_entry(entry);
            if (previous == NULL) {
                runtime->inputs = next;
            } else {
                previous->next = next;
            }
            free(entry->name);
            free(entry);
            return result;
        }
        previous = entry;
        entry = next;
    }

    return -1.0;
}

static double qk_read_file_line(
    qk_runtime *runtime,
    const char *target,
    bool update_record,
    const char **result_out
)
{
    FILE *handle;
    ssize_t line_length;

    if (result_out != NULL) {
        *result_out = QK_EMPTY_FIELD;
    }
    if ((runtime == NULL) || (target == NULL)) {
        return -1.0;
    }

    handle = qk_open_input(runtime, target);
    if (handle == NULL) {
        return -1.0;
    }

    line_length = qk_read_record(
        runtime,
        handle,
        &runtime->scratch_buffer,
        &runtime->scratch_capacity
    );
    if (line_length < 0) {
        if (feof(handle)) {
            return 0.0;
        }
        return -1.0;
    }

    if (result_out != NULL) {
        *result_out = runtime->scratch_buffer;
    }
    if (update_record) {
        if (!qk_replace_current_record(runtime, runtime->scratch_buffer)) {
            return -1.0;
        }
        return qk_rebuild_fields(runtime) ? 1.0 : -1.0;
    }
    return 1.0;
}

qk_runtime *qk_runtime_create(int argc, char **argv, const char *field_separator)
{
    qk_runtime_profile_prepare();
    int index;

    qk_runtime *runtime = calloc(1U, sizeof(*runtime));
    if (runtime == NULL) {
        return NULL;
    }

    runtime->argc = argc;
    runtime->argv = argv;
    runtime->random_seed = 1;
    runtime->random_state = 1U;
    qk_update_record_separator(runtime, "\n");

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
    if (!qk_scalar_set_string_value(runtime, "FS", field_separator == NULL ? " " : field_separator)) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_update_field_separator(runtime, field_separator == NULL ? " " : field_separator)) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_string_value(runtime, "RS", "\n")) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_number_value(runtime, "RSTART", 0.0)) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_number_value(runtime, "RLENGTH", -1.0)) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_number_value(runtime, "ARGC", (double)(argc + 1))) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_scalar_set_string_value(runtime, "SUBSEP", QK_DEFAULT_SUBSEP)) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_ensure_mixed_slot_capacity(runtime, 8U)) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    if (!qk_array_set(runtime, "ARGV", "0", "quawk")) {
        qk_runtime_destroy(runtime);
        return NULL;
    }
    for (index = 0; index < argc; index += 1) {
        char key[32];
        snprintf(key, sizeof(key), "%d", index + 1);
        if (!qk_array_set(runtime, "ARGV", key, argv[index])) {
            qk_runtime_destroy(runtime);
            return NULL;
        }
    }
    if (environ != NULL) {
        for (index = 0; environ[index] != NULL; index += 1) {
            char *separator = strchr(environ[index], '=');
            size_t name_length;
            char *name;

            if (separator == NULL) {
                continue;
            }
            name_length = (size_t)(separator - environ[index]);
            name = malloc(name_length + 1U);
            if (name == NULL) {
                qk_runtime_destroy(runtime);
                return NULL;
            }
            memcpy(name, environ[index], name_length);
            name[name_length] = '\0';
            if (!qk_array_set(runtime, "ENVIRON", name, separator + 1)) {
                free(name);
                qk_runtime_destroy(runtime);
                return NULL;
            }
            free(name);
        }
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
    qk_clear_temp_strings(runtime);
    free(runtime->temp_strings);
    qk_free_scalars(runtime->scalars);
    qk_free_arrays(runtime->arrays);
    free(runtime->numeric_slots);
    qk_free_slot_strings(runtime);
    free(runtime->string_slots);
    qk_free_mixed_slot_strings(runtime);
    free(runtime->mixed_slots);
    qk_free_outputs(runtime->outputs);
    qk_free_inputs(runtime->inputs);
    free(runtime);
}

bool qk_next_record(qk_runtime *runtime)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_NEXT_RECORD);
    return qk_read_main_line(runtime, true, NULL) > 0.0;
}

const char *qk_get_field(qk_runtime *runtime, int64_t index)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GET_FIELD);
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
    return qk_rebuild_current_record(runtime, runtime->field_count, index, value);
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

double qk_slot_get_number(qk_runtime *runtime, int64_t slot_index)
{
    size_t index;

    if ((runtime == NULL) || (slot_index < 0)) {
        return 0.0;
    }

    index = (size_t)slot_index;
    if (index >= runtime->numeric_slot_count) {
        return 0.0;
    }
    return runtime->numeric_slots[index];
}

void qk_slot_set_number(qk_runtime *runtime, int64_t slot_index, double value)
{
    size_t required_count;

    if ((runtime == NULL) || (slot_index < 0)) {
        return;
    }

    required_count = (size_t)slot_index + 1U;
    if (!qk_ensure_numeric_slot_capacity(runtime, required_count)) {
        return;
    }
    runtime->numeric_slots[(size_t)slot_index] = value;
}

const char *qk_slot_get_string(qk_runtime *runtime, int64_t slot_index)
{
    size_t index;

    if ((runtime == NULL) || (slot_index < 0)) {
        return QK_EMPTY_FIELD;
    }

    index = (size_t)slot_index;
    if ((index >= runtime->string_slot_count) || (runtime->string_slots[index] == NULL)) {
        return QK_EMPTY_FIELD;
    }
    return runtime->string_slots[index];
}

void qk_slot_set_string(qk_runtime *runtime, int64_t slot_index, const char *value)
{
    size_t required_count;
    size_t index;
    char *copy;

    if ((runtime == NULL) || (slot_index < 0)) {
        return;
    }

    required_count = (size_t)slot_index + 1U;
    if (!qk_ensure_string_slot_capacity(runtime, required_count)) {
        return;
    }

    index = (size_t)slot_index;
    copy = qk_strdup_or_null(value == NULL ? QK_EMPTY_FIELD : value);
    if (copy == NULL) {
        return;
    }

    free(runtime->string_slots[index]);
    runtime->string_slots[index] = copy;
}

FILE *qk_open_output(qk_runtime *runtime, const char *target, int32_t mode)
{
    struct qk_output_entry *entry;
    const char *file_mode;

    if ((runtime == NULL) || (target == NULL)) {
        return NULL;
    }

    entry = qk_find_output(runtime, target, mode);
    if (entry != NULL) {
        return entry->handle;
    }

    entry = calloc(1U, sizeof(*entry));
    if (entry == NULL) {
        return NULL;
    }
    entry->name = qk_strdup_or_null(target);
    if (entry->name == NULL) {
        free(entry);
        return NULL;
    }
    entry->mode = mode;
    entry->is_pipe = mode == QK_OUTPUT_PIPE;

    if (mode == QK_OUTPUT_PIPE) {
        entry->handle = popen(target, "w");
    } else {
        file_mode = mode == QK_OUTPUT_APPEND ? "a" : (mode == QK_OUTPUT_WRITE ? "w" : "w");
        entry->handle = fopen(target, file_mode);
    }
    if (entry->handle == NULL) {
        free(entry->name);
        free(entry);
        return NULL;
    }

    entry->next = runtime->outputs;
    runtime->outputs = entry;
    return entry->handle;
}

double qk_close_output(qk_runtime *runtime, const char *target)
{
    struct qk_output_entry *entry;
    struct qk_output_entry *previous;
    double result = -1.0;
    bool found = false;

    if ((runtime == NULL) || (target == NULL)) {
        return -1.0;
    }

    previous = NULL;
    entry = runtime->outputs;
    while (entry != NULL) {
        struct qk_output_entry *next = entry->next;
        if ((entry->name != NULL) && (strcmp(entry->name, target) == 0)) {
            found = true;
            result = qk_close_output_entry(entry);
            if (previous == NULL) {
                runtime->outputs = next;
            } else {
                previous->next = next;
            }
            free(entry->name);
            free(entry);
            entry = next;
            continue;
        }
        previous = entry;
        entry = next;
    }

    if (found) {
        return result;
    }
    return qk_close_input(runtime, target);
}

void qk_write_output_string(FILE *handle, const char *value)
{
    if (handle == NULL) {
        return;
    }
    fputs(value == NULL ? "" : value, handle);
}

void qk_write_output_number(qk_runtime *runtime, FILE *handle, double value)
{
    if (handle == NULL) {
        return;
    }
    fputs(qk_format_number_with_text(runtime, value, qk_output_variable_text(runtime, "OFMT", QK_DEFAULT_OFMT)), handle);
}

void qk_write_output_separator(qk_runtime *runtime, FILE *handle)
{
    if (handle == NULL) {
        return;
    }
    fputs(qk_output_variable_text(runtime, "OFS", " "), handle);
}

void qk_write_output_record_separator(qk_runtime *runtime, FILE *handle)
{
    if (handle == NULL) {
        return;
    }
    fputs(qk_output_variable_text(runtime, "ORS", "\n"), handle);
}

void qk_print_string(qk_runtime *runtime, const char *value)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_PRINT_STRING);
    qk_print_string_fragment(runtime, value);
    qk_print_output_record_separator(runtime);
}

void qk_print_number(qk_runtime *runtime, double value)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_PRINT_NUMBER);
    qk_print_number_fragment(runtime, value);
    qk_print_output_record_separator(runtime);
}

void qk_print_string_fragment(qk_runtime *runtime, const char *value)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_PRINT_STRING_FRAGMENT);
    (void)runtime;
    qk_write_output_string(stdout, value);
}

void qk_print_number_fragment(qk_runtime *runtime, double value)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_PRINT_NUMBER_FRAGMENT);
    qk_write_output_number(runtime, stdout, value);
}

void qk_print_output_separator(qk_runtime *runtime)
{
    qk_write_output_separator(runtime, stdout);
}

void qk_print_output_record_separator(qk_runtime *runtime)
{
    qk_write_output_record_separator(runtime, stdout);
}

double qk_getline_main_record(qk_runtime *runtime)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GETLINE_MAIN_RECORD);
    return qk_read_main_line(runtime, true, NULL);
}

double qk_getline_main_string(qk_runtime *runtime, const char **result_out)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GETLINE_MAIN_STRING);
    return qk_read_main_line(runtime, false, result_out);
}

double qk_getline_file_record(qk_runtime *runtime, const char *target)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GETLINE_FILE_RECORD);
    return qk_read_file_line(runtime, target, true, NULL);
}

double qk_getline_file_string(qk_runtime *runtime, const char *target, const char **result_out)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GETLINE_FILE_STRING);
    return qk_read_file_line(runtime, target, false, result_out);
}

void qk_nextfile(qk_runtime *runtime)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_NEXTFILE);
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
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_SCALAR_GET);
    struct qk_scalar_entry *entry = qk_find_scalar(runtime, name, false);
    return qk_scalar_string_view(runtime, entry);
}

double qk_scalar_get_number(qk_runtime *runtime, const char *name)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_SCALAR_GET_NUMBER);
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
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_SCALAR_TRUTHY);
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
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_SCALAR_SET_STRING);
    if ((runtime == NULL) || (name == NULL)) {
        return;
    }
    if (!qk_scalar_set_string_value(runtime, name, value)) {
        return;
    }
    (void)qk_apply_scalar_side_effects(runtime, name);
}

void qk_scalar_set_number(qk_runtime *runtime, const char *name, double value)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_SCALAR_SET_NUMBER);
    if ((runtime == NULL) || (name == NULL)) {
        return;
    }
    if (!qk_scalar_set_number_value(runtime, name, value)) {
        return;
    }
    (void)qk_apply_scalar_side_effects(runtime, name);
}

void qk_scalar_copy(qk_runtime *runtime, const char *target_name, const char *source_name)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_SCALAR_COPY);
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
        (void)qk_apply_scalar_side_effects(runtime, target_name);
        return;
    }
    if (source->kind == QK_SCALAR_STRING) {
        (void)qk_scalar_set_string_value(runtime, target_name, source->string);
        (void)qk_apply_scalar_side_effects(runtime, target_name);
        return;
    }
    qk_clear_scalar(target);
}

bool qk_compare_values(
    const char *left_string,
    double left_number,
    bool left_needs_numeric_check,
    bool left_force_string,
    const char *right_string,
    double right_number,
    bool right_needs_numeric_check,
    bool right_force_string,
    int32_t op
)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_COMPARE_VALUES);
    bool left_numeric;
    bool right_numeric;

    if (left_force_string || right_force_string) {
        return qk_compare_strings(left_string, right_string, op);
    }

    left_numeric = !left_needs_numeric_check || qk_is_full_numeric_string(left_string);
    right_numeric = !right_needs_numeric_check || qk_is_full_numeric_string(right_string);
    if (left_numeric && right_numeric) {
        return qk_compare_numbers(left_number, right_number, op);
    }
    return qk_compare_strings(left_string, right_string, op);
}

const char *qk_capture_string_arg(qk_runtime *runtime, const char *text)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_CAPTURE_STRING_ARG);
    char *copy;
    char **next_strings;

    if (runtime == NULL) {
        return QK_EMPTY_FIELD;
    }

    copy = qk_strdup_or_null(text == NULL ? "" : text);
    if (copy == NULL) {
        return QK_EMPTY_FIELD;
    }

    if (runtime->temp_string_count == runtime->temp_string_capacity) {
        size_t next_capacity = runtime->temp_string_capacity == 0U ? 8U : runtime->temp_string_capacity * 2U;
        next_strings = realloc(runtime->temp_strings, next_capacity * sizeof(*next_strings));
        if (next_strings == NULL) {
            free(copy);
            return QK_EMPTY_FIELD;
        }
        runtime->temp_strings = next_strings;
        runtime->temp_string_capacity = next_capacity;
    }

    runtime->temp_strings[runtime->temp_string_count] = copy;
    runtime->temp_string_count += 1U;
    return copy;
}

double qk_parse_number_text(const char *text)
{
    return qk_parse_awk_numeric_prefix(text);
}

const char *qk_format_number(qk_runtime *runtime, double value)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_FORMAT_NUMBER);
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

double qk_index(qk_runtime *runtime, const char *text, const char *search)
{
    const char *match;

    (void)runtime;
    if ((text == NULL) || (search == NULL)) {
        return 0.0;
    }
    if (*search == '\0') {
        return 1.0;
    }

    match = strstr(text, search);
    if (match == NULL) {
        return 0.0;
    }
    return (double)((match - text) + 1);
}

double qk_match(qk_runtime *runtime, const char *text, const char *pattern)
{
    regex_t regex;
    regmatch_t match;
    int result;

    if (runtime == NULL) {
        return 0.0;
    }

    (void)qk_scalar_set_number_value(runtime, "RSTART", 0.0);
    (void)qk_scalar_set_number_value(runtime, "RLENGTH", -1.0);
    if ((text == NULL) || (pattern == NULL)) {
        return 0.0;
    }
    if (regcomp(&regex, pattern, REG_EXTENDED) != 0) {
        return 0.0;
    }

    result = regexec(&regex, text, 1, &match, 0);
    regfree(&regex);
    if (result != 0) {
        return 0.0;
    }

    (void)qk_scalar_set_number_value(runtime, "RSTART", (double)(match.rm_so + 1));
    (void)qk_scalar_set_number_value(runtime, "RLENGTH", (double)(match.rm_eo - match.rm_so));
    return (double)(match.rm_so + 1);
}

static bool qk_append_substitute_replacement(
    qk_runtime *runtime,
    size_t *offset,
    const char *replacement,
    const char *match_start,
    size_t match_length
)
{
    size_t index = 0U;

    while ((replacement != NULL) && (replacement[index] != '\0')) {
        char current = replacement[index];
        if (current == '&') {
            if (!qk_append_scratch(runtime, offset, match_start, match_length)) {
                return false;
            }
            index += 1U;
            continue;
        }
        if (current == '\\') {
            char escaped = replacement[index + 1U];
            if (escaped == '&' || escaped == '\\') {
                if (!qk_append_char_scratch(runtime, offset, escaped)) {
                    return false;
                }
                index += 2U;
                continue;
            }
        }
        if (!qk_append_char_scratch(runtime, offset, current)) {
            return false;
        }
        index += 1U;
    }
    return true;
}

double qk_substitute(
    qk_runtime *runtime,
    const char *pattern,
    const char *replacement,
    const char *text,
    bool global,
    const char **result_out
)
{
    regex_t regex;
    regmatch_t match;
    int result;
    double count = 0.0;
    size_t offset = 0U;
    const char *cursor;

    if (result_out != NULL) {
        *result_out = QK_EMPTY_FIELD;
    }
    if (runtime == NULL) {
        return 0.0;
    }
    if ((pattern == NULL) || (replacement == NULL) || (text == NULL)) {
        return 0.0;
    }
    if (regcomp(&regex, pattern, REG_EXTENDED) != 0) {
        return 0.0;
    }

    cursor = text;
    if (!qk_store_scratch(runtime, "", 0U)) {
        regfree(&regex);
        return 0.0;
    }

    while ((result = regexec(&regex, cursor, 1, &match, 0)) == 0) {
        size_t match_start = (size_t)match.rm_so;
        size_t match_length = (size_t)(match.rm_eo - match.rm_so);

        if (!qk_append_scratch(runtime, &offset, cursor, match_start)) {
            regfree(&regex);
            return 0.0;
        }
        if (!qk_append_substitute_replacement(runtime, &offset, replacement, cursor + match_start, match_length)) {
            regfree(&regex);
            return 0.0;
        }
        count += 1.0;

        if (!global) {
            cursor += match.rm_eo;
            break;
        }

        if (match.rm_so == match.rm_eo) {
            if (cursor[match.rm_eo] == '\0') {
                cursor += match.rm_eo;
                break;
            }
            if (!qk_append_char_scratch(runtime, &offset, cursor[match.rm_eo])) {
                regfree(&regex);
                return 0.0;
            }
            cursor += match.rm_eo + 1;
            continue;
        }

        cursor += match.rm_eo;
    }

    regfree(&regex);
    if (!qk_append_scratch(runtime, &offset, cursor, strlen(cursor))) {
        return 0.0;
    }
    if (result_out != NULL) {
        *result_out = runtime->scratch_buffer == NULL ? QK_EMPTY_FIELD : runtime->scratch_buffer;
    }
    return count;
}

static bool qk_append_sprintf_segment(
    qk_runtime *runtime,
    size_t *offset,
    const char *format_text,
    char specifier,
    double number_value,
    const char *string_value
)
{
    int required;
    size_t start;

    if ((runtime == NULL) || (offset == NULL) || (format_text == NULL)) {
        return false;
    }

    switch (specifier) {
    case 's':
        required = snprintf(NULL, 0, format_text, string_value == NULL ? "" : string_value);
        break;
    case 'd':
    case 'i':
    case 'o':
    case 'u':
    case 'x':
    case 'X':
    case 'c':
        required = snprintf(NULL, 0, format_text, (int)number_value);
        break;
    default:
        required = snprintf(NULL, 0, format_text, number_value);
        break;
    }
    if (required < 0) {
        return false;
    }

    start = *offset;
    if (!qk_reserve_scratch(runtime, start + (size_t)required)) {
        return false;
    }
    switch (specifier) {
    case 's':
        snprintf(runtime->scratch_buffer + start, (size_t)required + 1U, format_text, string_value == NULL ? "" : string_value);
        break;
    case 'd':
    case 'i':
    case 'o':
    case 'u':
    case 'x':
    case 'X':
    case 'c':
        snprintf(runtime->scratch_buffer + start, (size_t)required + 1U, format_text, (int)number_value);
        break;
    default:
        snprintf(runtime->scratch_buffer + start, (size_t)required + 1U, format_text, number_value);
        break;
    }
    *offset = start + (size_t)required;
    return true;
}

const char *qk_sprintf(
    qk_runtime *runtime,
    const char *format,
    int32_t argc,
    const double *numbers,
    const char *const *strings
)
{
    size_t index = 0U;
    size_t offset = 0U;
    int32_t arg_index = 0;

    if ((runtime == NULL) || (format == NULL)) {
        return QK_EMPTY_FIELD;
    }
    if (!qk_store_scratch(runtime, "", 0U)) {
        return QK_EMPTY_FIELD;
    }

    while (format[index] != '\0') {
        size_t start;
        size_t spec_length;
        char specifier;
        char *spec_text;

        if (format[index] != '%') {
            if (!qk_append_char_scratch(runtime, &offset, format[index])) {
                return QK_EMPTY_FIELD;
            }
            index += 1U;
            continue;
        }
        if (format[index + 1U] == '%') {
            if (!qk_append_char_scratch(runtime, &offset, '%')) {
                return QK_EMPTY_FIELD;
            }
            index += 2U;
            continue;
        }

        start = index;
        index += 1U;
        while (format[index] != '\0') {
            char current = format[index];
            if (strchr("aAcdeEfgGiosuxX", current) != NULL) {
                break;
            }
            index += 1U;
        }
        if (format[index] == '\0') {
            return QK_EMPTY_FIELD;
        }

        specifier = format[index];
        spec_length = index - start + 1U;
        spec_text = malloc(spec_length + 1U);
        if (spec_text == NULL) {
            return QK_EMPTY_FIELD;
        }
        memcpy(spec_text, format + start, spec_length);
        spec_text[spec_length] = '\0';

        if (arg_index >= argc) {
            free(spec_text);
            return QK_EMPTY_FIELD;
        }
        if (!qk_append_sprintf_segment(
                runtime,
                &offset,
                spec_text,
                specifier,
                numbers == NULL ? 0.0 : numbers[arg_index],
                strings == NULL ? QK_EMPTY_FIELD : strings[arg_index])) {
            free(spec_text);
            return QK_EMPTY_FIELD;
        }
        free(spec_text);
        arg_index += 1;
        index += 1U;
    }

    return runtime->scratch_buffer == NULL ? QK_EMPTY_FIELD : runtime->scratch_buffer;
}

const char *qk_tolower(qk_runtime *runtime, const char *text)
{
    size_t index;
    size_t length;

    if ((runtime == NULL) || (text == NULL)) {
        return QK_EMPTY_FIELD;
    }
    length = strlen(text);
    if (!qk_store_scratch(runtime, text, length)) {
        return QK_EMPTY_FIELD;
    }
    for (index = 0U; index < length; index += 1U) {
        runtime->scratch_buffer[index] = (char)tolower((unsigned char)runtime->scratch_buffer[index]);
    }
    return runtime->scratch_buffer;
}

const char *qk_toupper(qk_runtime *runtime, const char *text)
{
    size_t index;
    size_t length;

    if ((runtime == NULL) || (text == NULL)) {
        return QK_EMPTY_FIELD;
    }
    length = strlen(text);
    if (!qk_store_scratch(runtime, text, length)) {
        return QK_EMPTY_FIELD;
    }
    for (index = 0U; index < length; index += 1U) {
        runtime->scratch_buffer[index] = (char)toupper((unsigned char)runtime->scratch_buffer[index]);
    }
    return runtime->scratch_buffer;
}

double qk_atan2(double left, double right)
{
    return atan2(left, right);
}

double qk_cos(double value)
{
    return cos(value);
}

double qk_exp(double value)
{
    return exp(value);
}

double qk_int_builtin(double value)
{
    return trunc(value);
}

double qk_log(double value)
{
    return log(value);
}

double qk_rand(qk_runtime *runtime)
{
    if (runtime == NULL) {
        return 0.0;
    }
    runtime->random_state = qk_next_rand_state(runtime->random_state);
    return ((double)runtime->random_state) / QK_RAND_MODULUS;
}

double qk_sin(double value)
{
    return sin(value);
}

double qk_sqrt(double value)
{
    return sqrt(value);
}

double qk_srand0(qk_runtime *runtime)
{
    int64_t previous_seed;
    int64_t next_seed;

    if (runtime == NULL) {
        return 0.0;
    }

    previous_seed = runtime->random_seed;
    next_seed = (int64_t)time(NULL);
    runtime->random_seed = next_seed;
    runtime->random_state = qk_normalize_seed((double)next_seed);
    return (double)previous_seed;
}

double qk_srand1(qk_runtime *runtime, double seed)
{
    int64_t previous_seed;
    int64_t next_seed;

    if (runtime == NULL) {
        return 0.0;
    }

    previous_seed = runtime->random_seed;
    next_seed = (int64_t)trunc(seed);
    runtime->random_seed = next_seed;
    runtime->random_state = qk_normalize_seed(seed);
    return (double)previous_seed;
}

double qk_system(qk_runtime *runtime, const char *command)
{
    int status;

    (void)runtime;
    if (command == NULL) {
        return -1.0;
    }

    status = system(command);
    if (status < 0) {
        return -1.0;
    }
    if (WIFEXITED(status)) {
        return (double)WEXITSTATUS(status);
    }
    return (double)status;
}

bool qk_regex_match_current_record(qk_runtime *runtime, const char *pattern)
{
    if ((runtime == NULL) || (runtime->current_record == NULL)) {
        return false;
    }
    return qk_regex_match_text_impl(runtime->current_record, pattern);
}

bool qk_regex_match_text(const char *text, const char *pattern)
{
    return qk_regex_match_text_impl(text, pattern);
}

double qk_get_nr(qk_runtime *runtime)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GET_NR);
    return runtime == NULL ? 0.0 : runtime->nr;
}

double qk_get_fnr(qk_runtime *runtime)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GET_FNR);
    return runtime == NULL ? 0.0 : runtime->fnr;
}

double qk_get_nf(qk_runtime *runtime)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GET_NF);
    return runtime == NULL ? 0.0 : (double)runtime->field_count;
}

const char *qk_get_filename(qk_runtime *runtime)
{
    qk_runtime_profile_note(QK_RUNTIME_PROFILE_GET_FILENAME);
    if ((runtime == NULL) || (runtime->current_filename == NULL)) {
        return "-";
    }
    return runtime->current_filename;
}

double qk_split_into_array(qk_runtime *runtime, const char *text, const char *array_name, const char *separator)
{
    regex_t regex;
    regmatch_t match;
    int regex_result;

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
    if (separator == NULL) {
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
        const char *cursor = text;
        if (*separator == '\0') {
            (void)qk_array_set(runtime, array_name, "1", text);
            free(buffer);
            return 1.0;
        }

        if (regcomp(&regex, separator, REG_EXTENDED) != 0) {
            free(buffer);
            return 0.0;
        }

        while ((regex_result = regexec(&regex, cursor, 1, &match, 0)) == 0) {
            count += 1U;
            char key[32];
            snprintf(key, sizeof(key), "%zu", count);

            if (!qk_store_scratch(runtime, cursor, (size_t)match.rm_so)) {
                regfree(&regex);
                free(buffer);
                return 0.0;
            }
            if (!qk_array_set(runtime, array_name, key, runtime->scratch_buffer)) {
                regfree(&regex);
                free(buffer);
                return 0.0;
            }

            if (match.rm_so == match.rm_eo) {
                if (cursor[match.rm_eo] == '\0') {
                    cursor += match.rm_eo;
                    break;
                }
                cursor += match.rm_eo + 1;
                continue;
            }
            cursor += match.rm_eo;
        }

        if ((regex_result != 0) && (regex_result != REG_NOMATCH)) {
            regfree(&regex);
            free(buffer);
            return 0.0;
        }

        count += 1U;
        char key[32];
        snprintf(key, sizeof(key), "%zu", count);
        if (!qk_array_set(runtime, array_name, key, cursor)) {
            regfree(&regex);
            free(buffer);
            return 0.0;
        }
        regfree(&regex);
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

bool qk_array_contains(qk_runtime *runtime, const char *array_name, const char *key)
{
    struct qk_array *array;
    struct qk_array_entry *entry;

    if ((runtime == NULL) || (array_name == NULL) || (key == NULL)) {
        return false;
    }

    array = qk_find_array(runtime, array_name, false);
    if (array == NULL) {
        return false;
    }

    entry = array->entries;
    while (entry != NULL) {
        if (strcmp(entry->key, key) == 0) {
            return true;
        }
        entry = entry->next;
    }
    return false;
}

void qk_array_set_string(qk_runtime *runtime, const char *array_name, const char *key, const char *value)
{
    if ((runtime == NULL) || (array_name == NULL) || (key == NULL)) {
        return;
    }
    (void)qk_array_set(runtime, array_name, key, value == NULL ? "" : value);
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
