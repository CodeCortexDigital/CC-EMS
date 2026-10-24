"""Student numbers and employee IDs.

They are also the login names for the student and staff portals, so they must be unique across every school on the system.
To make that automatic, each school's own code (three letters, for example ``GVS``) is part of every ID it creates:
``GVS-STU0001`` for a student and ``GVS-EMP-0001`` for a staff member. Each school numbers from 1 on its own, and a number that
is already used is refused with a clear message instead of being renumbered behind the user's back.

IDs that already exist (created before this, or loaded from a data pack) are left exactly as they are.
"""
from __future__ import annotations

import re

from .context import get_current_tenant


def tenant_of(serializer):
    """The school a request belongs to. The thread-wide "current school" is not always set while a serializer validates, so read it
    from the request first."""
    from .scoping import tenant_for_request

    request = serializer.context.get('request')
    return tenant_for_request(request) if request is not None else get_current_tenant()


def school_prefix(tenant=None) -> str:
    t = tenant or get_current_tenant()
    return (getattr(t, 'tenant_code', '') or '').strip().upper() if t else ''


def with_prefix(raw: str, tenant=None) -> str:
    """The ID as the school will store it: its own code in front, unless it is already there."""
    raw = (raw or '').strip()
    prefix = school_prefix(tenant)
    if not raw or not prefix:
        return raw
    return raw if raw.upper().startswith(f'{prefix}-') else f'{prefix}-{raw}'


def next_id(model, field: str, stem: str, tenant=None, width: int = 4) -> str:
    """The next free ID for this school, for example ``GVS-STU0007``. Looks across all schools, so it can never collide."""
    prefix = school_prefix(tenant)
    head = f'{prefix}-{stem}' if prefix else stem
    taken = model._base_manager.filter(**{f'{field}__startswith': head}).values_list(field, flat=True)
    numbers = []
    for value in taken:
        m = re.fullmatch(re.escape(head) + r'(\d+)', value or '')
        if m:
            numbers.append(int(m.group(1)))
    n = (max(numbers) if numbers else 0) + 1
    while model._base_manager.filter(**{field: f'{head}{n:0{width}d}'}).exists():
        n += 1
    return f'{head}{n:0{width}d}'
