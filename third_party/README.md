# Upstream Sources

This directory holds pinned upstream source trees used for compatibility work.

Current submodules:

- `onetrueawk`
- `gawk`

Initialize them from a fresh checkout with:

```sh
git submodule update --init --recursive
```

Build local compatibility references with:

```sh
uv run python scripts/upstream_compat.py bootstrap
```

Policy:

- keep these trees pinned as Git submodules
- do not build inside the submodule directories directly
- keep local build outputs under ignored `build/` paths
- treat these sources as the compatibility reference inputs for `P11`
