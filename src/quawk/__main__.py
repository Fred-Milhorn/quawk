# Command-line module entrypoint.
# Keeps `python -m quawk` aligned with the installed `quawk` console script.

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
