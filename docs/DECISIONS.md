# Architecture Decision Records

Short ADR-style entries. Each records **context → decision → consequences**. Newest decisions are appended at the end.

---

## ADR-001 — Project generated from the cookiecutter template, flattened to the repo root

**Context.** The brief asks for the project to be generated from `gh:MagedSaeed/cookiecutter-django-react` (answers: `project_name=HealTrip`, `project_slug=healtrip`, everything else default). The template produces a `healtrip/` folder containing `backend/`, `frontend/`, compose files and CI.

**Decision.** Generate into a temporary directory and move the contents to the repository root. The first commit is the unmodified template output, so every later change shows up as a reviewable diff.

**Consequences.** Reviewers see `backend/`, `frontend/`, `docs/` and `README.md` straight away. GitHub Actions only discovers workflows at the repo root (`.github/workflows`), so this layout is also needed for CI to run.

## ADR-002 — PostgreSQL in every environment (no SQLite fallback)

**Context.** The template uses SQLite for development and Postgres for production. The brief requires PostgreSQL.

**Decision.** `DATABASE_URL` drives `DATABASES` in all settings modules, with a local Postgres URL as the default. Doctor `languages` uses the Postgres `ArrayField`. Tests run on Postgres locally and in CI (via a service container).

**Consequences.** Dev, test and prod behave the same. The development machine has no Docker, so local development uses the official **portable PostgreSQL 16 Windows binaries** in `.local/` (gitignored). `docker compose up` remains the documented one-command path.

## ADR-003 — Template bug fixes made during setup

**Context.** As generated, the template's `docker-compose.yml` used `build: ./backend`, but `backend/Dockerfile` copies `backend/...` paths, which assumes the repo root as build context (the context Railway uses). The CI `docker build ./backend` step had the same mismatch, and the template's generated migration failed its own `ruff format --check`.

**Decision.** Use `context: .` with `dockerfile: backend/Dockerfile` (and the same for the frontend) in both compose files and CI. Exclude `*/migrations/*` from ruff, since they are generated code. Add `.gitattributes` so shell scripts stay LF when committed from Windows (the nginx entrypoint would otherwise fail in Linux containers). The dev compose mounts an anonymous volume at `/app/.venv` so the host checkout doesn't hide the container's virtualenv.

**Consequences.** `docker compose up`, the Railway build and the CI image build all use one consistent build context.

## ADR-004 — `AgentRunLog` is a separate table from `ToolCallLog`

**Context.** The brief allowed folding per-turn metrics into `ToolCallLog`.

**Decision.** Keep a separate `AgentRunLog` with one row per assistant turn. `ToolCallLog` gets a nullable FK to it.

**Consequences.** A turn can have zero tool calls (the emergency short-circuit, or a pure clarifying question) or several. Putting turn metrics on tool rows would either duplicate them or lose the zero-tool turns. With the split, "urgency provenance" and "grounding violations per turn" become simple queries, which also makes the admin a useful audit view.

## ADR-005 — Closed enums for city and specialty, shared by DB and tool schemas

**Decision.** `providers/choices.py` defines `City` and `SpecialtyCode` once. The model field choices, the seed data and the Pydantic tool-input schemas all import them.

**Consequences.** The JSON schema the LLM sees lists the only valid values, and Pydantic rejects anything else before the query runs. Adding a city is a code change plus a migration, which is acceptable for a prototype. A production system would load the vocabulary from the DB at startup.
