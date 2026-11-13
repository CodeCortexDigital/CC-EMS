"""Send the newest hash of each school's audit chain to the time-stamping authority and keep the signed reply (run daily from cron).

    python manage.py anchor_audit_chain
"""
from django.core.management.base import BaseCommand, CommandError

from services.core.audit import anchors
from services.core.audit.models import AuditChainHead


class Command(BaseCommand):
    help = 'Time-stamp the newest hash of every audit chain with an outside authority (TIMESTAMP_AUTHORITY_URL).'

    def handle(self, *args, **opts):
        if not anchors.authority():
            raise CommandError('No time-stamping authority is set (TIMESTAMP_AUTHORITY_URL).')
        done, failed = 0, 0
        for chain in AuditChainHead.objects.exclude(last_hash='').values_list('chain', flat=True):
            try:
                a = anchors.anchor(chain)
                done += 1
                self.stdout.write(f'{chain}: record {a.seq} time-stamped')
            except anchors.AnchorError as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f'{chain}: {exc}'))
        self.stdout.write(f'{done} chain(s) time-stamped, {failed} failed.')
        if failed:
            raise CommandError('Some chains could not be time-stamped.')
