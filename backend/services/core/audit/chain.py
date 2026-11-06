"""A tamper-evident trail for decisions made with or about AI.

Routine audit rows stay as they are. Decision records (an AI request, who approved it and what happened, a person's review of a risk
flag, a change to the school's AI settings) are written here instead. Each one carries the hash of the one before it for the same
school, so changing, removing or inserting a record afterwards breaks the chain and `verify_audit_chain` reports where.

What this does and does not give you: the application cannot change or delete these rows, and anyone with direct access to the
database who edits one is caught on the next check. It cannot catch someone who rewrites the whole chain and its head together;
for that, copy the head hash that `verify_audit_chain` prints to somewhere outside the database from time to time.

The hash covers the school, position, previous hash, action, resource, time and the data (which includes the person's email at the
time). The user link itself is not hashed, so deleting a user account does not break the chain.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timezone as dt_timezone

from django.db import transaction

from .models import AuditChainHead, AuditLog

PROTECTED_PREFIXES = ('ai.action.', 'analytics.risk.', 'ai.settings.', 'ai.chat.')


class AuditWriteError(Exception):
    """The decision record could not be written, so whatever it was recording must not go ahead."""


def is_protected(resource_type: str) -> bool:
    return (resource_type or '').startswith(PROTECTED_PREFIXES)


def _plain(value):
    """The data as the database will hand it back (strings for ids and dates), so the hash is the same on every read."""
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def _canonical(row) -> str:
    stamp = row.timestamp.astimezone(dt_timezone.utc).isoformat()
    body = {'chain': row.chain, 'seq': row.seq, 'prev': row.prev_hash, 'action': row.action, 'resource_type': row.resource_type,
            'resource_id': str(row.resource_id) if row.resource_id else None, 'timestamp': stamp,
            'new_data': row.new_data, 'old_data': row.old_data}
    return json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _hash(row) -> str:
    return hashlib.sha256(_canonical(row).encode('utf-8')).hexdigest()


def append(*, user, school, action: str, resource_type: str, resource_id=None, new_data=None, old_data=None) -> AuditLog:
    """Write one decision record to the school's chain. Raises AuditWriteError if it cannot be saved (call it inside the
    transaction of whatever it records, so that nothing happens without its record)."""
    chain = str(school.pk) if getattr(school, 'pk', None) else 'platform'
    data = _plain(new_data or {})
    data.setdefault('actor', getattr(user, 'email', '') or '')
    try:
        with transaction.atomic():
            AuditChainHead.objects.get_or_create(chain=chain)
            head = AuditChainHead.objects.select_for_update().get(chain=chain)
            seq = head.last_seq + 1
            row = AuditLog.objects.create(
                user=user if getattr(user, 'pk', None) else None, school=school if getattr(school, 'pk', None) else None, action=action,
                resource_type=resource_type, resource_id=resource_id, new_data=data, old_data=_plain(old_data) if old_data else None,
                chain=chain, seq=seq, prev_hash=head.last_hash)
            row.entry_hash = _hash(row)
            AuditLog.objects.filter(pk=row.pk, entry_hash='').update(entry_hash=row.entry_hash)
            head.last_seq, head.last_hash = seq, row.entry_hash
            head.save(update_fields=['last_seq', 'last_hash'])
    except Exception as exc:
        raise AuditWriteError('The decision record could not be saved.') from exc
    return row


def verify(chain: str | None = None) -> dict:
    """Check every chain (or one). Returns {'ok': bool, 'chains': n, 'records': n, 'problems': [...], 'heads': {chain: hash}}."""
    problems, records, heads = [], 0, {}
    names = [chain] if chain else sorted(set(AuditLog._base_manager.exclude(chain='').values_list('chain', flat=True))
                                         | set(AuditChainHead.objects.values_list('chain', flat=True)))
    for name in names:
        expected_seq, prev = 1, ''
        for row in AuditLog._base_manager.filter(chain=name).exclude(entry_hash='').order_by('seq', 'timestamp'):
            records += 1
            if row.seq != expected_seq:
                problems.append(f'{name}: expected record {expected_seq} but found {row.seq} (a record is missing or was inserted)')
                expected_seq = row.seq
            if row.prev_hash != prev:
                problems.append(f'{name}: record {row.seq} does not follow the one before it')
            if _hash(row) != row.entry_hash:
                problems.append(f'{name}: record {row.seq} ({row.resource_type}) was changed after it was written')
            prev, expected_seq = row.entry_hash, expected_seq + 1
        head = AuditChainHead.objects.filter(chain=name).first()
        last_seq = expected_seq - 1
        if head and (head.last_seq != last_seq or head.last_hash != prev):
            problems.append(f'{name}: the newest record does not match what was last written (records at the end were removed or changed)')
        heads[name] = prev
    return {'ok': not problems, 'chains': len(names), 'records': records, 'problems': problems, 'heads': heads}
