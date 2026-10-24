"""The school's own documents as something the assistant can look things up in (retrieval-augmented answers).

A document is split into short passages. A question is matched to the best passages with a keyword ranking (BM25), so it
needs no extra service and works without an AI provider. The passages are given to the assistant as reference text, with
their document titles so the answer can name its sources.

Which documents someone may be shown is decided here, on the server, from their role and school:
``everyone`` -> every role, ``staff`` -> administrators, accountants and teachers, ``admin`` -> administrators only.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from django.db import transaction

from .models import KnowledgeChunk, KnowledgeDocument

CHUNK_CHARS = 900
OVERLAP_CHARS = 150
MAX_DOCUMENT_CHARS = 200_000
MAX_PASSAGE_CHARS = 700
STOP_WORDS = frozenset(
    'a an and are as at be by for from has have how i if in is it its of on or our that the their this to was we what when where which who '
    'will with you your can do does my me'.split()
)
AUDIENCE_ROLES = {
    'everyone': ('admin', 'accountant', 'teacher', 'student', 'parent'),
    'staff': ('admin', 'accountant', 'teacher'),
    'admin': ('admin',),
}


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or '').lower())
    return [w[:-1] if len(w) > 3 and w.endswith('s') and not w.endswith('ss') else w for w in words if w not in STOP_WORDS and len(w) > 1]


def split_passages(text: str) -> list[str]:
    """Paragraph-aware pieces of about CHUNK_CHARS, each starting a little before the last one ended."""
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', (text or '').replace('\r\n', '\n')) if p.strip()]
    pieces, current = [], ''
    for para in paragraphs:
        while len(para) > CHUNK_CHARS:                      # one very long paragraph: cut at a sentence or space
            cut = max(para.rfind('. ', 0, CHUNK_CHARS), para.rfind(' ', 0, CHUNK_CHARS))
            cut = cut + 1 if cut > CHUNK_CHARS // 2 else CHUNK_CHARS
            pieces.append(para[:cut].strip())
            para = para[max(cut - OVERLAP_CHARS, 1):].strip()
        if current and len(current) + len(para) + 2 > CHUNK_CHARS:
            pieces.append(current)
            current = current[-OVERLAP_CHARS:].split(' ', 1)[-1] + '\n\n' + para
        else:
            current = f'{current}\n\n{para}' if current else para
    if current.strip():
        pieces.append(current.strip())
    return [p for p in pieces if p]


@transaction.atomic
def index_document(doc: KnowledgeDocument) -> int:
    """(Re)build the passages of a document. Returns how many there are."""
    KnowledgeChunk.objects.filter(document=doc).delete()
    rows = []
    for ordinal, text in enumerate(split_passages(doc.body[:MAX_DOCUMENT_CHARS])):
        counts = Counter(tokens(text))
        rows.append(KnowledgeChunk(document=doc, ordinal=ordinal, text=text, terms=dict(counts), length=sum(counts.values())))
    KnowledgeChunk.objects.bulk_create(rows)
    return len(rows)


def documents_for(role, tenant):
    """The active documents this role may be shown in this school (never another school's)."""
    audiences = [a for a, roles in AUDIENCE_ROLES.items() if role in roles]
    return KnowledgeDocument.all_objects.filter(tenant=tenant, is_active=True, audience__in=audiences)


def search(query: str, *, role, tenant, limit: int = 4) -> list[dict]:
    """The best passages for a question: [{document_id, title, ordinal, text, score}], best first."""
    words = list(dict.fromkeys(tokens(query)))
    if not words:
        return []
    chunks = list(KnowledgeChunk._base_manager.filter(document__in=documents_for(role, tenant)).select_related('document'))
    if not chunks:
        return []
    n = len(chunks)
    average = (sum(c.length for c in chunks) / n) or 1
    document_frequency = {w: sum(1 for c in chunks if w in c.terms) for w in words}
    k1, b = 1.5, 0.75
    scored = []
    for c in chunks:
        score = 0.0
        for w in words:
            tf = c.terms.get(w, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - document_frequency[w] + 0.5) / (document_frequency[w] + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (c.length or 1) / average))
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda pair: -pair[0])
    return [{'document_id': str(c.document_id), 'title': c.document.title, 'ordinal': c.ordinal + 1,
             'text': c.text[:MAX_PASSAGE_CHARS], 'score': round(score, 3)} for score, c in scored[:limit]]
