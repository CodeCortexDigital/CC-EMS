"""How pressing a message from a family reads: normal, frustrated or urgent.

Deliberately a plain keyword check, not an AI call: it runs on every message, must be instant and free, and
must never send a family's words to a provider just to sort an inbox. It only decides the order staff see
messages in; nobody is told a message was flagged, and the label is the only thing stored.
"""
from __future__ import annotations

import re

URGENT = (
    'urgent', 'emergency', 'asap', 'immediately', 'right now', 'ambulance', 'hospital', 'injured', 'bleeding',
    'unsafe', 'bullied', 'bullying', 'hit by', 'hurt', 'threat', 'missing child', 'not arrived', "hasn't arrived",
    'has not arrived', 'allergic reaction', 'cannot reach', "can't reach", 'pick up now', 'collect now',
)
FRUSTRATED = (
    'unacceptable', 'disappointed', 'frustrated', 'fed up', 'angry', 'furious', 'ridiculous', 'complain',
    'complaint', 'third time', 'again and again', 'no one replied', 'nobody replied', 'no response', 'still waiting',
    'never responded', 'not happy', 'unhappy', 'outraged', 'terrible', 'worst',
)
_ORDER = {'normal': 0, 'frustrated': 1, 'urgent': 2}


def classify(subject: str, body: str) -> str:
    text = f'{subject} {body}'.lower()
    if any(k in text for k in URGENT):
        return 'urgent'
    shouting = len(re.findall(r'\b[A-Z]{4,}\b', body or '')) >= 3 or (body or '').count('!!') >= 1
    if shouting or any(k in text for k in FRUSTRATED):
        return 'frustrated'
    return 'normal'


def worst(labels) -> str:
    """The most pressing label in a set of messages ('normal' when there are none)."""
    return max((str(x) for x in labels), key=lambda x: _ORDER.get(x, 0), default='normal')
