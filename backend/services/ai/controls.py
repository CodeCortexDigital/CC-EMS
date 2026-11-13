"""Three school-level controls on AI use, from the MEXT generative-AI guidelines and the APPI:

  require_user_notice   each person reads and accepts the AI use notice before their first use
  require_training      no AI use while the school has no record of the provider's no-training confirmation
  mask_names            student names are replaced by tokens before anything is sent to the AI provider

All three are off until the school switches them on (a school's existing use must not stop without warning). They only matter
while a provider is configured: with no provider nothing leaves the server. The checks are made on the server."""
from __future__ import annotations

import re

from django.utils import timezone

from .llm import get_llm_client

CONTROL_KEYS = ('require_user_notice', 'require_training', 'mask_names')
USER_NOTICE_VERSION = 1
USER_NOTICE_TEXT = (
    'Before you use the AI assistant: what you type, and the school information it looks up to answer you, is sent to an outside AI '
    'provider. Do not type names, ID numbers or health details of students unless you need to; names are replaced before they are sent '
    'when your school has switched that on. The AI can be wrong. Everything it writes is a draft that you check before you use it; you '
    'remain responsible for it. Your questions and its answers are kept in the school\'s records and can be reviewed by the school. '
    'The provider has confirmed in writing that what is sent is not used to train its models (the school keeps that record).'
)


class AINotReady(Exception):
    """AI use is refused until something is done. `code` tells the screen what: ai_notice_required, ai_training_required."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def controls(school) -> dict:
    saved = ((getattr(school, 'settings_json', None) or {}).get('ai_controls') or {}) if school else {}
    return {k: bool(saved.get(k)) for k in CONTROL_KEYS}


def user_accepted(user, school) -> bool:
    from .models import AIUserNotice

    if user is None or school is None:
        return False
    return AIUserNotice.objects.filter(tenant=school, user=user, version__gte=USER_NOTICE_VERSION).exists()


def check_ready(ctx) -> None:
    """Refuse AI use that would break a control the school switched on. Called before every AI request that reaches a provider."""
    school = getattr(ctx, 'tenant', None)
    if school is None or get_llm_client() is None:
        return
    on = controls(school)
    if on['require_training']:
        from .settings_api import _training_payload, training_confirmation

        if not training_confirmation(school) or _training_payload(school, get_llm_client())['provider_mismatch']:
            raise AINotReady('AI is paused: this school has no record that the AI provider does not train on what is sent. '
                             'Ask an administrator to record it under AI settings.', 'ai_training_required')
    if on['require_user_notice'] and not user_accepted(ctx.user, school):
        raise AINotReady('Please read and accept the AI use notice before using AI.', 'ai_notice_required')


def accept_user_notice(user, school):
    from .models import AIUserNotice

    row, _ = AIUserNotice.objects.update_or_create(
        tenant=school, user=user, defaults={'version': USER_NOTICE_VERSION, 'accepted_at': timezone.now()})
    return row


# ---------------------------------------------------------------------------------------------------------------------------
# Student names
# ---------------------------------------------------------------------------------------------------------------------------

MAX_NAMES = 6000
_TOKEN = re.compile(r'\[Student (\d+)\]')


class NameMask:
    """Replaces the names of the school's students with tokens ([Student 1]) in text going to the provider and puts the names back in
    the answer. The same name always gets the same token within one request. Names are matched with or without a space between
    the family and given name (山田 太郎 / 山田太郎). A name written in another way (only the given name, a nickname) is not caught."""

    def __init__(self, names):
        names = sorted({' '.join(str(n).split()) for n in names if n and len(str(n).strip()) >= 2}, key=lambda n: -len(n))[:MAX_NAMES]
        self._names = {n.replace(' ', '').lower(): n for n in names}
        self._pattern = None
        if names:
            parts = (r'\s*'.join(re.escape(p) for p in n.split(' ')) for n in names)
            self._pattern = re.compile('|'.join(parts), re.IGNORECASE)
        self.tokens: dict[str, str] = {}          # token -> real name
        self._by_name: dict[str, str] = {}

    @classmethod
    def for_school(cls, ctx):
        from services.education.students.models import Student

        qs = ctx.scope_tenant(Student.objects.all(), 'tenant')
        return cls(qs.values_list('full_name', flat=True)[:MAX_NAMES])

    @property
    def count(self) -> int:
        return len(self.tokens)

    def _token(self, matched: str) -> str:
        real = self._names.get(re.sub(r'\s+', '', matched).lower(), matched)
        if real not in self._by_name:
            tok = f'[Student {len(self._by_name) + 1}]'
            self._by_name[real] = tok
            self.tokens[tok] = real
        return self._by_name[real]

    def mask(self, text):
        if not isinstance(text, str) or not text or self._pattern is None:
            return text
        return self._pattern.sub(lambda m: self._token(m.group(0)), text)

    def mask_data(self, value):
        """Mask every string inside tool output (dicts, lists)."""
        if isinstance(value, dict):
            return {k: self.mask_data(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.mask_data(v) for v in value]
        return self.mask(value)

    def restore(self, text):
        if not isinstance(text, str) or not self.tokens:
            return text
        return _TOKEN.sub(lambda m: self.tokens.get(m.group(0), m.group(0)), text)

    def restore_data(self, value):
        if isinstance(value, dict):
            return {k: self.restore_data(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.restore_data(v) for v in value]
        return self.restore(value)

    def leaked(self, text) -> bool:
        """True when a real student name appears in text that should only contain tokens (the model's own reply)."""
        return bool(isinstance(text, str) and self._pattern is not None and self._pattern.search(text))

    def streamer(self):
        return _Streamer(self)


class _Streamer:
    """Puts names back into streamed text. A token can arrive in pieces, so text from an open '[' is held until it closes."""

    def __init__(self, mask: NameMask):
        self._mask, self._held = mask, ''

    def feed(self, text: str) -> str:
        self._held += text
        cut = self._held.rfind('[')
        if cut != -1 and ']' not in self._held[cut:] and len(self._held) - cut < 16:
            out, self._held = self._held[:cut], self._held[cut:]
        else:
            out, self._held = self._held, ''
        return self._mask.restore(out)

    def flush(self) -> str:
        out, self._held = self._held, ''
        return self._mask.restore(out)
