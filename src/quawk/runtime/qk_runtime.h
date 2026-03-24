/*
 * Streaming runtime support API for record-driven AWK execution.
 *
 * The compiler lowers reusable BEGIN/record/END program code against this ABI.
 * The runtime owns input iteration, field access, regex matching, and printing
 * so compiled IR does not have to specialize to a concrete input stream.
 */

#ifndef QUAWK_RUNTIME_QK_RUNTIME_H
#define QUAWK_RUNTIME_QK_RUNTIME_H

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

/* Print a string or number using the same newline-terminated formatting as AWK print. */
void qk_print_string(qk_runtime *runtime, const char *value);
void qk_print_number(qk_runtime *runtime, double value);

/* Match one regular expression pattern against the current record text. */
bool qk_regex_match_current_record(qk_runtime *runtime, const char *pattern);

#endif
