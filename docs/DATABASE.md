# Database structure

PostgreSQL 16. There are two Django apps:

- **`providers`** is the provider directory. It is read-only from the agent's point of view and is the only source of truth for doctors and hospitals.
- **`assistant`** holds the conversations and the audit trail: what the agent did, which tools it called, and which IDs those tools returned.

All provider data is **fictional** (`backend/providers/seed_data.py`).

## ERD

```mermaid
erDiagram
    SPECIALTY ||--o{ DOCTOR_SPECIALTIES : "tagged on"
    DOCTOR ||--o{ DOCTOR_SPECIALTIES : has
    HOSPITAL ||--o{ DOCTOR : employs
    DOCTOR ||--o{ AVAILABILITY_SLOT : offers
    USER |o--o{ CHAT_SESSION : "owns (optional)"
    CHAT_SESSION ||--o{ MESSAGE : contains
    CHAT_SESSION ||--o{ AGENT_RUN_LOG : "one per assistant turn"
    CHAT_SESSION ||--o{ TOOL_CALL_LOG : "every tool call"
    AGENT_RUN_LOG |o--o{ TOOL_CALL_LOG : "calls made in that turn"

    SPECIALTY {
        bigint id PK
        varchar code UK "CARDIOLOGY, NEUROLOGY, ... (enum)"
        varchar name_en
        varchar name_ar
    }
    HOSPITAL {
        bigint id PK
        varchar name_en UK
        varchar name_ar
        varchar city "RIYADH|JEDDAH|DAMMAM|ABHA (enum, indexed)"
        varchar address_en
        varchar address_ar
        bool has_emergency "indexed with city"
        varchar emergency_phone
        varchar accreditation "JCI / CBAHI / empty"
        bool is_active "indexed with city"
    }
    DOCTOR {
        bigint id PK "the provider_id the LLM may reference"
        varchar name_en
        varchar name_ar
        bigint hospital_id FK
        varchar_array languages "ar/en - GIN indexed"
        smallint years_experience
        bool offers_second_opinion
        bool offers_telemedicine
        decimal consultation_fee_sar
        decimal rating "nullable"
        bool is_active "indexed"
    }
    DOCTOR_SPECIALTIES {
        bigint doctor_id FK "indexed"
        bigint specialty_id FK "indexed"
    }
    AVAILABILITY_SLOT {
        bigint id PK
        bigint doctor_id FK
        timestamptz start_time "unique with doctor"
        smallint duration_minutes
        bool is_booked "index (doctor, is_booked, start_time)"
    }
    CHAT_SESSION {
        uuid id PK "non-enumerable"
        bigint user_id FK "nullable - anonymous chat allowed"
        varchar language "ar|en"
        jsonb state "PatientState slots"
        varchar urgency_level
        varchar current_stage "INTAKE..RECOMMEND|EMERGENCY"
        smallint clarification_rounds
        timestamptz created_at
        timestamptz updated_at "indexed (retention purge)"
    }
    MESSAGE {
        bigint id PK
        uuid session_id FK
        varchar role "user|assistant|tool"
        text content
        jsonb structured_payload "assistant turn payload"
        timestamptz created_at
    }
    AGENT_RUN_LOG {
        bigint id PK
        uuid session_id FK
        varchar llm_provider
        varchar llm_model
        smallint iterations
        int latency_ms
        varchar rules_urgency
        varchar llm_urgency
        varchar final_urgency "max(rules, llm)"
        varchar urgency_source "rules|llm|fallback"
        varchar next_step
        varchar stage
        varchar outcome "ok|emergency_short_circuit|fallback"
        jsonb matched_red_flags
        jsonb grounding_violations
        smallint grounding_violations_count
        varchar fallback_reason
        timestamptz created_at
    }
    TOOL_CALL_LOG {
        bigint id PK
        uuid session_id FK
        bigint run_id FK "nullable"
        varchar tool_name
        jsonb arguments "validated enums/ints only"
        jsonb result_ids "doctor ids returned = grounding whitelist"
        jsonb result_hospital_ids
        bool success
        text error
        int latency_ms
        timestamptz created_at
    }
```

## Tables

| Table | Purpose | Notes |
|---|---|---|
| `providers_specialty` | Closed list of specialties | `code` mirrors the `SpecialtyCode` enum used in the tool schemas, so the LLM cannot search for a specialty that doesn't exist |
| `providers_hospital` | Hospitals and ERs | `has_emergency` + `emergency_phone` power the emergency path. Indexes: `(is_active, city)`, `(has_emergency, city)` |
| `providers_doctor` | Doctors (the *providers* the agent recommends) | `languages` is a Postgres `varchar[]` with a GIN index, so `languages @> '{ar}'` is index-backed. Unique `(name_en, hospital)` makes seeding idempotent |
| `providers_doctor_specialties` | M2M doctor↔specialty | Django indexes both FKs |
| `providers_availabilityslot` | Bookable 30-minute slots, next 14 days | Composite index `(doctor, is_booked, start_time)` answers "next free slots for doctor X" |
| `assistant_chatsession` | One conversation | `state` holds the validated `PatientState`. The UUID primary key can't be enumerated, and ownership is still checked separately (see SECURITY.md) |
| `assistant_message` | User and assistant turns | `structured_payload` stores the full assistant API payload, so history can be replayed exactly |
| `assistant_agentrunlog` | One row per assistant turn | Records urgency provenance (rules vs LLM), iterations, latency and grounding violations: the "why did it answer that" audit trail |
| `assistant_toolcalllog` | One row per tool execution | `result_ids` is the **grounding whitelist**: the model may only recommend doctor IDs that appear here for its own session |

## Seed coverage (fictional)

| City | ER hospital | Specialties available | Deliberate gaps |
|---|---|---|---|
| Riyadh | Al-Wahah Medical City | all 7 | (one inactive cardiologist, for grounding tests) |
| Jeddah | Red Sea Care Hospital | all except Gastroenterology | Gastroenterology |
| Dammam | Eastern Gulf Hospital | all except Pulmonology | Pulmonology |
| Abha | Asir Highlands Hospital | all except Neurology and Gastroenterology | **Neurology** (headline "not found" case) |

Seed with `python manage.py seed_providers`. The command is idempotent and runs automatically on `docker compose up`.
