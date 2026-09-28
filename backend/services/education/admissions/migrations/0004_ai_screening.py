from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("education_admissions", "0003_online_admissions_reenrollment"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="ai_screening_score",
            field=models.IntegerField(blank=True, null=True,
                                      help_text="0-100, how well the application matches the school's admission criteria"),
        ),
        migrations.AddField(
            model_name="application",
            name="ai_screening_summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="application",
            name="ai_screened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
