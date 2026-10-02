"""Turn the old week-long automatic substitutions into dated cover.

Each old row said "relief teacher X covers this timetable entry for the whole leave". For every future date in that leave
that falls on the entry's weekday, create a filled cover request. Past dates are left alone. Old rows stay in place, unused.
"""
from datetime import date, timedelta

from django.db import migrations

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def move(apps, schema_editor):
    Old = apps.get_model('education_academics', 'TimetableSubstitution')
    Request = apps.get_model('education_hr', 'SubstituteRequest')
    today = date.today()
    for sub in Old.objects.select_related('leave', 'original_entry__class_subject__subject', 'original_entry__class_subject__class_ref',
                                         'original_entry__period', 'original_entry__teacher'):
        leave, entry = sub.leave, sub.original_entry
        if leave.status != 'approved' or leave.teacher_id is None:
            continue
        d = max(leave.start_date, today)
        while d <= leave.end_date:
            if WEEKDAYS[d.weekday()] == entry.day_of_week and not Request.objects.filter(
                    requester_id=entry.teacher_id, date=d, period_id=entry.period_id).exclude(status='cancelled').exists():
                cs = entry.class_subject
                Request.objects.create(
                    tenant_id=leave.tenant_id, requester_id=entry.teacher_id, date=d, entry=entry, period=entry.period, leave=leave,
                    status='filled', substitute_id=sub.relief_teacher_id, filled_how='auto',
                    description=f'{cs.class_ref.name} {cs.subject.name}'[:255], reason='Approved leave')
            d += timedelta(days=1)


class Migration(migrations.Migration):

    dependencies = [
        ('education_hr', '0002_cover_leave_override'),
        ('education_academics', '0031_timetable_snapshot'),
    ]

    operations = [
        migrations.RunPython(move, migrations.RunPython.noop),
    ]
