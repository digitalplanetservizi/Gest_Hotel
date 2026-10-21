from django.db import migrations, models
from django.db.models.functions import Lower


def merge_case_duplicates(apps, schema_editor):
    ExtraCategory = apps.get_model("hotel", "ExtraCategory")
    PriceItem = apps.get_model("hotel", "PriceItem")
    alias = schema_editor.connection.alias
    canonical_by_name = {}

    for category in ExtraCategory.objects.using(alias).order_by("pk"):
        key = category.name.strip().casefold()
        canonical = canonical_by_name.get(key)
        if canonical:
            PriceItem.objects.using(alias).filter(category_id=category.pk).update(category_id=canonical.pk)
            category.delete(using=alias)
        else:
            canonical_by_name[key] = category


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("hotel", "0005_extra_categories_and_database_catalogue_ids")]

    operations = [
        migrations.RunPython(merge_case_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="extracategory",
            constraint=models.UniqueConstraint(
                Lower("name"), name="extra_category_name_case_insensitive_unique"
            ),
        ),
    ]
