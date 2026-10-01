# Notes for the reviewer

Short, honest notes on what this is, what I assumed, and what I'd do next.

## What to look at first (10 minutes)

1. The **README** guiding principle and the traceability table (§3).
2. `backend/assistant/agent/orchestrator.py`: one turn, end to end, in about 120 readable lines (rules → loop → rules → enforcement → persist).
3. `backend/assistant/agent/loop.py`: the agent loop and its correction policy.
4. `backend/assistant/agent/grounding.py`: why the model can't put an unverified provider on screen.
5. `backend/assistant/safety/red_flags.py` + `assistant/tests/test_red_flags.py`: the deterministic EN/AR safety layer.
6. Run the app with no API key (`LLM_PROVIDER=mock`), click the examples, and open **Agent trace**.

## Assumptions

- All directory data is **fictional**. There is no real booking; slots are display-only.
- **Not medical advice.** The assistant navigates, never diagnoses or prescribes. A bilingual disclaimer comes with every response.
- **Saudi context:** 997 (Red Crescent ambulance), 911 (unified), 937 (MOH line, non-emergency); four cities; Asia/Riyadh time.
- Anonymous use is the default so reviewers need no login; the template's Google login still works.
- "Arabic support" means the full UI, the agent's replies, DB fields, error messages and the red-flag rules, not only RTL layout.

## Things I'm deliberately transparent about

- **Real-LLM eval results are pending.** The eval runner, scenarios and Claude integration are complete and tested against a faked SDK. When I ran them against the live API, the account had no credit (`400 invalid_request_error: credit balance is too low`). The fallback path handled that exactly as designed. The committed `evals/RESULTS.md` is therefore a clearly labeled **mock run**, which validates the deterministic layers end to end. Regenerate it with: `cd backend && uv run python manage.py run_evals --provider anthropic`.
- **Two safety-rule bugs were found by testing the product, not the unit tests.** Both are fixed with regression tests, and both are in the git history:
  1. `ألم شديد في الصدر يمتد للذراع ويتعرق` was rated URGENT instead of EMERGENCY: an adjective between "pain" and "chest", plus a missing verb form (commit `7001480`).
  2. "No shortness of breath, sweating or dizziness" escalated to EMERGENCY, because negation didn't cover a comma list.

  This is the kind of failure keyword rules have. It's also why the LLM is kept as a second net (it can escalate), and why every miss becomes a test.
- **The mock LLM is a heuristic,** used for CI and for offline demos. It speaks the same tool protocol as Claude, and the trace labels it `mock`.
- **The local environment had no Docker,** so `docker compose up` was not executed on this machine. The compose file and Dockerfiles were corrected: the template's build context didn't match its Dockerfile. CI builds both images. Locally everything ran against real PostgreSQL 16 (portable binaries, `scripts/dev-postgres.ps1`).

## Time spent

_<fill in>_

## What I'd improve next

See README §15. The top three: a clinician-reviewed red-flag rule set with NER instead of regex; SSE streaming plus an observability dashboard over `AgentRunLog`; and real booking with slot holds.

## Trace: the brief's chest-pain example (English and Arabic)

Generated with `uv run python manage.py demo_trace --provider mock`. Re-run with `--provider anthropic` once the API account has credit, to get the real model's version. What to notice:
- **Turn 1** is **URGENT, decided by the rules** (`CHEST_PAIN`), with **NEED_MORE_INFO** and screening questions, and no tool calls yet.
- **Turn 2**: the patient denies the red flags, so the agent calls `search_providers` filtered by specialty and city. The recommended IDs are exactly the tool's `result_ids`, and there are no grounding violations.
- The urgency never drops below the rules' floor (URGENT), even though no emergency was found.

