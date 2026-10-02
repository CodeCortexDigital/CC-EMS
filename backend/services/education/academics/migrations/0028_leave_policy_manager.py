import uuid

import django.db.models.deletion
from django.db import migrations, models

LEAVE_TYPES = [('sick', 'Sick'), ('casual', 'Casual'), ('annual', 'Annual'), ('maternity', 'Maternity'),
               ('emergency', 'Emergency'), ('personal', 'Personal day'), ('bereavement', 'Bereavement'),
               ('jury', 'Jury duty'), ('professional', 'Professional development'), ('unpaid', 'Unpaid'),
               ('other', 'Other')]
STATUSES = [('pending', 'Pending'), ('recommended', 'Recommended by manager'), ('approved', 'Approved'),
            ('rejected', 'Rejected'), ('cancelled', 'Cancelled')]


class Migration(migrations.Migration):

    dependencies = [
        ('core_tenants', '0003_assign_unowned_rows'),
        ('education_academics', '0027_classsubject_periods_per_week'),
    ]

    operations = [
        migrations.AddField(
            model_name='teacher', name='manager',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='direct_reports', to='education_academics.teacher'),
        ),
        migrations.AlterField(
            model_name='teacherleave', name='leave_type',
            field=models.CharField(choices=LEAVE_TYPES, default='sick', max_length=20),
        ),
        migrations.AlterField(
            model_name='teacherleave', name='status',
            field=models.CharField(choices=STATUSES, default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='teacherleave', name='day_part',
            field=models.CharField(choices=[('full', 'Full day'), ('am', 'Morning only'), ('pm', 'Afternoon only')],
                                   default='full', help_text='Half-day leave: only for a single-day request',
                                   max_length=4),
        ),
        migrations.AddField(model_name='teacherleave', name='recommended_by',
                            field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='teacherleave', name='decided_by',
                            field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='teacherleave', name='decided_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='teacherleave', name='decision_note',
                            field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='leavebalance', name='personal_entitlement',
                            field=models.IntegerField(default=0, help_text='Personal days allowed per year')),
        migrations.AddField(model_name='leavebalance', name='bereavement_entitlement',
                            field=models.IntegerField(default=0, help_text='Bereavement days allowed per year')),
        migrations.AddField(model_name='leavebalance', name='jury_entitlement',
                            field=models.IntegerField(default=0, help_text='Jury duty days allowed per year')),
        migrations.AddField(model_name='leavebalance', name='professional_entitlement',
                            field=models.IntegerField(default=0, help_text='Professional development days allowed per year')),
        migrations.AddField(model_name='leavebalance', name='carried_over_days',
                            field=models.IntegerField(default=0, help_text='Unused annual days brought in from last year')),
        migrations.CreateModel(
            name='LeavePolicy',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('skip_weekends', models.BooleanField(default=True, help_text='Do not count non-working days against the balance')),
                ('skip_holidays', models.BooleanField(default=True, help_text='Do not count school holidays and closures')),
                ('two_step_approval', models.BooleanField(default=False, help_text='A manager or HR recommends first, then an administrator gives final approval')),
                ('carry_over_max_days', models.PositiveSmallIntegerField(default=0, help_text='Most unused annual-leave days that may move into the next year')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                             related_name='+', to='core_tenants.school')),
            ],
        ),
        migrations.AddConstraint(
            model_name='leavepolicy',
            constraint=models.UniqueConstraint(fields=('tenant',), name='uniq_leave_policy_per_school'),
        ),
    ]
