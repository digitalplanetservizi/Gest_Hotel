"""Database-level protection also covers direct ORM writes outside services."""
from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    schema_editor.execute("""
        ALTER TABLE hotel_staysegment ADD CONSTRAINT room_no_overlapping_segments
        EXCLUDE USING gist (
            room_id WITH =,
            tstzrange(arrival, departure, '[)') WITH &&
        ) WHERE (active)
    """)
    schema_editor.execute("""
        ALTER TABLE hotel_rate ADD CONSTRAINT rate_no_ambiguous_seasons
        EXCLUDE USING gist (
            room_type WITH =,
            board WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        ) WHERE (is_active)
    """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("ALTER TABLE hotel_staysegment DROP CONSTRAINT room_no_overlapping_segments")
        schema_editor.execute("ALTER TABLE hotel_rate DROP CONSTRAINT rate_no_ambiguous_seasons")


class Migration(migrations.Migration):
    dependencies = [("hotel", "0001_initial")]
    operations = [migrations.RunPython(install, uninstall)]
