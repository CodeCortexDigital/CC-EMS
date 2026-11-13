"""An outside time stamp for the audit chain (RFC 3161).

Only the 32-byte hash of the newest record leaves the server, never any data. The time-stamping authority signs "this hash existed at
this time" and sends back a token, which is kept. The token can be checked with the authority's certificate using standard tools:

    openssl ts -verify -in anchor.tsr -digest <hash> -sha256 -CAfile authority-chain.pem

Set TIMESTAMP_AUTHORITY_URL (a service the school or its board trusts) to turn this on. Nothing is sent while it is empty.
"""
from __future__ import annotations

import urllib.request

from django.conf import settings

from .models import AuditChainHead, AuditLog, ChainAnchor

# SEQUENCE { SEQUENCE { sha256, NULL }, OCTET STRING (32 bytes) ... } up to the digest itself
_SHA256_IMPRINT = bytes.fromhex('3031300d060960864801650304020105000420')


class AnchorError(Exception):
    pass


def authority() -> str:
    return (getattr(settings, 'TIMESTAMP_AUTHORITY_URL', '') or '').strip()


def build_request(digest_hex: str) -> bytes:
    """A TimeStampReq (DER) for a SHA-256 digest: version 1, the digest, and certReq TRUE so the reply carries the certificate."""
    digest = bytes.fromhex(digest_hex)
    if len(digest) != 32:
        raise AnchorError('A SHA-256 hash is 32 bytes.')
    body = bytes.fromhex('020101') + _SHA256_IMPRINT + digest + bytes.fromhex('0101ff')
    return b'\x30' + bytes([len(body)]) + body


def _skip_header(data: bytes, at: int) -> int:
    """Position of the content of the DER element that starts at `at`."""
    length = data[at + 1]
    return at + 2 if length < 0x80 else at + 2 + (length & 0x7F)


def check_reply(reply: bytes, digest_hex: str) -> None:
    """A light check that the reply is a granted answer for this hash. It does not check the signature (see the module note)."""
    try:
        if len(reply) < 40 or reply[0] != 0x30:
            raise AnchorError('The time-stamping authority sent something that is not a time stamp reply.')
        status_info = _skip_header(reply, 0)               # TimeStampResp: SEQUENCE { PKIStatusInfo SEQUENCE { status INTEGER ...
        if reply[status_info] != 0x30:
            raise AnchorError('The reply could not be read.')
        integer = _skip_header(reply, status_info)
        if reply[integer] != 0x02 or reply[integer + 1] != 1:
            raise AnchorError('The reply could not be read.')
        if reply[integer + 2] not in (0, 1):                # 0 granted, 1 granted with modifications
            raise AnchorError(f'The authority refused the request (status {reply[integer + 2]}).')
    except IndexError as exc:
        raise AnchorError('The reply could not be read.') from exc
    if bytes.fromhex(digest_hex) not in reply:
        raise AnchorError('The reply is for a different hash.')


def _post(url: str, request: bytes) -> bytes:
    req = urllib.request.Request(url, data=request, headers={'Content-Type': 'application/timestamp-query'}, method='POST')
    with urllib.request.urlopen(req, timeout=20) as r:          # noqa: S310 (the address is set by the operator)
        return r.read()


def anchor(chain: str) -> ChainAnchor:
    """Time-stamp the newest hash of one chain. Raises AnchorError when it is not set up, there is nothing to stamp, or the authority fails."""
    url = authority()
    if not url:
        raise AnchorError('No time-stamping authority is set (TIMESTAMP_AUTHORITY_URL).')
    head = AuditChainHead.objects.filter(chain=chain).first()
    if head is None or not head.last_hash:
        raise AnchorError('There are no records to time-stamp yet.')
    last = ChainAnchor.objects.filter(chain=chain).order_by('-seq').first()
    if last and last.seq == head.last_seq and last.head_hash == head.last_hash:
        return last                                            # already stamped; nothing new since
    try:
        reply = _post(url, build_request(head.last_hash))
    except OSError as exc:
        raise AnchorError(f'The time-stamping authority could not be reached: {exc}') from exc
    check_reply(reply, head.last_hash)
    school = None
    if chain != 'platform':
        from services.core.tenants.models import School

        school = School.objects.filter(pk=chain).first()
    return ChainAnchor.objects.create(school=school, chain=chain, seq=head.last_seq, head_hash=head.last_hash, authority=url, token=reply)


def check(chain: str | None = None) -> list[str]:
    """For every kept time stamp: the record at that position must still have the stamped hash. Returns what does not."""
    problems = []
    rows = ChainAnchor.objects.all() if not chain else ChainAnchor.objects.filter(chain=chain)
    for a in rows.order_by('chain', 'seq'):
        row = AuditLog._base_manager.filter(chain=a.chain, seq=a.seq).exclude(entry_hash='').first()
        if row is None or row.entry_hash != a.head_hash:
            problems.append(f'{a.chain}: record {a.seq}, time-stamped by an outside authority on {a.created_at:%Y-%m-%d %H:%M} UTC, is no longer the same '
                            f'(the history before that time was rewritten or removed)')
    return problems
