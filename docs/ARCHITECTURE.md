# Architecture

> **The LLM decides what to do. Deterministic code decides what is safe. The database decides what is true.**

## Components

```mermaid
flowchart LR
    subgraph Browser
        UI["React 19 + TS SPA<br/>i18n EN/AR · RTL/LTR<br/>Agent Trace panel"]
    end
    subgraph Edge["nginx (prod) / Vite proxy (dev)"]
        P["same-origin /api/*"]
    end
    subgraph Django["Django 6 + DRF"]
        API["Chat API<br/>ownership · CSRF · throttles<br/>bilingual error envelope"]
        ORC["Orchestrator<br/>assistant/agent/orchestrator.py"]
        RF["Red-Flag Engine<br/>(pure Python, EN+AR)"]
        LOOP["Agent Loop<br/>iteration cap · repairs"]
        REG["Tool Registry<br/>Pydantic-validated, read-only"]
        GV["Grounding Validator<br/>session-scoped ID whitelist"]
        SER["Card serializers<br/>(DB → UI)"]
        DIR["Directory API<br/>/api/providers /api/specialties"]
    end
    LLM[("Anthropic Messages API<br/>claude-sonnet-5-5")]
    subgraph PG["PostgreSQL 16"]
        PROV[("providers_*<br/>doctors · hospitals · slots")]
        CHAT[("assistant_*<br/>sessions · messages · runs · tool calls")]
    end

    UI --> P --> API --> ORC
    ORC -->|"1 pre-check"| RF
    ORC -->|"2 run"| LOOP
    LOOP <-->|"tool use"| LLM
    LOOP --> REG
    REG -->|"tools_readonly role<br/>SELECT only"| PROV
    REG -->|"ToolCallLog"| CHAT
    LOOP --> GV
    GV -->|"result_ids of this session"| CHAT
    ORC -->|"3 post-check on merged state"| RF
    ORC -->|"persist"| CHAT
    API --> SER --> PROV
    UI --> P --> DIR --> PROV
```

| Layer | Responsibility | Key files |
|---|---|---|
| SPA | Chat UX, bilingual/RTL, quick replies, urgency banner, DB-rendered provider cards, trace panel, friendly errors with retry | `frontend/src/pages/Chat/ChatPage.tsx`, `frontend/src/components/chat/*`, `frontend/src/api/client.ts` |
| API | Validation (1000 chars), session ownership, CSRF (anonymous too), throttles, error envelope, OpenAPI | `backend/assistant/api/*` |
| Orchestrator | The only place a turn is decided: rules → loop → rules again → enforcement → persistence | `backend/assistant/agent/orchestrator.py` |
| Red-Flag Engine | Deterministic EN/AR emergency detection over text + structured state | `backend/assistant/safety/red_flags.py` |
| Agent loop | LLM ↔ tools, repair of invalid output, iteration cap | `backend/assistant/agent/loop.py` |
| Tools | Read-only, schema-validated directory queries; everything logged | `backend/assistant/tools/*` |
| Grounding | Recommended IDs must come from this session's search results; unverified names stripped | `backend/assistant/agent/grounding.py` |
| Stages / policy | Urgency floor, round limit, transitions (RECOMMEND requires grounded IDs) | `backend/assistant/agent/stages.py` |
| Cards | Provider/hospital facts serialized from DB rows, never LLM text | `backend/providers/serializers.py` |

## One message, end to end

