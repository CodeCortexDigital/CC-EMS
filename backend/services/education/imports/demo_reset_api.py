"""Nightly demo reset: puts the hosted demo back to its starting state so a visitor can never leave it broken.

POST /api/v1/demo/reset/  with the header  X-Demo-Reset-Token: <DEMO_RESET_TOKEN>

* Works only on a demo or staging server (APP_ENV is not production) that has DEMO_RESET_TOKEN set. Anywhere else it answers
  404, as if it did not exist, so the live site can never be reset this way.
* The reset (the same as ``setup_demo --reset``) takes a minute or two, so it runs in the background; the call answers 202 at once.
  A second call while one is running answers 409.
* A GitHub Actions job (.github/workflows/demo-reset.yml) calls it each night: Render's free plan has no scheduler.
"""
import hmac
import logging
import os
import threading

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)
_running = threading.Lock()


def _run():
    try:
        call_command('setup_demo', '--reset')
        logger.info('Demo reset finished.')
    except Exception:
        logger.exception('Demo reset failed')
    finally:
        connection.close()
        _running.release()


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def reset_demo(request):
    token = os.environ.get('DEMO_RESET_TOKEN', '').strip()
    if getattr(settings, 'APP_ENV', '') == 'production' or not token:
        return Response({'error': 'Not found.'}, status=404)
    sent = request.headers.get('X-Demo-Reset-Token', '')
    if not hmac.compare_digest(sent.encode(), token.encode()):
        return Response({'error': 'Not found.'}, status=404)
    if not _running.acquire(blocking=False):
        return Response({'status': 'already running'}, status=409)
    threading.Thread(target=_run, daemon=True).start()
    return Response({'status': 'started'}, status=202)
