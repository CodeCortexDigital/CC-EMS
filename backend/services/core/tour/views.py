"""Remember who has seen the guided tour. A person can only read and change their own progress."""
import re

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TourProgress

TOUR_NAME = re.compile(r'^[a-z][a-z0-9_-]{0,39}$')


def _payload(rows):
    return {'tours': {r.tour: {'version': r.version, 'status': r.status} for r in rows}}


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def progress(request):
    """GET: my progress. POST {tour, version, status}: finished or skipped. DELETE ?tour=: forget it so it shows again."""
    if request.method == 'GET':
        return Response(_payload(TourProgress.objects.filter(user=request.user)))

    if request.method == 'DELETE':
        tour = str(request.query_params.get('tour') or '')
        qs = TourProgress.objects.filter(user=request.user)
        TourProgress.objects.filter(pk__in=qs.filter(tour=tour).values('pk') if tour else qs.values('pk')).delete()
        return Response(_payload(TourProgress.objects.filter(user=request.user)))

    tour, version, outcome = str(request.data.get('tour') or ''), request.data.get('version', 1), request.data.get('status')
    if not TOUR_NAME.match(tour):
        return Response({'error': 'Say which tour.'}, status=status.HTTP_400_BAD_REQUEST)
    if outcome not in ('completed', 'skipped'):
        return Response({'error': 'Status must be completed or skipped.'}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= 1000:
        return Response({'error': 'Version must be a whole number.'}, status=status.HTTP_400_BAD_REQUEST)
    TourProgress.objects.update_or_create(user=request.user, tour=tour, defaults={'version': version, 'status': outcome})
    return Response(_payload(TourProgress.objects.filter(user=request.user)), status=status.HTTP_200_OK)
