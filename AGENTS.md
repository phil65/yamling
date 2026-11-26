# AGENTS.md

## Overview

Serialization stuff for config files (PyPI `configz`; the GitHub repo is `phil65/yamling`).

## Commands

```bash
uv sync --all-extras          # setup
uv run pytest                 # tests
uv run ruff check . && uv run ruff format --check .
uv run ty check               # type check (warnings fail too)
uv run mknodes build          # docs (README + auto-generated pages)
uv build
```

## Specs

Protocols / APIs this project implements (keep the Targets column up to date when touching
protocol code). Write "unpinned (tracks latest)" if no version is targeted.

| Spec | URL | Targets | Code | Update check |
|---|---|---|---|---|
