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

- **Evals on the real model: 16/16** (`evals/RESULTS.md`). The model's replies never named a provider: it referred to "the cards below", as the prompt requires. When I first tried the live API the account had no credit; the 400 was handled by the safe fallback exactly as designed, and the API's error type is now logged so that kind of failure is diagnosable.
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

## Trace: the brief's chest-pain example (English and Arabic, real model)

Generated with `uv run python manage.py demo_trace --provider anthropic` (`claude-sonnet-5-5`). What to notice:
- **Turn 1** is **URGENT, decided by the rules** (`CHEST_PAIN`), with **NEED_MORE_INFO** and focused screening questions, and no tool calls yet. The model also gives the 997 safety-net instruction up front.
- **Turn 2**: the patient denies the red flags, so the model calls `search_providers` (cardiology + city). Its `recommended_provider_ids` equal the tool's `result_ids` exactly, and there are no grounding violations.
- The reply text names no doctor; the UI renders the cards from the database.

### EN (anthropic · claude-sonnet-5-5)
**Turn 1, patient:** I have chest pain and I'm not sure whether I should see a cardiologist, go to the ER, or seek a second opinion.
**Assistant:** I'm sorry you're dealing with this. Chest pain deserves attention, so let me ask a few quick questions to point you to the right step. If at any point you get shortness of breath, sweating, nausea, fainting, or pain spreading to your arm, jaw or back, call 997 right away.
```json
{
  "urgency": "URGENT",
  "urgency_source": "rules",
  "next_step": "NEED_MORE_INFO",
  "clarifying_questions": [
    "Are you having any shortness of breath, sweating, nausea, dizziness or fainting with the pain?",
    "Does the pain spread to your arm, jaw, neck or back?",
    "When did it start, and is it constant or does it come and go?"
  ],
  "provider_ids": [],
  "trace": {
    "stage": "CLARIFY",
    "state": {
      "chief_complaint": "chest pain",
      "symptoms": [
        "chest pain"
      ],
      "patient_goal": "UNSURE",
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
**Assistant:** Thank you, that helps. Chest pain that has come and gone for two weeks, without shortness of breath, sweating or dizziness, doesn't sound like an emergency right now. It still needs to be checked soon, so I'd suggest booking a cardiologist visit in the next few days instead of waiting. I can't say what is causing it. An in-person exam and tests are the way to find out.

I've listed English-speaking cardiologists in Riyadh below. Both also offer second-opinion visits, which is useful if you've already been given a diagnosis.

Go to the ER or call 997 right away if any of these happen:
- The pain becomes severe, or lasts more than a few minutes without easing
- Shortness of breath, sweating or nausea
- Fainting or dizziness
- Pain spreading to your arm, jaw, neck or back

One more question, so I can guide you better:
```json
{
  "urgency": "URGENT",
  "urgency_source": "rules",
  "next_step": "SEE_SPECIALIST",
  "clarifying_questions": [],
  "provider_ids": [
    1,
    3
  ],
  "trace": {
    "stage": "RECOMMEND",
    "state": {
      "chief_complaint": "chest pain",
      "symptoms": [
        "chest pain",
        "intermittent"
      ],
      "onset": "two weeks ago, intermittent",
      "duration": "two weeks",
      "radiating_pain": false,
      "shortness_of_breath": false,
      "sweating_or_nausea": false,
      "age_range": "18_39",
      "patient_goal": "SPECIALIST",
      "city": "RIYADH",
      "preferred_language": "en"
    },
    "tool_calls": [
      {
        "name": "search_providers",
        "args": {
          "city": "RIYADH",
          "limit": 3,
          "language": "en",
          "specialty": "CARDIOLOGY"
        },
        "result_ids": [
          1,
          3
        ],
        "latency_ms": 55,
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

### AR (anthropic · claude-sonnet-5-5)
**Turn 1, patient:** عندي ألم في الصدر ومو متأكد هل أشوف دكتور قلب أو أروح الطوارئ أو آخذ رأي طبي ثاني
**Assistant:** سلامتك. ألم الصدر يستاهل الانتباه، وأبغى أتأكد أولاً من أهم الأشياء عشان أحدد لك الخطوة الأنسب. وإذا كان معه ضيق نفس أو تعرّق أو غثيان أو دوخة أو إغماء أو انتشار الألم إلى الذراع أو الفك، لا تنتظر واتصل على 997 فوراً.
```json
{
  "urgency": "URGENT",
  "urgency_source": "rules",
  "next_step": "NEED_MORE_INFO",
  "clarifying_questions": [
    "هل معه ضيق نفس أو تعرّق أو غثيان أو دوخة؟",
    "هل الألم ينتشر إلى الذراع أو الفك أو الرقبة أو الظهر؟",
    "متى بدأ الألم وهل هو مستمر أو يجي ويروح؟"
  ],
  "provider_ids": [],
  "trace": {
    "stage": "CLARIFY",
    "state": {
      "chief_complaint": "ألم في الصدر",
      "symptoms": [
        "ألم في الصدر"
      ],
      "patient_goal": "UNSURE",
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
**Assistant:** شكراً على التوضيح، وسلامتك. كون الألم ما ينتشر ولا معه ضيق نفس أو تعرّق شيء مطمّن نوعاً ما، لكن ألم صدر مستمر أسبوعين ويجي ويروح لازم يتقيّم عند طبيب قلب قريباً، وما أنصح تأجّله. أنا ما أقدر أشخّص السبب، والطبيب هو اللي يحدد الفحوصات اللازمة.

الخطوة المناسبة الآن: موعد مع طبيب قلب في جدة في أقرب وقت. حطيت لك أدناه أطباء قلب في جدة يتكلمون العربي.

لكن اذهب للطوارئ أو اتصل 997 فوراً إذا صار الألم شديداً أو طال أكثر من دقائق، أو ظهر ضيق نفس أو تعرّق أو غثيان أو دوخة أو إغماء، أو انتشر للذراع أو الفك.

عشان أضبط لك التوصية أكثر:
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
      "chief_complaint": "ألم في الصدر",
      "symptoms": [
        "ألم في الصدر"
      ],
      "onset": "قبل أسبوعين",
      "duration": "أسبوعان، متقطع",
      "radiating_pain": false,
      "shortness_of_breath": false,
      "sweating_or_nausea": false,
      "age_range": "18_39",
      "patient_goal": "SPECIALIST",
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
        "latency_ms": 18,
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
