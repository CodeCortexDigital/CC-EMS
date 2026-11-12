"""The 調査書: preview from the 指導要録, and the principal's issue to a named high school (a saved copy, audited).

Anyone who may read the record can preview it; only an administrator (the principal) can issue it, and only when all three years carry the principal's seal.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.education.students.access import audit_read, audit_write

from . import chosasho
from .models import ChosashoIssue
from .views import RecordStaff, _record_for, _role


def _issue(i: ChosashoIssue, full: bool = False) -> dict:
    out = {'id': str(i.pk), 'issued_to': i.issued_to, 'note': i.note, 'issued_at': i.issued_at.isoformat(),
           'issued_by': (getattr(i.issued_by, 'full_name', '') or getattr(i.issued_by, 'email', '')) if i.issued_by_id else ''}
    if full:
        out['snapshot'] = i.snapshot
    return out


@api_view(['GET', 'POST'])
@permission_classes([RecordStaff])
def chosasho_view(request, pk):
    """GET: the 調査書 as it would be issued now, and the issues made so far. POST ``{issued_to, note?}`` (administrator): issue it."""
    record, error = _record_for(request, pk)
    if error:
        return error
    if record.level != chosasho.LEVEL:
        return Response({'detail': 'A 調査書 is made from a junior high school record.'}, status=status.HTTP_400_BAD_REQUEST)
    data = chosasho.assemble(record)
    if request.method == 'POST':
        if _role(request.user) != 'admin':
            return Response({'detail': 'Only the principal (an administrator) can issue a 調査書.'}, status=status.HTTP_403_FORBIDDEN)
        issued_to = str((request.data or {}).get('issued_to') or '').strip()
        if not issued_to:
            return Response({'issued_to': 'Write which school it is for (提出先).'}, status=status.HTTP_400_BAD_REQUEST)
        if not data['ready']:
            return Response({'detail': 'It cannot be issued yet.', 'problems': data['problems']}, status=status.HTTP_409_CONFLICT)
        issue = ChosashoIssue.objects.create(record=record, issued_to=issued_to[:200], note=str((request.data or {}).get('note') or '')[:300],
                                             snapshot=data, issued_by=request.user)
        audit_write(request, 'CREATE', 'records/chosasho-issue', issue.pk, {'record': str(record.pk), 'issued_to': issue.issued_to})
        return Response(_issue(issue, full=True), status=status.HTTP_201_CREATED)
    audit_read(request, 'records/chosasho', record.pk)
    return Response({'chosasho': data, 'issues': [_issue(i) for i in record.chosasho_issues.select_related('issued_by')]})


@api_view(['GET'])
@permission_classes([RecordStaff])
def chosasho_issue(request, pk, issue_id):
    """One issued 調査書, exactly as it was issued."""
    record, error = _record_for(request, pk)
    if error:
        return error
    issue = record.chosasho_issues.select_related('issued_by').filter(pk=issue_id).first()
    if issue is None:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    audit_read(request, 'records/chosasho-issue', issue.pk)
    return Response(_issue(issue, full=True))
