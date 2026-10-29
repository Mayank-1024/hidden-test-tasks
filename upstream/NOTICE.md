# Vendored upstream: jmespath.py 1.1.0

`upstream/jmespath/` is an unmodified snapshot of the JMESPath Python library.
Every task starts from this tree.

| | |
|---|---|
| Project | jmespath.py, https://github.com/jmespath/jmespath.py |
| Version | tag `1.1.0` (released 2026-01-22) |
| Commit | `6ff419a8b171d055a9bfc6904605bceb8b7a80ef` |
| License | MIT, Copyright (c) 2013 Amazon.com, Inc. or its affiliates. See `jmespath/LICENSE`. |
| Copied | `jmespath/` (the package), `tests/`, `LICENSE`, `README.rst`, `CHANGELOG.rst`, `setup.py`, `setup.cfg` |
| Left out | `bin/`, `extra/` (hypothesis fuzzing), `perf/`, `scripts/`, CI and packaging files |

No file in the snapshot has been edited. Ruff is configured to skip this
directory so the code stays byte-for-byte identical to the upstream tag.

## Why this library

- **Permissive license** (MIT) and no runtime dependencies or native code, so
  the environment is CPython plus pytest.
- **Small but real.** About 1,700 lines across a lexer, a Pratt parser, an AST
  module, a tree-walking interpreter and a typed function registry. A task can
  require changes across several layers while a solver can still read the
  whole package.
- **A strong existing suite.** 992 tests (991 pass, 1 skipped on CPython
  3.13), most of them generated from the language's JSON compliance files.
  That suite is the "visible" suite the solver can run, and every task must
  keep it green.
- **A written spec.** JMESPath has a grammar and a specification, so task
  statements can be precise and hidden tests can be checked against stated
  behavior rather than one implementation's quirks.