### EN (mock · mock-scripted)
**Turn 1, patient:** I have chest pain and I'm not sure whether I should see a cardiologist, go to the ER, or seek a second opinion.
**Assistant:** I'm sorry you're dealing with this. To point you to the right next step, I need a few details.
```json
{
  "urgency": "URGENT",
  "urgency_source": "rules",
  "next_step": "NEED_MORE_INFO",
  "clarifying_questions": [
    "When did the pain start, and does it come and go or is it constant?",
    "Does the pain spread to your arm, jaw, neck or back?",
    "Do you have shortness of breath, sweating, nausea or dizziness?"
  ],
  "provider_ids": [],
  "trace": {
    "stage": "CLARIFY",
    "state": {
      "chief_complaint": "I have chest pain and I'm not sure whether I should see a cardiologist, go to the ER, or seek a second opinion.",
      "preferred_language": "en"
    },
    "tool_calls": [],
    "iterations": 1,
    "rules": {
      "level": "URGENT",
      "matched_flags": [
        "CHEST_PAIN"
      ]
    },
    "grounding_violations": []
  }
}
```
**Turn 2, patient:** It started two weeks ago and comes and goes. No, it stays in my chest. No shortness of breath, sweating or dizziness. I'm 35 and I live in Riyadh.
**Assistant:** Based on what you told me, a specialist visit is a sensible next step. Here are verified options from our directory. If your symptoms get worse, call 997.
```json
{
  "urgency": "URGENT",
  "urgency_source": "rules",
  "next_step": "SEE_SPECIALIST",
  "clarifying_questions": [],
  "provider_ids": [
    1,
    3,
    2
  ],
  "trace": {
    "stage": "RECOMMEND",
    "state": {
      "chief_complaint": "I have chest pain and I'm not sure whether I should see a cardiologist, go to the ER, or seek a second opinion.",
      "city": "RIYADH",
      "preferred_language": "en"
    },
    "tool_calls": [
      {
        "name": "search_providers",
        "args": {
          "city": "RIYADH",
          "limit": 3,
          "specialty": "CARDIOLOGY"
        },
        "result_ids": [
          1,
          2,
          3
        ],
        "latency_ms": 58,
        "success": true,
        "error": ""
      }
    ],
    "iterations": 2,
    "rules": {
      "level": "URGENT",
      "matched_flags": [
        "CHEST_PAIN"
      ]
    },
    "grounding_violations": []
  }
}
```

### AR (mock · mock-scripted)
**Turn 1, patient:** عندي ألم في الصدر ومو متأكد هل أشوف دكتور قلب أو أروح الطوارئ أو آخذ رأي طبي ثاني
**Assistant:** أنا آسف لما تمر به. حتى أوجهك للخطوة المناسبة، أحتاج بعض التفاصيل.
```json
{
  "urgency": "URGENT",
  "urgency_source": "rules",
  "next_step": "NEED_MORE_INFO",
  "clarifying_questions": [
    "متى بدأ الألم؟ وهل هو مستمر أم يأتي ويذهب؟",
    "هل ينتشر الألم إلى الذراع أو الفك أو الرقبة أو الظهر؟",
    "هل لديك ضيق في التنفس أو تعرق أو غثيان أو دوخة؟"
  ],
  "provider_ids": [],
  "trace": {
    "stage": "CLARIFY",
    "state": {
      "chief_complaint": "عندي ألم في الصدر ومو متأكد هل أشوف دكتور قلب أو أروح الطوارئ أو آخذ رأي طبي ثاني",
      "preferred_language": "ar"
    },
    "tool_calls": [],
    "iterations": 1,
    "rules": {
      "level": "URGENT",
      "matched_flags": [
        "CHEST_PAIN"
      ]
    },
    "grounding_violations": []
  }
}
```
**Turn 2, patient:** بدأ قبل أسبوعين ويجي ويروح، ما ينتشر لأي مكان، وما عندي ضيق تنفس ولا تعرق. عمري ٣٥ وأنا في جدة.
**Assistant:** بناءً على ما ذكرته، زيارة طبيب مختص خطوة مناسبة. هذه خيارات موثّقة من دليلنا. إذا ساءت الأعراض فاتصل على 997.
```json
{
  "urgency": "URGENT",
  "urgency_source": "rules",
  "next_step": "SEE_SPECIALIST",
  "clarifying_questions": [],
  "provider_ids": [
    11,
    12
  ],
  "trace": {
    "stage": "RECOMMEND",
    "state": {
      "chief_complaint": "عندي ألم في الصدر ومو متأكد هل أشوف دكتور قلب أو أروح الطوارئ أو آخذ رأي طبي ثاني",
      "city": "JEDDAH",
      "preferred_language": "ar"
    },
    "tool_calls": [
      {
        "name": "search_providers",
        "args": {
          "city": "JEDDAH",
          "limit": 3,
          "language": "ar",
          "specialty": "CARDIOLOGY"
        },
        "result_ids": [
          11,
          12
        ],
        "latency_ms": 32,
        "success": true,
        "error": ""
      }
    ],
    "iterations": 2,
    "rules": {
      "level": "URGENT",
      "matched_flags": [
        "CHEST_PAIN"
      ]
    },
    "grounding_violations": []
  }
}
```
