import io
import json
import zipfile

from django.test import TestCase
from rest_framework.test import APIClient

from hotel import models as m


class CatalogueDeletionAndAuditTests(TestCase):
    def setUp(self):
        self.admin = m.User.objects.create_user(
            username="admin@example.it",
            email="admin@example.it",
            password="Safe-admin-password-2026",
            role="admin",
        )
        self.operator = m.User.objects.create_user(
            username="operator@example.it",
            email="operator@example.it",
            password="Safe-operator-password-2026",
            role="operator",
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.operator_client = APIClient()
        self.operator_client.force_authenticate(self.operator)

    def test_only_administrator_can_delete_a_price_item_and_the_operation_is_logged(self):
        item = m.PriceItem.objects.create(description="Late check-out", price="35.00")

        denied = self.operator_client.delete(f"/api/v1/price-items/{item.pk}/")
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(m.PriceItem.objects.filter(pk=item.pk).exists())

        deleted = self.admin_client.delete(f"/api/v1/price-items/{item.pk}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(m.PriceItem.objects.filter(pk=item.pk).exists())
        event = m.AuditEvent.objects.get(action="resource.deleted", object_type="PriceItem")
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.object_id, item.pk)
        self.assertEqual(event.data["label"], "Late check-out")
        self.assertIsNotNone(event.created_at)

    def test_category_can_be_deleted_only_when_empty_and_by_an_administrator(self):
        category = m.ExtraCategory.objects.create(name="Bar")
        m.PriceItem.objects.create(description="Caffè", category=category, price="1.50")
        blocked = self.admin_client.delete(f"/api/v1/extra-categories/{category.pk}/")
        self.assertEqual(blocked.status_code, 400)
        self.assertTrue(m.ExtraCategory.objects.filter(pk=category.pk).exists())

        empty_category = m.ExtraCategory.objects.create(name="Da rimuovere")
        denied = self.operator_client.delete(f"/api/v1/extra-categories/{empty_category.pk}/")
        self.assertEqual(denied.status_code, 403)
        deleted = self.admin_client.delete(f"/api/v1/extra-categories/{empty_category.pk}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(m.ExtraCategory.objects.filter(pk=empty_category.pk).exists())

    def test_audit_log_is_restricted_to_administrators_and_filterable_by_operator(self):
        category = m.Group.objects.create(name="Gruppo", reference_name="Referente")
        self.operator_client.patch(
            f"/api/v1/groups/{category.pk}/", {"name": "Gruppo ospiti"}, format="json"
        )
        self.assertEqual(self.operator_client.get("/api/v1/audit-events/").status_code, 403)

        result = self.admin_client.get(f"/api/v1/audit-events/?actor={self.operator.pk}")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["count"], 1)
        event = result.data["results"][0]
        self.assertEqual(event["actor"], self.operator.pk)
        self.assertEqual(event["actor_name"], self.operator.email)
        self.assertEqual(event["action"], "resource.updated")
        self.assertEqual(event["action_label"], "Configurazione modificata")
        self.assertEqual(event["object_label"], f"Gruppo #{category.pk}")
        self.assertIn("created_at", event)

    def test_administrator_can_download_a_portable_full_data_backup(self):
        item = m.PriceItem.objects.create(description="Colazione", price="12.00")

        denied = self.operator_client.get("/api/v1/backup/export/")
        self.assertEqual(denied.status_code, 403)
        response = self.admin_client.get("/api/v1/backup/export/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(archive.namelist(), ["hotel-backup.json"])
            payload = json.loads(archive.read("hotel-backup.json"))
        self.assertEqual(payload["format"], "hotel-tempio-backup")
        self.assertEqual(payload["version"], 1)
        rows = {(row["model"], row["pk"]) for row in payload["objects"]}
        self.assertIn(("hotel.priceitem", item.pk), rows)
        self.assertTrue(any(row["model"] == "hotel.auditevent" for row in payload["objects"]))
