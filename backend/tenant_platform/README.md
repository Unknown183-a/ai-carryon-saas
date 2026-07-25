# Why this folder is `tenant_platform/`, not `platform/`

The phase briefs and SAD (`../../phases/phase-06-multi-tenancy-channel-factory/PHASE.md`,
Ch.12b–12e) refer to this folder as `backend/platform/` — that's still what it's *called*
conceptually. It's on disk as `tenant_platform/` instead because `platform` is a Python
standard library module name (`platform.system()`, `platform.python_version()`, etc.,
used internally by several dependencies this project already has — httpx and uvicorn
among them).

This codebase's established convention (every prior phase) puts `backend/` itself
directly on `sys.path` and imports everything as top-level packages — `from ai.agents...`,
`from app.core...`, `from integrations.gemini...`. Under that same convention, a
directory literally named `backend/platform/` with an `__init__.py` becomes an
importable top-level package named `platform` — which **shadows the real stdlib
module for the rest of the process**, breaking anything downstream that does a plain
`import platform` expecting the real thing. This was verified directly, not assumed —
adding `backend/platform/__init__.py` and running `import platform; platform.system()`
with `backend/` on `sys.path` throws `AttributeError: module 'platform' has no
attribute 'system'` because Python resolves the name to this folder instead of the
stdlib module.

Renaming to `tenant_platform` is a one-word, zero-semantic-change fix — the module
content, structure, and everything the phase brief asks for is otherwise exactly as
specified. Import paths throughout this codebase use `tenant_platform.channels.brain`,
`tenant_platform.factory.factory`, `tenant_platform.security.permissions`, etc.
instead of the `platform.*` form the brief's prose uses.
