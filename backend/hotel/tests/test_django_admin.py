from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from hotel.models import AuditEvent, PlatformLicense, User

PASSWORD = "Django-admin-test-password-2026"


class DjangoBackendAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in ("superadmin", "admin", "operator"):
            cls.users[role] = User.objects.create_user(
                username=f"{role}@example.it", email=f"{role}@example.it", password=PASSWORD, role=role
            )

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get("/admin/")
        self.assertRedirects(response, "/admin/login/?next=/admin/")

    def test_only_superadmin_can_log_in_even_without_django_staff_flags(self):
        for role, user in self.users.items():
            client = Client()
            response = client.post(
                "/admin/login/?next=/admin/",
                {
                    "username": user.username,
                    "password": PASSWORD,
                    "next": "/admin/",
                },
            )
            self.assertEqual(response.status_code, 302 if role == "superadmin" else 200)
            self.assertEqual("_auth_user_id" in client.session, role == "superadmin")
        self.assertTrue(
            AuditEvent.objects.filter(action="auth.logged_in", data__source="django_admin").exists()
        )

    def test_staff_superuser_flags_and_model_permissions_do_not_bypass_role(self):
        for role in ("admin", "operator"):
            user = self.users[role]
            user.is_staff = True
            user.is_superuser = True
            user.save()
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label="hotel"))
            client = Client()
            client.force_login(user)
            for path in ("/admin/", "/admin/hotel/user/", f"/admin/hotel/user/{user.pk}/change/"):
                self.assertEqual(client.get(path).status_code, 302)
            client.logout()
            response = client.post("/admin/login/", {"username": user.username, "password": PASSWORD})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("_auth_user_id", client.session)

    def test_existing_session_loses_access_after_demotion_or_deactivation(self):
        user = self.users["superadmin"]
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        User.objects.filter(pk=user.pk).update(role="admin")
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        User.objects.filter(pk=user.pk).update(role="superadmin", is_active=False)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        client = Client()
        self.assertEqual(
            client.post("/admin/login/", {"username": user.username, "password": PASSWORD}).status_code, 200
        )
        self.assertNotIn("_auth_user_id", client.session)

    def test_console_is_read_only_even_for_superadmin_with_expired_license(self):
        PlatformLicense.objects.create(pk=1, enabled=False)
        user = self.users["superadmin"]
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.client.get("/admin/hotel/user/").status_code, 200)
        detail = self.client.get(f"/admin/hotel/user/{user.pk}/change/")
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, user.password)
        self.assertEqual(
            self.client.post(f"/admin/hotel/user/{user.pk}/change/", {"role": "operator"}).status_code, 403
        )
        self.assertEqual(
            self.client.post(f"/admin/hotel/user/{user.pk}/delete/", {"post": "yes"}).status_code, 403
        )
        self.assertEqual(self.client.post("/admin/hotel/user/add/", {}).status_code, 403)
        user.refresh_from_db()
        self.assertEqual(user.role, "superadmin")

    def test_admin_login_retains_csrf_protection(self):
        user = self.users["superadmin"]
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            client.post("/admin/login/", {"username": user.username, "password": PASSWORD}).status_code, 403
        )
