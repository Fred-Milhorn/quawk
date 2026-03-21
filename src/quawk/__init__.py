# Package metadata and top-level exports.
# Keeps the version string and CLI entrypoint importable from one place.

__all__ = ["__version__", "main"]

__version__ = "0.1.0"

from .cli import main
