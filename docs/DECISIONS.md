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

## ADR-006 — Tool results are ID-based; only `search_providers` IDs are recommendable

**Context.** The model has to point at real providers without fabricating details, and a guessed ID must not become a "recommendation".

**Decision.**
1. `search_providers` returns **IDs and structured facts only** (`provider_id`, `hospital_id`, specialty codes, city, languages, flags, next slot). It returns no names, phones or fees, so the model has nothing to paraphrase wrongly. The UI renders those from the DB.
2. The grounding whitelist is the set of doctor IDs returned by **`search_providers`** calls in the current session, including `nearby_alternatives`. IDs seen only through `get_provider_details` or `check_availability` don't count. This closes a "laundering" hole where the model guesses an ID, fetches its details, and then recommends a real provider that was never matched against the patient's criteria.

**Consequences.** Recommendations always trace back to a logged search whose filters (specialty, city, language, second opinion) are visible in the trace. `get_provider_details` stays available for extra facts, such as accreditation.

## ADR-007 — Tools never raise; failures are structured tool results

**Decision.** `registry.execute()` catches validation errors, unknown tool names and `DatabaseError`, and returns `{"error": {"code", "message", ...}}`. The agent loop passes that result back to the model as a `tool_result` with `is_error: true`.

**Consequences.** The model can self-correct invalid arguments, which is the usual cause. A DB outage degrades one tool call instead of crashing the request. Every failure is still logged to `ToolCallLog` with its error code.

## ADR-008 — Official `anthropic` SDK with a hand-written loop (no LangChain, no SDK tool runner)

**Decision.** `assistant/llm/client.py` calls the Messages API directly with native tool use. `assistant/agent/loop.py` is about 100 lines.

**Why.**
- *Transparency.* Every branch of the loop is a safety control: the iteration cap, the single repair per failure kind, grounding before accepting, and `submit_response` having to be called alone. These need to be visible in one file and easy to explain line by line.
- *Testability.* The loop depends on a three-method `LLMClient` protocol, so `MockLLMClient` scripts drive every failure path in CI without network access.
- *Fewer abstractions.* LangChain would add agent and memory abstractions and version churn that we'd need to work around to enforce these rules. The SDK's beta tool runner hides the exact points where we validate and correct.

## ADR-009 — The final answer is a `submit_response` tool call validated by Pydantic

**Context.** We need schema-constrained output for the turn result (urgency, next step, IDs, questions, state updates). Current Claude models reject forced `tool_choice` (`any`/`tool`).

**Decision.** `AgentResponse` generates the `submit_response` input schema. `tool_choice` is `auto` and the prompt requires finishing with `submit_response`, called alone. The loop enforces the rest:
- A prose answer gets one correction.
- `submit_response` called alongside other tools is rejected, because the model answered without seeing the results.
- A schema violation gets one repair, then the safe fallback.
- Cross-field rules (`NEED_MORE_INFO` needs questions; `EMERGENCY` needs `CALL_EMERGENCY` or `GO_TO_ER`) are model validators.

## ADR-010 — PII is redacted before storage and before the LLM

**Decision.** `orchestrator.sanitize()` strips control and bidi-override characters (a prompt-smuggling vector) and redacts emails, phone numbers, Saudi ID/Iqama-like numbers and long digit runs *before* the message is stored or sent to the LLM.

**Consequences.** The LLM provider never receives identifiers the patient pasted by mistake. The navigation task needs none of them; city is the most specific location we use.

## ADR-011 — Model and request settings

**Decision.**
- `LLM_MODEL` defaults to **`claude-sonnet-5-5`**, the current Sonnet, as the brief asked for a current Sonnet model. It is configurable.
- `output_config.effort` defaults to `medium`. This is a conversational task, and effort is tunable through `LLM_EFFORT`.
- Thinking is left at the model default (adaptive).
- The static system prompt carries `cache_control`, so the system prompt and tools are cached across turns. Per-session facts go in a `<session_context>` block in the user turn, so the cached prefix never changes.
- **Server-side refusal fallback** (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) is on by default: if the primary model declines on a safety classifier (possible with medical wording), the API re-runs the request on a fallback model within the same call. Set `LLM_REFUSAL_FALLBACK=False` to disable it. A refusal that still gets through becomes the safe fallback response.
- SDK retries are disabled (`max_retries=0`) and `tenacity` owns the retry policy: exponential backoff on timeouts, connection errors, 429 and 5xx only. A 4xx fails fast.

**History.** Each turn rebuilds the conversation from stored text (the last 12 messages plus the structured state). Within a turn the message list is append-only and assistant content is echoed back unchanged. After a server-side fallback, blocks from the declined attempt are dropped, as the API requires.