```mermaid
sequenceDiagram
    autonumber
    actor U as Patient (browser)
    participant API as DRF MessageCreateView
    participant O as Orchestrator
    participant R as Red-Flag Engine
    participant L as Agent Loop
    participant C as Claude (Messages API)
    participant T as Tool Registry
    participant G as Grounding Validator
    participant DB as PostgreSQL

    U->>API: POST /api/chat/sessions/{id}/messages/ {content} + CSRF + session cookie
    API->>API: ownership check (404 if not yours) · throttles · 1000-char limit · 50 msgs/session
    API->>O: handle_message(session, text)
    O->>O: strip control/bidi chars · redact PII
    O->>DB: save user Message · create AgentRunLog
    O->>R: evaluate(all user texts, state)
    alt EMERGENCY (e.g. chest pain + shortness of breath)
        R-->>O: EMERGENCY + matched_flags
        O->>T: get_emergency_info(city)  [called by CODE, no LLM]
        T->>DB: ER hospitals (read-only)
        O->>DB: persist reply (static bilingual text), stage=EMERGENCY
        O-->>API: urgency=EMERGENCY, source=rules, 997/911 + ER hospital IDs
    else not an emergency by rules
        O->>L: run(history + session_context + fenced patient text)
        loop until submit_response is valid (≤ AGENT_MAX_ITERATIONS)
            L->>C: messages.create(system, tools, messages)
            alt data tool call(s)
                C-->>L: tool_use search_providers {...}
                L->>T: execute(name, args)  (Pydantic validation)
                T->>DB: ORM query (SELECT only) + ToolCallLog(result_ids)
                T-->>L: result or structured error → tool_result (is_error)
            else submit_response
                C-->>L: tool_use submit_response {...}
                L->>L: schema check → policy check (1 repair each)
                L->>G: validate(recommended_ids, reply_text)
                G->>DB: IDs ∈ this session's search results ∩ active doctors?
                G-->>L: kept IDs, stripped text, violations (1 corrective retry if all dropped)
            end
        end
        L-->>O: answer | fallback reason (LLM down / max iterations / invalid)
        O->>R: evaluate(texts, state ⊕ state_updates)
        O->>O: urgency = max(rules, llm) · round limit · stage transition
        O->>DB: persist Message(payload with IDs), session state, AgentRunLog
    end
    API->>DB: serialize provider/hospital cards for the IDs
    API-->>U: reply_text, urgency(+source), next_step, questions, providers[], emergency, trace, disclaimer
```

## Data model

See [DATABASE.md](DATABASE.md) for the ERD. The key relationship is `ToolCallLog.result_ids`: it's what the model was actually shown, so it forms the whitelist of what the model is allowed to recommend.

## Failure handling at each boundary

| Boundary | Failure | Behaviour |
|---|---|---|
| Browser → API | offline / timeout (90 s) / 429 / 409 / 5xx / non-JSON proxy error | `ApiError.kind` → bilingual message, retry or "new conversation" button, 997 hint |
| API | invalid input, not owner, CSRF | `{"error": {code, message_en, message_ar}}` with 400/404/403 |
| Orchestrator → LLM | timeout, connection, 429, 5xx | tenacity exponential backoff (`LLM_MAX_RETRIES`, default 3), then safe fallback **with emergency numbers + ER list** |
| Orchestrator → LLM | 4xx / missing key / refusal | no retry, safe fallback |
| Loop | prose instead of tool / invalid schema / policy breach / all IDs invalid | one targeted correction each, then fallback (or deterministic enforcement) |
| Loop | runaway tool calling | hard cap `AGENT_MAX_ITERATIONS=5` → fallback |
| Tools | bad args / unknown tool / DB error | structured tool error to the model; logged; never raises |
| Anything unexpected | unhandled exception | logged with stack trace, generic bilingual 500 |

## Why these boundaries

- **Rules before and after the LLM.** Before, for availability and latency (an emergency doesn't wait on a model). After, because structured answers ("yes, it spreads to my arm" captured as a slot) can reveal an emergency the raw text didn't.
- **IDs, not names, cross the LLM boundary.** The model references `provider_id` values, and the UI renders DB rows. Fabrication is structurally impossible on the card surface, and reply text is scanned as a second line of defense.
- **One orchestrator.** Every turn, including the emergency short-circuit and fallbacks, ends in the same `_persist()`, so the audit trail (`AgentRunLog`, `ToolCallLog`) has no blind spots.
