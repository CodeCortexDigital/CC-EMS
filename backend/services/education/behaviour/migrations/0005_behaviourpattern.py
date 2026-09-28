import uuid

import django.db.models.deletion
from django.db import migrations, models

import services.core.tenants.mixins


class Migration(migrations.Migration):

    dependencies = [
        ("behaviour", "0004_backfill_tenants"),
        ("education_students", "0010_backfill_households"),
        ("core_tenants", "0003_assign_unowned_rows"),
    ]

    operations = [
        migrations.CreateModel(
            name="BehaviourPattern",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("pattern_type", models.CharField(choices=[
                    ("escalating", "Escalating frequency"),
                    ("repeated_category", "Repeated concern"),
                    ("high_severity", "High-severity incident"),
                    ("frequent", "Frequent incidents"),
                ], max_length=20)),
                ("severity", models.CharField(choices=[
                    ("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical"),
                ], max_length=10)),
                ("window_days", models.PositiveSmallIntegerField(default=30)),
                ("incident_count", models.PositiveSmallIntegerField(default=0)),
                ("summary", models.TextField(blank=True, default="")),
                ("recommended_actions", models.JSONField(blank=True, default=list)),
                ("source", models.CharField(default="ai", max_length=10)),
                ("notified_count", models.PositiveSmallIntegerField(default=0)),
                ("is_resolved", models.BooleanField(default=False)),
                ("detected_at", models.DateTimeField(auto_now_add=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="behaviour_patterns", to="education_students.student")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                            related_name="%(app_label)s_%(class)s_set", to="core_tenants.school")),
            ],
            options={
                "ordering": ["-detected_at"],
            },
            bases=(services.core.tenants.mixins.SchoolAliasMixin, models.Model),
        ),
    ]
