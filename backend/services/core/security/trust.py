"""Trust evidence for the school's board: the off-site time stamp of the audit chain (``/security/timestamps/``).

    GET   timestamps/                 the school's chain check, the time-stamping setting and the stamps kept so far
    POST  timestamps/                 stamp the newest hash now (administrator)
    GET   timestamps/<id>/            download one stamp's signed reply (.tsr) to check it with openssl
"""
from __future__ import annotations

import csv

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.core.audit import anchors, chain
from services.core.audit.models import AuditChainHead, ChainAnchor
from services.education.students.access import audit_write

from . import assessment
from .api import _admin_school


def _payload(a: ChainAnchor) -> dict:
    return {'id': str(a.id), 'seq': a.seq, 'hash': a.head_hash, 'authority': a.authority, 'at': a.created_at.isoformat()}


def _state(school) -> dict:
    name = str(school.pk)
    head = AuditChainHead.objects.filter(chain=name).first()
    rows = list(ChainAnchor.objects.filter(chain=name)[:50])
    check = chain.verify(name)
    return {
        'enabled': bool(anchors.authority()), 'authority': anchors.authority(),
        'records': head.last_seq if head else 0, 'newest_hash': head.last_hash if head else '',
        'chain': {'ok': check['ok'], 'problems': check['problems'][:5]},
        'stamps': [_payload(a) for a in rows],
        'up_to_date': bool(rows and head and rows[0].seq == head.last_seq),
        'how_to_check': 'openssl ts -verify -in stamp.tsr -digest <hash> -sha256 -CAfile authority-chain.pem',
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def timestamps(request):
    school, error = _admin_school(request)
    if error:
        return error
    if request.method == 'POST':
        try:
            a = anchors.anchor(str(school.pk))
        except anchors.AnchorError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        audit_write(request, 'CREATE', 'security/chain-timestamp', a.id, {'seq': a.seq, 'authority': a.authority})
    return Response(_state(school))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def timestamp_token(request, anchor_id):
    school, error = _admin_school(request)
    if error:
        return error
    a = ChainAnchor.objects.filter(pk=anchor_id, chain=str(school.pk)).first()
    if a is None:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    r = HttpResponse(bytes(a.token), content_type='application/timestamp-reply')
    r['Content-Disposition'] = f'attachment; filename="chain-{a.seq}.tsr"'
    r['X-Chain-Hash'] = a.head_hash
    return r


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def self_assessment(request):
    """GET: the school's self-assessment (``?export=csv`` to download). PUT ``{key, answer: yes|partly|no|"", note}``: answer a line only the school can answer."""
    school, error = _admin_school(request)
    if error:
        return error
    if request.method == 'PUT':
        d = request.data if isinstance(request.data, dict) else {}
        saved, problem = assessment.answer(school, request.user, str(d.get('key') or ''), str(d.get('answer') if d.get('answer') is not None else ''), str(d.get('note') or ''))
        if problem:
            return Response({'error': problem}, status=status.HTTP_400_BAD_REQUEST)
        audit_write(request, 'UPDATE', 'security/self-assessment', None, {'key': d.get('key'), 'answer': d.get('answer')})
    data = assessment.assessment(school)
    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="self-assessment.csv"'
        resp.write('﻿')
        w = csv.writer(resp)
        w.writerow([data['disclaimer']])
        w.writerow(['Area', 'Line', 'Status', 'Source', 'Evidence or note', 'Answered by', 'Answered at'])
        labels = {'met': 'Met', 'partly': 'Partly', 'open': 'Open'}
        for i in data['items']:
            w.writerow([i['area'], i['text'], labels[i['status']], 'System' if i['source'] == 'system' else 'School', i['evidence'], i.get('answered_by', ''), i.get('answered_at') or ''])
        return resp
    return Response(data)
