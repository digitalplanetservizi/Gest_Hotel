from django.db import migrations, models
import django.db.models.deletion


def migrate_categories(apps, schema_editor):
    PriceItem = apps.get_model("hotel", "PriceItem")
    ExtraCategory = apps.get_model("hotel", "ExtraCategory")
    alias = schema_editor.connection.alias

    for item in PriceItem.objects.using(alias).exclude(category=""):
        category, _ = ExtraCategory.objects.using(alias).get_or_create(name=item.category)
        PriceItem.objects.using(alias).filter(pk=item.pk).update(category_ref_id=category.pk)


class Migration(migrations.Migration):
    dependencies = [("hotel", "0004_charge_consumed_at")]

    operations = [
        migrations.CreateModel(
            name="ExtraCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name", "pk"]},
        ),
        migrations.AddField(
            model_name="priceitem",
            name="category_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="price_items",
                to="hotel.extracategory",
            ),
        ),
        migrations.RunPython(migrate_categories, migrations.RunPython.noop),
        migrations.RemoveField(model_name="priceitem", name="category"),
        migrations.RenameField(model_name="priceitem", old_name="category_ref", new_name="category"),
        migrations.RemoveField(model_name="priceitem", name="code"),
    ]
