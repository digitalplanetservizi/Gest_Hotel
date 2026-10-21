import io
import json
from datetime import UTC, date, datetime
from unittest.mock import patch

from django.core import signing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from hotel import backups
from hotel import models as m

PASSWORD = "Safe-test-superadmin-2026"


class SuperadminTests(TestCase):
    def setUp(self):
        cache.clear()
        m.HotelSettings.objects.create(pk=1)
        self.users = {}
        for role in ("operator", "admin", "superadmin"):
            self.users[role] = m.User.objects.create_user(
                username=role, email=f"{role}@example.it", password=PASSWORD, role=role
            )
        self.client = APIClient()
        self.client.force_authenticate(self.users["superadmin"])

    def test_operator_reads_catalogs_but_cannot_configure_or_manage_accounts(self):
        self.client.force_authenticate(self.users["operator"])
        for endpoint in ("rooms", "rates", "price-items", "extra-categories", "cash/reasons"):
            self.assertEqual(self.client.get(f"/api/v1/{endpoint}/").status_code, 200)
            self.assertEqual(self.client.post(f"/api/v1/{endpoint}/", {}, format="json").status_code, 403)
            self.assertEqual(self.client.patch(f"/api/v1/{endpoint}/1/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/users/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)

    def upload(self, content, password=PASSWORD, confirmation="RIPRISTINA"):
        return self.client.post(
            "/api/v1/superadmin/restore/",
            {
                "file": SimpleUploadedFile("backup.json", content, content_type="application/json"),
                "password": password,
                "confirmation": confirmation,
            },
            format="multipart",
        )

    def test_privilege_boundaries_and_no_escalation(self):
        for role in ("operator", "admin"):
            self.client.force_authenticate(self.users[role])
            for endpoint in ("license", "backup", "recovery-backups"):
                self.assertEqual(self.client.get(f"/api/v1/superadmin/{endpoint}/").status_code, 403)
            self.assertEqual(self.upload(b"{}").status_code, 403)
            self.assertEqual(
                self.client.patch(
                    "/api/v1/superadmin/license/",
                    {
                        "expires_on": "2027-01-01",
                    },
                    format="json",
                ).status_code,
                403,
            )
        self.client.force_authenticate(self.users["admin"])
        superadmin = self.users["superadmin"]
        self.assertEqual(
            self.client.patch(
                f"/api/v1/users/{superadmin.pk}/",
                {
                    "password": "Changed-password-2026",
                },
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/users/{self.users['admin'].pk}/",
                {
                    "role": "superadmin",
                },
                format="json",
            ).status_code,
            400,
        )
        created = self.client.post(
            "/api/v1/users/",
            {
                "email": "new@example.it",
                "password": PASSWORD,
                "role": "operator",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        denied = self.client.post(
            "/api/v1/users/",
            {
                "email": "escalation@example.it",
                "password": PASSWORD,
                "role": "superadmin",
            },
            format="json",
        )
        self.assertEqual(denied.status_code, 400)

    def test_superadmin_can_manage_roles_but_cannot_lock_itself_out(self):
        target = self.users["admin"]
        response = self.client.patch(f"/api/v1/users/{target.pk}/", {"role": "superadmin"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        for change in ({"role": "operator"}, {"is_active": False}):
            self.assertEqual(
                self.client.patch(
                    f"/api/v1/users/{self.users['superadmin'].pk}/", change, format="json"
                ).status_code,
                400,
            )
        target.is_superuser = True
        target.save()
        self.client.patch(f"/api/v1/users/{target.pk}/", {"role": "operator"}, format="json")
        target.refresh_from_db()
        self.assertFalse(target.is_superuser)

    def test_license_expiry_uses_property_date_and_can_be_renewed(self):
        m.PlatformLicense.objects.create(pk=1, expires_on=date(2026, 10, 21))
        self.client.force_authenticate(self.users["operator"])
        with patch("hotel.permissions.timezone.now", return_value=datetime(2026, 10, 21, 21, 59, tzinfo=UTC)):
            self.assertEqual(self.client.get("/api/v1/rooms/").status_code, 200)
        with patch("hotel.permissions.timezone.now", return_value=datetime(2026, 10, 21, 22, 0, tzinfo=UTC)):
            result = self.client.get("/api/v1/rooms/")
            self.assertEqual(result.status_code, 403)
            self.assertEqual(result.data["code"], "license_inactive")
            self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
            self.assertEqual(self.client.get("/api/v1/license/").data["status"], "expired")
            self.client.force_authenticate(self.users["superadmin"])
            self.assertEqual(self.client.get("/api/v1/rooms/").status_code, 200)
            result = self.client.patch("/api/v1/superadmin/license/", {"expires_on": None}, format="json")
            self.assertTrue(result.data["active"])
        self.assertTrue(m.AuditEvent.objects.filter(action="license.updated").exists())

    def test_disabled_license_blocks_admin_and_preserves_superadmin_access(self):
        m.PlatformLicense.objects.create(pk=1, enabled=False)
        self.client.force_authenticate(self.users["admin"])
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/audit-events/").status_code, 403)
        self.client.force_authenticate(self.users["superadmin"])
        self.assertEqual(self.client.get("/api/v1/superadmin/backup/").status_code, 200)

    def test_restore_round_trip_full_demo_preserves_security_and_safety_copy(self):
        call_command("seed_demo", stdout=io.StringIO())
        original = {model: list(model.objects.order_by("pk").values()) for model in backups.MODELS}
        downloaded = self.client.get("/api/v1/superadmin/backup/")
        self.assertEqual(downloaded.status_code, 200)
        added = m.Room.objects.create(number="NEW", room_type="test")
        m.HotelSettings.objects.filter(pk=1).update(name="Modified")
        m.PlatformLicense.objects.create(pk=1, enabled=False)
        response = self.upload(downloaded.content)
        self.assertEqual(response.status_code, 200, response.data)
        for model, rows in original.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows, model.__name__)
        after_restore = m.Room.objects.create(number="AFTER-FIRST", room_type="test")
        self.assertGreater(after_restore.pk, added.pk)
        self.assertEqual(m.User.objects.count(), 3)
        self.assertFalse(m.PlatformLicense.objects.get().enabled)
        self.assertTrue(m.AuditEvent.objects.filter(action="backup.restored").exists())
        safety = self.client.get(
            f"/api/v1/superadmin/recovery-backups/{response.data['recovery_backup_id']}/"
        )
        result = self.upload(safety.content)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertTrue(m.Room.objects.filter(number="NEW").exists())
        self.assertEqual(m.HotelSettings.objects.get(pk=1).name, "Modified")
        self.assertGreater(m.Room.objects.create(number="AFTER", room_type="test").pk, after_restore.pk)

    def test_restore_rejects_bad_password_confirmation_tampering_and_foreign_signature(self):
        content = self.client.get("/api/v1/superadmin/backup/").content
        for kwargs in ({"password": "wrong"}, {"confirmation": "no"}):
            self.assertEqual(self.upload(content, **kwargs).status_code, 400)
        self.assertEqual(self.upload(b"invalid").status_code, 400)
        self.assertEqual(self.upload(b'{"signed_data":42}').status_code, 400)
        envelope = json.loads(content)
        envelope["signed_data"] += "tampered"
        self.assertEqual(self.upload(json.dumps(envelope).encode()).status_code, 400)
        self.assertEqual(self.upload(content).status_code, 429)
        cache.clear()
        with self.settings(SECRET_KEY="another-installation"):
            self.assertEqual(self.upload(content).status_code, 400)
        self.assertEqual(m.RecoveryBackup.objects.count(), 0)

    def test_failed_restore_rolls_back_data_and_safety_copy(self):
        m.Room.objects.create(number="KEEP", room_type="test")
        content = self.client.get("/api/v1/superadmin/backup/").content
        with patch("hotel.backups.connection.check_constraints", side_effect=IntegrityError("test")):
            response = self.upload(content)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(m.Room.objects.filter(number="KEEP").exists())
        self.assertEqual(m.RecoveryBackup.objects.count(), 0)

    def test_restore_rejects_security_models_even_with_valid_signature(self):
        signed = json.loads(self.client.get("/api/v1/superadmin/backup/").content)["signed_data"]
        payload = signing.loads(signed, salt=backups.SALT)
        payload["objects"].append({"model": "hotel.platformlicense", "pk": 1, "fields": {"enabled": True}})
        content = json.dumps({"signed_data": signing.dumps(payload, salt=backups.SALT)}).encode()
        self.assertEqual(self.upload(content).status_code, 400)
