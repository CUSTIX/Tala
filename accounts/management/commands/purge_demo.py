from django.conf import settings
from django.core.management.base import BaseCommand

from core.demo import purge_expired


class Command(BaseCommand):
    help = "Delete demo teachers older than DEMO_TTL_HOURS, with all their fake classes."

    def handle(self, *args, **options):
        count = purge_expired(settings.DEMO_TTL_HOURS)
        self.stdout.write(f"Deleted {count} expired demo account(s).")
