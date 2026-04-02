/*
 * Streaming runtime support API for record-driven AWK execution.
 *
 * The compiler lowers reusable BEGIN/record/END program code against this ABI.
 * The runtime owns input iteration, field access, regex matching, and printing
 * so compiled IR does not have to specialize to a concrete input stream.
 */

#ifndef QUAWK_RUNTIME_QK_RUNTIME_H
#define QUAWK_RUNTIME_QK_RUNTIME_H

#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>

typedef struct qk_runtime qk_runtime;

/*
 * Create a runtime over the given input-file operands and optional field
 * separator. `argv` is the ordered list of AWK input operands, not the full
 * process argument vector.
 */
qk_runtime *qk_runtime_create(int argc, char **argv, const char *field_separator);

/* Destroy one runtime instance and release all owned buffers and file handles. */
void qk_runtime_destroy(qk_runtime *runtime);

/*
 * Advance to the next logical input record.
 *
 * Returns true when a new current record is available and false on clean EOF or
 * an input/open failure. The runtime keeps the current record and field state
 * available to subsequent field and regex queries until the next call.
 */
bool qk_next_record(qk_runtime *runtime);

/* Return `$0` for index 0 or `$n` for positive 1-based field indexes. */
const char *qk_get_field(qk_runtime *runtime, int64_t index);
void qk_set_field_string(qk_runtime *runtime, int64_t index, const char *value);
void qk_set_field_number(qk_runtime *runtime, int64_t index, double value);

/* Print a string or number using the same newline-terminated formatting as AWK print. */
void qk_print_string(qk_runtime *runtime, const char *value);
void qk_print_number(qk_runtime *runtime, double value);
void qk_print_string_fragment(qk_runtime *runtime, const char *value);
void qk_print_number_fragment(qk_runtime *runtime, double value);
void qk_print_output_separator(qk_runtime *runtime);
void qk_print_output_record_separator(qk_runtime *runtime);
FILE *qk_open_output(qk_runtime *runtime, const char *target, int32_t mode);
double qk_close_output(qk_runtime *runtime, const char *target);
void qk_write_output_string(FILE *handle, const char *value);
void qk_write_output_number(qk_runtime *runtime, FILE *handle, double value);
void qk_write_output_separator(qk_runtime *runtime, FILE *handle);
void qk_write_output_record_separator(qk_runtime *runtime, FILE *handle);

/* Record-control support for the reusable backend/runtime path. */
void qk_nextfile(qk_runtime *runtime);
void qk_request_exit(qk_runtime *runtime, int32_t status);
bool qk_should_exit(qk_runtime *runtime);
int32_t qk_exit_status(qk_runtime *runtime);

/* Match one regular expression pattern against the current record text. */
bool qk_regex_match_current_record(qk_runtime *runtime, const char *pattern);

/* Builtin-variable and builtin-function support for backend parity. */
const char *qk_scalar_get(qk_runtime *runtime, const char *name);
double qk_scalar_get_number(qk_runtime *runtime, const char *name);
bool qk_scalar_truthy(qk_runtime *runtime, const char *name);
void qk_scalar_set_string(qk_runtime *runtime, const char *name, const char *value);
void qk_scalar_set_number(qk_runtime *runtime, const char *name, double value);
void qk_scalar_copy(qk_runtime *runtime, const char *target_name, const char *source_name);
const char *qk_format_number(qk_runtime *runtime, double value);
const char *qk_concat(qk_runtime *runtime, const char *left, const char *right);
double qk_get_nr(qk_runtime *runtime);
double qk_get_fnr(qk_runtime *runtime);
double qk_get_nf(qk_runtime *runtime);
const char *qk_get_filename(qk_runtime *runtime);
double qk_split_into_array(qk_runtime *runtime, const char *text, const char *array_name, const char *separator);
const char *qk_array_get(qk_runtime *runtime, const char *array_name, const char *key);
void qk_array_set_number(qk_runtime *runtime, const char *array_name, const char *key, double value);
void qk_array_delete(qk_runtime *runtime, const char *array_name, const char *key);
void qk_array_clear(qk_runtime *runtime, const char *array_name);
double qk_array_length(qk_runtime *runtime, const char *array_name);
const char *qk_array_first_key(qk_runtime *runtime, const char *array_name);
const char *qk_array_next_key(qk_runtime *runtime, const char *array_name, const char *current_key);
const char *qk_substr2(qk_runtime *runtime, const char *text, int64_t start);
const char *qk_substr3(qk_runtime *runtime, const char *text, int64_t start, int64_t length);

#endif
