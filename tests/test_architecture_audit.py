from __future__ import annotations

from pathlib import Path

from quawk import architecture_audit


def test_architecture_audit_manifest_matches_checked_in_backend_state() -> None:
    entries = architecture_audit.load_architecture_audit_manifest()

    assert architecture_audit.manifest_mismatches(entries) == []


def test_families_lacking_full_backend_support_match_checked_in_baseline() -> None:
    entries = architecture_audit.load_architecture_audit_manifest()

    assert architecture_audit.families_lacking_full_backend_support(entries) == [
        "record-control-next",
        "control-flow-do-while",
        "control-flow-loop-break-continue",
        "expression-pattern-actions",
        "default-print-expression-patterns",
    ]


def test_observe_backend_support_reports_completed_backend_family() -> None:
    observed = architecture_audit.observe_backend_support(
        'BEGIN { n = split("a b", a); print n; print a[1]; print substr("hello", 2, 3) }'
    )

    assert observed.uses_host_runtime is False
    assert observed.supports_public_backend_execution is True
    assert observed.supports_ir_asm is True


def test_architecture_audit_manifest_reports_expectation_mismatch(tmp_path: Path) -> None:
    manifest_path = tmp_path / "audit.toml"
    manifest_path.write_text(
        """
[[case]]
family = "user-defined-functions"
spec_area = "demo"
program = '''
function f(x) { return x + 1 }
BEGIN { print f(2) }
'''
expected_uses_host_runtime = false
expected_supports_public_backend_execution = false
expected_supports_ir_asm = false

[[case]]
family = "record-control-next"
spec_area = "demo"
program = '''
/skip/ { next }
{ print $0 }
'''
expected_uses_host_runtime = true
expected_supports_public_backend_execution = false
expected_supports_ir_asm = false

[[case]]
family = "record-control-nextfile"
spec_area = "demo"
program = '''
/stop/ { nextfile }
{ print $0 }
'''
expected_uses_host_runtime = false
expected_supports_public_backend_execution = true
expected_supports_ir_asm = true

[[case]]
family = "record-control-exit"
spec_area = "demo"
program = '''
BEGIN { print "before"; exit 7 }
'''
expected_uses_host_runtime = false
expected_supports_public_backend_execution = true
expected_supports_ir_asm = true

[[case]]
family = "scalar-string-coercions"
spec_area = "demo"
program = '''
BEGIN { x = "12"; print x + 1; print x "a" }
'''
expected_uses_host_runtime = false
expected_supports_public_backend_execution = true
expected_supports_ir_asm = true

[[case]]
family = "control-flow-do-while"
spec_area = "demo"
program = '''
BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }
'''
expected_uses_host_runtime = true
expected_supports_public_backend_execution = false
expected_supports_ir_asm = false

[[case]]
family = "control-flow-loop-break-continue"
spec_area = "demo"
program = '''
BEGIN {
    for (i = 0; i < 5; i = i + 1) {
        if (i == 2) {
            break
        } else {
            continue
        }
    }
}
'''
expected_uses_host_runtime = true
expected_supports_public_backend_execution = false
expected_supports_ir_asm = false

[[case]]
family = "expression-pattern-actions"
spec_area = "demo"
program = '''
1 { print $0 }
'''
expected_uses_host_runtime = false
expected_supports_public_backend_execution = false
expected_supports_ir_asm = false

[[case]]
family = "default-print-expression-patterns"
spec_area = "demo"
program = '''
1
'''
expected_uses_host_runtime = true
expected_supports_public_backend_execution = false
expected_supports_ir_asm = false
""".strip(),
        encoding="utf-8",
    )

    entries = architecture_audit.load_architecture_audit_manifest(path=manifest_path)
    mismatches = architecture_audit.manifest_mismatches(entries)

    assert mismatches == [
        "user-defined-functions: expected supports_public_backend_execution=False, observed True",
        "user-defined-functions: expected supports_ir_asm=False, observed True",
    ]
