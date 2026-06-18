# Contributing

Thanks for your interest in improving the Family Financial Advisor. This is a privacy-first, educational tool — contributions that make it clearer, safer, or more genuinely helpful to families are very welcome.

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2) — the recommended path; runs the whole stack.
- An **Anthropic API key** — the advisor calls the Claude API.
- For running outside Docker: **Python 3.12+** and **Node 22.12+** (the frontend uses Vite 8, which requires Node 22.12 or newer).

## Local setup

The whole stack runs in Docker, so Docker is the only hard requirement.

```bash
# 1. Clone the repo, then add your Anthropic key
cp .env.example .env
#    edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# 2. Build and run both services
docker compose up --build

# 3. Open the app
#    frontend → http://localhost:5173
#    backend  → http://localhost:8000   (health: /health)
```

Source is bind-mounted, so editing a `.py` in `backend/` or a file in `frontend/src/` reloads live — no rebuild needed. After changing `requirements.txt` or `frontend/package.json`, re-run with `docker compose up --build` to refresh the dependency layer.

Prefer running without Docker? See the "Notes for contributors" in the [README](README.md#installation).

## Privacy rule (important)

**Never put real financial data in tests, examples, fixtures, or documentation.** Always use fictional families and made-up numbers. This is a tool people trust with sensitive household finances; our own repo must model that discipline.

## Branch naming

Use a type prefix matching the change:

- `feat/` — new functionality
- `fix/` — bug fixes
- `docs/` — documentation only
- `chore/` — tooling, deps, housekeeping

Example: `feat/monte-carlo-glide-path`.

## Commit format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.

## Changelog duty

Every user-facing change adds a line to the `[Unreleased]` section of [CHANGELOG.md](CHANGELOG.md), under the appropriate heading (`Added`, `Changed`, `Fixed`, `Security`, etc.). Internal-only refactors don't need an entry.

## Pull request process

1. Open a PR against `main` describing the change and your testing.
2. Make sure the privacy rule holds — no real financial data anywhere.
3. Add your changelog line.
4. A maintainer reviews; address feedback.
5. PRs are squash-merged to keep history clean.

## Tests

```bash
# Backend (from repo root)
pytest

# Frontend lint
cd frontend && npm run lint
```

Please add or update tests for behavior you change.
