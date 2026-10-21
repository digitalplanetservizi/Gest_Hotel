from django.test import TestCase
from rest_framework.test import APIClient

from hotel import models as m


class ExtraCatalogueApiTests(TestCase):
    def setUp(self):
        self.user = m.User.objects.create_user(
            username="catalogo@example.it",
            email="catalogo@example.it",
            password="Safe-catalogue-password-2026",
            role="admin",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_categories_are_configurable_and_items_use_database_ids(self):
        created = self.client.post("/api/v1/extra-categories/", {"name": "Bar"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        category_id = created.data["id"]

        response = self.client.post(
            "/api/v1/price-items/",
            {
                "description": "Caffè espresso",
                "category": category_id,
                "unit": "pz",
                "price": "1.50",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsInstance(response.data["id"], int)
        self.assertNotIn("code", response.data)
        self.assertEqual(response.data["category"], category_id)
        self.assertEqual(response.data["category_name"], "Bar")

        duplicate = self.client.post("/api/v1/extra-categories/", {"name": " bar "}, format="json")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("name", duplicate.data)

    def test_list_can_be_filtered_by_category(self):
        bar = m.ExtraCategory.objects.create(name="Bar")
        spa = m.ExtraCategory.objects.create(name="SPA")
        item = m.PriceItem.objects.create(description="Caffè", category=bar, price="1.50")
        m.PriceItem.objects.create(description="Ingresso", category=spa, price="25.00")
        m.PriceItem.objects.create(description="Senza categoria", price="2.00")

        response = self.client.get(f"/api/v1/price-items/?category={bar.pk}")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], item.pk)
        self.assertEqual(response.data["results"][0]["category_name"], "Bar")
        invalid = self.client.get("/api/v1/price-items/?category=bar")
        self.assertEqual(invalid.status_code, 400)

    def test_an_inactive_category_cannot_be_assigned(self):
        category = m.ExtraCategory.objects.create(name="Storica", is_active=False)
        response = self.client.post(
            "/api/v1/price-items/",
            {"description": "Extra", "category": category.pk, "unit": "pz", "price": "3.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)
