from django.conf import settings
from django.db import models


class TourProgress(models.Model):
    """Whether a person has finished or skipped a guided tour. The tour's steps live in the app, per role; this only
    remembers the person's answer so the tour is not shown again until they ask for it or the tour itself changes."""
    STATUSES = [('completed', 'Finished'), ('skipped', 'Skipped')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tour_progress')
    tour = models.CharField(max_length=40, help_text='Which tour, for example "admin" or "parent"')
    version = models.PositiveSmallIntegerField(default=1, help_text='A new version of a tour is shown once more')
    status = models.CharField(max_length=10, choices=STATUSES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tour']
        constraints = [models.UniqueConstraint(fields=['user', 'tour'], name='uniq_user_tour')]
