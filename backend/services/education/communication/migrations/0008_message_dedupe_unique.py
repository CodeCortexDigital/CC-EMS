from django.db import migrations, models


def separate_old_duplicates(apps, schema_editor):
    """Rows saved before the rule existed may share a key; keep the first and mark the others so the rule can be added."""
    Message = apps.get_model('education_communication', 'Message')
    seen = set()
    for row in Message._base_manager.exclude(dedupe_key='').order_by('created_at').only('id', 'tenant_id', 'dedupe_key'):
        key = (row.tenant_id, row.dedupe_key)
        if key in seen:
            Message._base_manager.filter(pk=row.pk).update(dedupe_key=f'{row.dedupe_key[:150]}#older-duplicate-{row.pk}')
        seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('education_communication', '0007_urgency_and_translation_cache'),
    ]

    operations = [
        migrations.RunPython(separate_old_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='message',
            constraint=models.UniqueConstraint(condition=models.Q(('dedupe_key', ''), _negated=True), fields=('tenant', 'dedupe_key'), name='uniq_message_dedupe_per_school'),
        ),
    ]
