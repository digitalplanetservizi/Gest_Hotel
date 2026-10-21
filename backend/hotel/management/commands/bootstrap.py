import os

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hotel.models import HotelSettings, User


class Command(BaseCommand):
    help = "Initialize single property and optional first administrator from environment. No demo data."

    @transaction.atomic
    def handle(self, *args, **options):
        HotelSettings.objects.get_or_create(pk=1)
        if User.objects.exists():
            self.stdout.write("Struttura inizializzata; utenti esistenti conservati.")
            return
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        if not email or not password:
            raise CommandError(
                "Per il primo avvio impostare BOOTSTRAP_ADMIN_EMAIL e BOOTSTRAP_ADMIN_PASSWORD."
            )
        user = User(username=email, email=email, role="superadmin", is_staff=True, is_superuser=True)
        validate_password(password, user)
        user.set_password(password)
        user.save()
        self.stdout.write("Primo superadmin creato; nessuna camera o tariffa dimostrativa.")
