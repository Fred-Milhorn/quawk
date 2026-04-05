"""Compatibility wrapper for the moved upstream execution module."""

from importlib import import_module as _import_module
import sys as _sys
from types import ModuleType as _ModuleType

_MODULE = _import_module("quawk.compat.upstream_suite")
_WRAPPER = _sys.modules[__name__]


class _CompatModuleProxy(_ModuleType):
    def __getattr__(self, name: str):
        return getattr(_MODULE, name)

    def __setattr__(self, name: str, value) -> None:
        setattr(_MODULE, name, value)
        super().__setattr__(name, value)


_WRAPPER.__class__ = _CompatModuleProxy
globals().update(_MODULE.__dict__)
