from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("education_academics", "0026_guess_grade_levels"),
    ]

    operations = [
        migrations.AddField(
            model_name="classsubject",
            name="periods_per_week",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
