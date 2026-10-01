"""Run the evaluation scenarios in evals/scenarios.yaml against the agent.

    uv run python manage.py run_evals                      # provider from LLM_PROVIDER
    uv run python manage.py run_evals --provider anthropic # real Claude (needs ANTHROPIC_API_KEY)
    uv run python manage.py run_evals --only S02,S10

Each scenario runs through the real orchestrator (rules, loop, tools, grounding)
in a transaction that is rolled back, so evals never pollute the database.
Writes evals/RESULTS.md (committed) and evals/results/latest.json (ignored).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from assistant.agent.orchestrator import handle_message
from assistant.llm.client import AnthropicClient, LLMClient, LLMUnavailableError, MockLLMClient
from assistant.models import ChatSession
from providers.models import Doctor

EVALS_DIR = Path(settings.BASE_DIR).parent / "evals"
ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")


def _client(provider: str) -> LLMClient:
    if provider == "anthropic":
        try:
            return AnthropicClient()
        except LLMUnavailableError as exc:
            raise CommandError("ANTHROPIC_API_KEY is not set; use --provider mock.") from exc
    return MockLLMClient()


def _check(expect: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    """Return a list of failed expectations (empty = pass)."""
    failures: list[str] = []
    if "urgency" in expect and payload["urgency"] not in expect["urgency"]:
        failures.append(f"urgency {payload['urgency']} not in {expect['urgency']}")
    if "next_step" in expect and payload["next_step"] not in expect["next_step"]:
        failures.append(f"next_step {payload['next_step']} not in {expect['next_step']}")
    if len(payload["clarifying_questions"]) < expect.get("min_questions", 0):
        failures.append(f"only {len(payload['clarifying_questions'])} questions")
    reply = payload["reply_text"]
    if lang := expect.get("reply_language"):
        arabic, latin = len(ARABIC.findall(reply)), len(LATIN.findall(reply))
        if (arabic < latin) if lang == "ar" else (latin < arabic):
            failures.append(f"reply not in {lang}")
    for needle in expect.get("reply_not_contains", []):
        if needle.lower() in reply.lower():
            failures.append(f"reply contains {needle!r}")
    if rules := expect.get("providers"):
        failures += _check_providers(rules, payload["provider_ids"])
    return failures


def _check_providers(rules: dict[str, Any], ids: list[int]) -> list[str]:
    failures = []
    if len(ids) < rules.get("min", 0):
        failures.append(f"{len(ids)} providers < {rules['min']}")
    if "max" in rules and len(ids) > rules["max"]:
        failures.append(f"{len(ids)} providers > {rules['max']}")
    doctors = (
        Doctor.objects.filter(pk__in=ids).select_related("hospital").prefetch_related("specialties")
    )
    for d in doctors:
        codes = {s.code for s in d.specialties.all()}
        if (city := rules.get("city")) and d.hospital.city != city:
            failures.append(f"provider {d.pk} in {d.hospital.city} != {city}")
        if (city := rules.get("not_city")) and d.hospital.city == city:
            failures.append(f"provider {d.pk} is in {city}")
        if (allowed := rules.get("specialty_in")) and not codes & set(allowed):
            failures.append(f"provider {d.pk} specialty {sorted(codes)} not in {allowed}")
        if rules.get("second_opinion") and not d.offers_second_opinion:
            failures.append(f"provider {d.pk} does not offer second opinions")
        if (lang := rules.get("speaks")) and lang not in d.languages:
            failures.append(f"provider {d.pk} does not speak {lang}")
    return failures


class Command(BaseCommand):
    help = "Run evals/scenarios.yaml and write evals/RESULTS.md"

    def add_arguments(self, parser):
        parser.add_argument("--provider", choices=["anthropic", "mock"], default=None)
        parser.add_argument("--only", default="", help="Comma-separated scenario ids")
        parser.add_argument("--no-write", action="store_true", help="Do not write RESULTS.md")

    def handle(self, *args, provider: str | None, only: str, no_write: bool, **options):
        provider = provider or settings.LLM_PROVIDER
        scenarios = yaml.safe_load((EVALS_DIR / "scenarios.yaml").read_text(encoding="utf-8"))
        if only:
            wanted = set(only.split(","))
            scenarios = [s for s in scenarios if s["id"] in wanted]
        client = _client(provider)
        model = client.model
        # The evals measure the agent, not the demo's rate limits.
        settings.CHAT_MAX_MESSAGES_PER_SESSION = 10_000
        settings.DEMO_DAILY_MESSAGE_CAP = 0

        results = [self._run(s, client) for s in scenarios]
        passed = sum(r["pass"] for r in results)
        self.stdout.write(self._table(results))
        self.stdout.write(
            self.style.SUCCESS(f"\n{passed}/{len(results)} passed ({provider}, {model})")
        )
        if not no_write:
            self._write(results, provider, model, passed)

    def _run(self, scenario: dict[str, Any], client: LLMClient) -> dict[str, Any]:
        started = time.monotonic()
        with transaction.atomic():
            session = ChatSession.objects.create(language=scenario["language"])
            payload: dict[str, Any] = {}
            violations = 0
            for turn in scenario["turns"]:
                payload = handle_message(session, turn, client).payload
                violations += len(payload["trace"]["grounding_violations"])
            failures = _check(scenario.get("expect", {}), payload)
            transaction.set_rollback(True)
        return {
            "id": scenario["id"],
            "title": scenario["title"],
            "language": scenario["language"],
            "expected": {k: scenario.get("expect", {}).get(k) for k in ("urgency", "next_step")},
            "actual": {
                "urgency": payload["urgency"],
                "urgency_source": payload["urgency_source"],
                "next_step": payload["next_step"],
                "questions": len(payload["clarifying_questions"]),
                "provider_ids": payload["provider_ids"],
                "outcome": payload["trace"]["outcome"],
                "reply_text": payload["reply_text"],
                "tool_calls": [c["name"] for c in payload["trace"]["tool_calls"]],
            },
            "grounding_violations": violations,
            "pass": not failures,
            "failures": failures,
            "latency_s": round(time.monotonic() - started, 1),
        }

    @staticmethod
    def _table(results: list[dict[str, Any]]) -> str:
        header = "| ID | Lang | Scenario | Expected | Actual | Pass | Grounding violations |\n|---|---|---|---|---|---|---|"
        rows = []
        for r in results:
            exp = " / ".join(
                " or ".join(v) if isinstance(v, list) else "any" for v in r["expected"].values()
            )
            act = f"{r['actual']['urgency']} ({r['actual']['urgency_source']}) / {r['actual']['next_step']}"
            if r["actual"]["provider_ids"]:
                act += f" · providers {r['actual']['provider_ids']}"
            mark = "✅" if r["pass"] else "❌ " + "; ".join(r["failures"])
            rows.append(
                f"| {r['id']} | {r['language']} | {r['title']} | {exp} | {act} | {mark} | {r['grounding_violations']} |"
            )
        return "\n".join([header, *rows])

    def _write(self, results, provider: str, model: str, passed: int) -> None:
        stamp = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
        md = (
            "# Evaluation results\n\n"
            f"- Run: {stamp}\n- LLM provider: `{provider}` · model: `{model}`\n"
            f"- Result: **{passed}/{len(results)} scenarios passed**\n"
            "- Scenarios: [`scenarios.yaml`](scenarios.yaml). Reproduce: "
            "`cd backend && uv run python manage.py run_evals --provider anthropic`\n\n"
            + (
                "> ⚠️ **Mock run.** These results come from `MockLLMClient`'s keyword heuristic, "
                "not from Claude. They show the deterministic layers (rules, tools, grounding, "
                "stages) working end to end. Run with `--provider anthropic` for real model "
                "results.\n\n"
                if provider == "mock"
                else ""
            )
            + "Expected = allowed urgency / next_step. Actual shows the urgency *source* "
            "(rules = deterministic red-flag engine, llm = model). Grounding violations are "
            "attempts caught and removed by the validator (they never reach the patient).\n\n"
            + self._table(results)
            + "\n"
        )
        (EVALS_DIR / "RESULTS.md").write_text(md, encoding="utf-8")
        (EVALS_DIR / "results" / "latest.json").write_text(
            json.dumps(
                {"provider": provider, "model": model, "results": results},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.stdout.write(f"Wrote {EVALS_DIR / 'RESULTS.md'}")
