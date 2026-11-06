"""Saving and loading the risk model files safely.

A pickle file can run code when it is loaded, so a model file that someone swapped on disk would run on the server. Every model is therefore saved
with a signature (HMAC-SHA256 with the server's secret key, in a ``.sig`` file next to it) and is loaded only when the signature matches. A file
with no signature, or the wrong one, is not loaded: the caller trains a fresh model instead.

This protects against a file changed or dropped in by someone who can write to the folder but does not hold the key. It is not a full model
registry: someone who can read the key and write the folder can still sign a file.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import pickle


class ModelFileNotTrusted(Exception):
    pass


def _key() -> bytes:
    key = os.environ.get('MODEL_SIGNING_KEY') or ''
    if not key:
        try:
            from django.conf import settings
            key = getattr(settings, 'MODEL_SIGNING_KEY', '') or getattr(settings, 'SECRET_KEY', '')
        except Exception:
            key = ''
    if not key:
        raise ModelFileNotTrusted('No signing key is set, so model files cannot be signed or checked.')
    return key.encode('utf-8')


def _sig_path(path: str) -> str:
    return path + '.sig'


def _sign(data: bytes) -> str:
    return hmac.new(_key(), data, hashlib.sha256).hexdigest()


def save_signed(model, path: str) -> None:
    data = pickle.dumps(model)
    with open(path, 'wb') as f:
        f.write(data)
    with open(_sig_path(path), 'w', encoding='ascii') as f:
        f.write(_sign(data))


def is_trusted(path: str) -> bool:
    """Whether the file exists and carries a signature that matches its content."""
    try:
        with open(path, 'rb') as f:
            data = f.read()
        with open(_sig_path(path), 'r', encoding='ascii') as f:
            saved = f.read().strip()
        return hmac.compare_digest(saved, _sign(data))
    except (OSError, ModelFileNotTrusted):
        return False


def load_signed(path: str):
    """Load a model only if its signature matches; otherwise raise ModelFileNotTrusted (nothing is unpickled)."""
    with open(path, 'rb') as f:
        data = f.read()
    try:
        with open(_sig_path(path), 'r', encoding='ascii') as f:
            saved = f.read().strip()
    except OSError:
        raise ModelFileNotTrusted(f'{os.path.basename(path)} has no signature, so it was not loaded.')
    if not hmac.compare_digest(saved, _sign(data)):
        raise ModelFileNotTrusted(f'{os.path.basename(path)} does not match its signature, so it was not loaded.')
    return pickle.loads(data)
