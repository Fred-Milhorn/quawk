# AWK Execution and JIT Caching Strategy (High-Level)

This document defines execution behavior for a realtime AWK front end (parse + JIT on demand) with optional caching of compiled artifacts.

Scope:
- runtime execution path
- cache lookup/store behavior
- cache key and invalidation rules
- failure and fallback behavior

Out of scope:
- concrete Python module APIs
- low-level LLVM JIT wiring details
- storage implementation specifics

## Goals

- Keep first execution responsive with realtime parse/JIT.
- Reuse prior compilation work aggressively across invocations.
- Preserve correctness by invalidating cached artifacts whenever semantics or target environment can differ.
- Fail safely: cache failures must not prevent program execution.

## Execution Model

The runtime uses a two-tier cache with a guaranteed realtime fallback:

1. Tier 1: process-local memory cache.
2. Tier 2: persistent disk cache.
3. Fallback: compile now (parse -> lower -> JIT) and execute.

## Runtime State Machine

1. `LoadInput`
2. `NormalizeSource`
- normalize line endings and canonicalize input identity for hashing
3. `ComputeCacheKey`
4. `MemoryLookup`
- hit: load executable handle and run
- miss: continue
5. `DiskLookup`
- hit: validate metadata, load compiled artifact into JIT, run
- miss: continue
6. `CompileRealtime`
- lex/parse, semantic checks, IR generation, optimization, code emission/JIT materialization
7. `Execute`
8. `StoreCache`
- write to memory cache immediately
- write to disk cache best-effort (sync or async policy)

Any failure in lookup/load/store transitions to `CompileRealtime` or continues execution without cache persistence.

## Cache Key Schema

Cache key must include all inputs that can change generated machine code or runtime behavior.

Required fields:
- `source_hash`: hash of normalized AWK source text
- `frontend_version`: parser/semantic pipeline version
- `awk_mode`: POSIX mode and language feature toggles
- `runtime_abi_version`: internal runtime/data-layout version
- `llvm_version`: LLVM version used by `llvmlite`
- `target_triple`: architecture-vendor-os
- `target_cpu`: selected CPU model
- `target_features`: CPU feature set (for example SIMD flags)
- `opt_level`: codegen optimization level

Optional fields:
- `stdlib_profile`: selected builtin/runtime profile
- `jit_policy`: options that alter emission or relocation behavior

Recommendation:
- define a canonical serialized key payload and hash that payload for directory/file naming

## Cache Artifacts

Recommended primary disk artifact:
- native object file + metadata sidecar

Optional secondary artifact:
- LLVM bitcode for debugging or cross-target workflows

Metadata sidecar should include:
- full unhashed key payload
- creation timestamp
- artifact format version
- optional integrity hash for artifact bytes

## Lookup and Validation Rules

- memory cache lookup uses exact key match
- disk lookup requires:
  - exact key match
  - metadata/artifact format compatibility
  - integrity check pass (if enabled)
- if validation fails, treat as miss and continue to realtime compile

## Store Policy

- memory cache:
  - insert on successful compile or successful disk load
  - bounded by LRU or size cap
- disk cache:
  - best-effort write after successful compile
  - bounded by size and/or entry count
  - eviction policy: LRU preferred

Suggested default behavior:
- synchronous memory insert
- asynchronous disk write when latency-sensitive

## Failure Behavior

Rules:
- cache read failure: log and continue as miss
- cache write failure: log and continue; do not fail execution
- artifact load/link failure: invalidate entry and fallback to realtime compile
- compile/JIT failure: report deterministic compile/runtime error and exit non-zero

Design principle:
- cache is a performance layer, never a correctness dependency

## Concurrency and Process Safety

- memory cache is process-local; guard with runtime locks if multithreaded
- disk cache should use atomic writes:
  - write temp file
  - fsync as needed
  - atomic rename into final key path
- for concurrent processes, allow duplicate compilation; correctness over dedup complexity

## Observability

Track at minimum:
- memory cache hit/miss counts
- disk cache hit/miss counts
- compile duration
- load/link duration
- cache write failures

Expose a compact execution summary for profiling startup behavior.

## Default Policy Profile

- realtime compile enabled always
- memory cache enabled, bounded LRU
- disk cache enabled, best-effort writes
- exact key matching, strict invalidation
- fallback-to-compile on all cache-layer failures

## Acceptance Scenarios

- first run with empty cache compiles and executes successfully
- second run with same source/options hits disk or memory cache and reduces startup time
- changing source invalidates prior cache entry
- changing LLVM version or target features invalidates prior cache entry
- corrupt cache artifact is ignored and rebuilt automatically
- disk cache unavailable still permits successful realtime execution
