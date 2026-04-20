from __future__ import annotations

from quawk import architecture_audit


def test_t156_architecture_audit_is_clean() -> None:
    assert architecture_audit.families_lacking_full_backend_support() == []
