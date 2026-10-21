from django.db import migrations, models
from django.db.models import F


def backfill_consumption_time(apps, schema_editor):
    # Existing records have no independent consumption time. Preserve their
    # known registration timestamp; do not invent a date or alter the audit.
    charge = apps.get_model("hotel", "Charge")
    charge.objects.using(schema_editor.connection.alias).filter(kind="extra", consumed_at__isnull=True).update(consumed_at=F("created_at"))


class Migration(migrations.Migration):
    dependencies = [("hotel", "0003_user_user_email_case_insensitive_unique")]
    operations = [
        migrations.AddField(
            model_name="charge",
            name="consumed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_consumption_time, migrations.RunPython.noop),
    ]
