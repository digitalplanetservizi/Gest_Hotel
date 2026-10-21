from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from hotel import models as m


class SeedDemoCommandTests(TestCase):
    def setUp(self):
        m.HotelSettings.objects.create(pk=1)
        m.User.objects.create_user(
            username="demo-admin@example.it",
            email="demo-admin@example.it",
            password="Test-demo-command-password2026",
            role="admin",
        )

    def test_seed_creates_a_complete_idempotent_dataset(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)

        self.assertGreaterEqual(m.Room.objects.count(), 12)
        self.assertGreaterEqual(m.Rate.objects.count(), 6)
        self.assertGreaterEqual(m.PriceItem.objects.count(), 8)
        self.assertGreaterEqual(m.ExtraCategory.objects.count(), 5)
        self.assertTrue(m.PriceItem.objects.exclude(category=None).exists())
        self.assertGreaterEqual(m.Group.objects.count(), 2)
        self.assertGreaterEqual(m.StockItem.objects.count(), 4)
        self.assertGreaterEqual(m.StockMovement.objects.count(), 8)
        self.assertTrue(m.Stay.objects.filter(status="reserved").exists())
        self.assertTrue(m.Stay.objects.filter(status="checked_in").exists())
        self.assertTrue(m.Stay.objects.filter(status="checked_out").exists())
        self.assertTrue(m.Stay.objects.filter(status="cancelled").exists())
        self.assertTrue(m.Stay.objects.filter(status="no_show").exists())
        self.assertTrue(m.Charge.objects.filter(kind="extra", voided_at__isnull=False).exists())
        self.assertTrue(m.CashMovement.objects.filter(direction="in").exists())
        self.assertTrue(m.CashMovement.objects.filter(direction="out").exists())

        snapshot = (m.Room.objects.count(), m.Stay.objects.count(), m.CashMovement.objects.count())
        call_command("seed_demo", stdout=output)
        self.assertEqual(
            (m.Room.objects.count(), m.Stay.objects.count(), m.CashMovement.objects.count()), snapshot
        )
        self.assertIn("nessuna riga duplicata", output.getvalue())
