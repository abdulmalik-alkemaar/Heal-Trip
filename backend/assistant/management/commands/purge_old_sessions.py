"""Retention policy: delete conversations not touched for CHAT_RETENTION_DAYS (default 30).

Cascades to messages, agent run logs and tool call logs. Run daily (cron / Railway
scheduled job):  python manage.py purge_old_sessions
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from assistant.models import ChatSession


class Command(BaseCommand):
    help = "Delete chat sessions (and their messages/logs) older than the retention period."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="Override CHAT_RETENTION_DAYS.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Only report what would be deleted."
        )

    def handle(self, *args, days: int | None, dry_run: bool, **options) -> None:
        days = days if days is not None else settings.CHAT_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)
        stale = ChatSession.objects.filter(updated_at__lt=cutoff)
        count = stale.count()
        if dry_run:
            self.stdout.write(
                f"Would delete {count} sessions last updated before {cutoff:%Y-%m-%d}."
            )
            return
        stale.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} sessions older than {days} days."))
