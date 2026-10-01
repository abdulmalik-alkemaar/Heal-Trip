"""Print the agent trace for the brief's chest-pain example in English and Arabic.

    uv run python manage.py demo_trace                       # provider from LLM_PROVIDER
    uv run python manage.py demo_trace --provider anthropic  # real Claude

Runs each conversation in a rolled-back transaction (nothing is persisted) and
prints Markdown that can be pasted into NOTES_FOR_REVIEWER.md.
"""

import json

from django.core.management.base import BaseCommand
from django.db import transaction

from assistant.agent.orchestrator import handle_message
from assistant.management.commands.run_evals import _client
from assistant.models import ChatSession

CONVERSATIONS = {
    "en": [
        "I have chest pain and I'm not sure whether I should see a cardiologist, go to the ER, "
        "or seek a second opinion.",
        "It started two weeks ago and comes and goes. No, it stays in my chest. "
        "No shortness of breath, sweating or dizziness. I'm 35 and I live in Riyadh.",
    ],
    "ar": [
        "عندي ألم في الصدر ومو متأكد هل أشوف دكتور قلب أو أروح الطوارئ أو آخذ رأي طبي ثاني",
        "بدأ قبل أسبوعين ويجي ويروح، ما ينتشر لأي مكان، وما عندي ضيق تنفس ولا تعرق. "
        "عمري ٣٥ وأنا في جدة.",
    ],
}


class Command(BaseCommand):
    help = "Print EN + AR traces for the brief's chest-pain example."

    def add_arguments(self, parser):
        parser.add_argument("--provider", choices=["anthropic", "mock"], default=None)

    def handle(self, *args, provider=None, **options):
        from django.conf import settings

        client = _client(provider or settings.LLM_PROVIDER)
        for language, turns in CONVERSATIONS.items():
            with transaction.atomic():
                session = ChatSession.objects.create(language=language)
                self.stdout.write(
                    f"\n### {language.upper()} ({client.provider} · {client.model})\n"
                )
                for number, text in enumerate(turns, 1):
                    payload = handle_message(session, text, client).payload
                    summary = {
                        "urgency": payload["urgency"],
                        "urgency_source": payload["urgency_source"],
                        "next_step": payload["next_step"],
                        "clarifying_questions": [
                            q["question"] for q in payload["clarifying_questions"]
                        ],
                        "provider_ids": payload["provider_ids"],
                        "trace": {
                            k: payload["trace"][k]
                            for k in (
                                "stage",
                                "state",
                                "tool_calls",
                                "iterations",
                                "rules",
                                "grounding_violations",
                            )
                        },
                    }
                    self.stdout.write(f"**Turn {number}, patient:** {text}\n")
                    self.stdout.write(f"**Assistant:** {payload['reply_text']}\n")
                    self.stdout.write(
                        "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n"
                    )
                transaction.set_rollback(True)
