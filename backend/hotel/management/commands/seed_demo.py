"""Populate a realistic, idempotent demo dataset without removing user records."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from hotel import services
from hotel.models import (
    CashReason,
    ExtraCategory,
    Group,
    HotelSettings,
    PriceItem,
    Rate,
    Room,
    Shift,
    Stay,
    StockItem,
    User,
)


class Command(BaseCommand):
    help = "Aggiunge dati demo completi senza eliminare o modificare i dati già presenti."

    marker_description = "Pacchetto degustazione"

    @transaction.atomic
    def handle(self, *args, **options):
        if PriceItem.objects.filter(
            description=self.marker_description, category__name="Esperienze"
        ).exists():
            self.stdout.write(self.style.WARNING("Dati demo già presenti: nessuna riga duplicata."))
            return

        actor = User.objects.order_by("pk").first()
        if not actor:
            raise CommandError("Creare prima un utente amministratore.")

        settings = HotelSettings.objects.get_or_create(pk=1)[0]
        zone = ZoneInfo(settings.timezone)
        today = timezone.now().astimezone(zone).date()

        def moment(offset, hour, minute=0):
            return datetime.combine(today + timedelta(days=offset), time(hour, minute), tzinfo=zone)

        def room(number, room_type, capacity, floor, default_group=None):
            result, _ = Room.objects.get_or_create(
                number=number,
                defaults={
                    "room_type": room_type,
                    "capacity": capacity,
                    "floor": floor,
                    "default_group": default_group,
                },
            )
            return result

        tour, _ = Group.objects.get_or_create(
            name="Demo · Tour del Lago",
            defaults={
                "label": "TOUR",
                "color": "#0f766e",
                "reference_name": "Giulia Bianchi",
                "reference_email": "giulia.bianchi@example.test",
                "reference_phone": "+39 333 555 0101",
            },
        )
        azienda, _ = Group.objects.get_or_create(
            name="Demo · Azienda Aurora",
            defaults={
                "label": "AURORA",
                "color": "#7c3aed",
                "reference_name": "Marco Conti",
                "reference_email": "marco.conti@example.test",
                "reference_phone": "+39 333 555 0202",
            },
        )

        rooms = {
            "101": room("101", "Doppia", 2, "1"),
            "102": room("102", "Doppia", 2, "1"),
            "103": room("103", "Matrimoniale", 2, "1"),
            "104": room("104", "Tripla", 3, "1"),
            "105": room("105", "Suite", 4, "1"),
            "201": room("201", "Doppia", 2, "2", tour),
            "202": room("202", "Doppia", 2, "2", tour),
            "203": room("203", "Matrimoniale", 2, "2"),
            "204": room("204", "Tripla", 3, "2"),
            "301": room("301", "Suite", 4, "3", azienda),
            "302": room("302", "Doppia", 2, "3"),
            "303": room("303", "Matrimoniale", 2, "3"),
        }

        rate_rows = [
            ("Doppia", "RO", "95.00", "room"),
            ("Doppia", "BB", "115.00", "room"),
            ("Matrimoniale", "RO", "125.00", "room"),
            ("Matrimoniale", "BB", "145.00", "room"),
            ("Tripla", "BB", "175.00", "room"),
            ("Suite", "BB", "250.00", "room"),
        ]
        for room_type, board, amount, basis in rate_rows:
            Rate.objects.get_or_create(
                name="Demo · Autunno 2026",
                room_type=room_type,
                board=board,
                start_date=today - timedelta(days=45),
                end_date=today + timedelta(days=75),
                defaults={"amount": Decimal(amount), "basis": basis, "is_active": True},
            )

        items = [
            ("DEMO-CHECK", "Pacchetto degustazione", "Esperienze", "pz", "45.00"),
            ("DEMO-CAFFE", "Caffè espresso", "Bar", "pz", "1.50"),
            ("DEMO-ACQUA", "Acqua naturale 50 cl", "Minibar", "pz", "2.00"),
            ("DEMO-WINE", "Calice vino della casa", "Ristorante", "pz", "6.50"),
            ("DEMO-SPA", "Ingresso SPA", "Benessere", "persona", "25.00"),
            ("DEMO-PARK", "Parcheggio coperto", "Servizi", "giorno", "12.00"),
            ("DEMO-PET", "Supplemento animale", "Servizi", "notte", "15.00"),
            ("DEMO-LAUNDRY", "Lavanderia", "Servizi", "pz", "8.00"),
        ]
        catalog = {}
        for code, description, category, unit, price in items:
            category_obj, _ = ExtraCategory.objects.get_or_create(name=category)
            catalog[code], _ = PriceItem.objects.get_or_create(
                description=description,
                category=category_obj,
                defaults={"unit": unit, "price": Decimal(price), "is_active": True},
            )

        in_reason, _ = CashReason.objects.get_or_create(name="Demo · Reintegro fondo", direction="in")
        out_reason, _ = CashReason.objects.get_or_create(name="Demo · Piccole spese", direction="out")
        CashReason.objects.get_or_create(name="Demo · Rimborso cliente", direction="out")

        def stay(
            key,
            room_key,
            guest,
            arrival,
            departure,
            board,
            rate,
            status="reserved",
            group=None,
            guests=1,
            day_use=False,
        ):
            existing = Stay.objects.filter(notes=f"DEMO:{key}").first()
            if existing:
                return existing
            created = services.save_stay(
                {
                    "room": rooms[room_key],
                    "guest_name": guest,
                    "guest_email": f"{key.lower()}@example.test",
                    "guest_phone": "+39 333 000 0000",
                    "guest_count": guests,
                    "board": board,
                    "group": group,
                    "arrival": arrival,
                    "departure": departure,
                    "nightly_rate": Decimal(rate),
                    "notes": f"DEMO:{key}",
                    "is_day_use": day_use,
                },
                actor,
            )
            if status in {"checked_in", "checked_out"}:
                services.stay_action(created.pk, "check-in", {}, actor)
            if status == "checked_out":
                services.stay_action(created.pk, "check-out", {}, actor)
            if status in {"cancelled", "no_show"}:
                action = {"cancelled": "cancel", "no_show": "no-show"}[status]
                services.stay_action(created.pk, action, {}, actor)
            return created

        today_arrival = stay(
            "ARRIVO-OGGI", "101", "Elena Rossi", moment(0, 14), moment(3, 10), "BB", "115.00"
        )
        current = stay(
            "IN-CORSO", "102", "Luca Ferri", moment(-2, 14), moment(1, 10), "BB", "115.00", "checked_in"
        )
        due_today = stay(
            "PARTENZA-OGGI", "103", "Sara Greco", moment(-2, 14), moment(0, 10), "RO", "125.00", "checked_in"
        )
        stay("PARTENZA-PREVISTA", "104", "Paolo Neri", moment(-2, 14), moment(0, 11), "BB", "175.00")
        stay(
            "PARTENZA-CONCLUSA",
            "105",
            "Anna Villa",
            moment(-3, 14),
            moment(0, 9),
            "BB",
            "250.00",
            "checked_out",
        )
        stay("DAY-USE", "203", "Davide Moretti", moment(0, 12), moment(0, 18), "RO", "80.00", day_use=True)
        stay("FUTURO", "204", "Marta Riva", moment(4, 14), moment(7, 10), "BB", "175.00", guests=3)
        group_one = stay(
            "TOUR-201",
            "201",
            "Tour del Lago · Camera 201",
            moment(1, 14),
            moment(4, 10),
            "BB",
            "115.00",
            group=tour,
        )
        group_two = stay(
            "TOUR-202",
            "202",
            "Tour del Lago · Camera 202",
            moment(1, 14),
            moment(4, 10),
            "BB",
            "115.00",
            group=tour,
        )
        stay(
            "AZIENDA",
            "301",
            "Azienda Aurora",
            moment(8, 14),
            moment(10, 10),
            "BB",
            "250.00",
            group=azienda,
            guests=2,
        )
        stay(
            "ANNULLATA",
            "302",
            "Prenotazione annullata",
            moment(12, 14),
            moment(14, 10),
            "RO",
            "95.00",
            "cancelled",
        )
        stay(
            "NO-SHOW", "303", "Ospite non arrivato", moment(-1, 14), moment(1, 10), "RO", "125.00", "no_show"
        )

        def extra(stay_object, item_code, quantity, consumed_at, description=None):
            if stay_object.charges.filter(
                description=description or catalog[item_code].description, kind="extra"
            ).exists():
                return
            services.add_charge(
                stay_object,
                {
                    "price_item": catalog[item_code],
                    "quantity": Decimal(quantity),
                    "consumed_at": consumed_at,
                    **({"description": description} if description else {}),
                },
                actor,
            )

        extra(current, "DEMO-CAFFE", "2", moment(-1, 8, 15))
        extra(current, "DEMO-SPA", "1", moment(0, 10, 30))
        extra(due_today, "DEMO-WINE", "3", moment(-1, 21, 10))
        extra(due_today, "DEMO-PARK", "2", moment(-1, 18, 0))
        extra(today_arrival, "DEMO-PET", "1", moment(0, 15, 0))
        extra(group_one, "DEMO-CHECK", "2", moment(1, 19, 30))
        extra(group_two, "DEMO-ACQUA", "6", moment(1, 20, 0))
        voidable = services.add_charge(
            current,
            {
                "price_item": catalog["DEMO-LAUNDRY"],
                "quantity": Decimal("1"),
                "consumed_at": moment(-1, 17, 20),
            },
            actor,
        )
        services.void_charge(voidable, "Demo: servizio non erogato", actor)

        if not Shift.objects.filter(closed_at__isnull=True).exists():
            services.open_shift({"opening_cash": Decimal("150.00")}, actor)

        services.record_payment(
            {
                "stay": due_today,
                "amount": Decimal("120.00"),
                "method": "cash",
                "reason": "Caparra",
                "scope": "all",
                "note": "Demo: saldo parziale",
            },
            actor,
            "demo-payment-due-today",
        )
        services.record_payment(
            {
                "stay": current,
                "amount": Decimal("25.00"),
                "method": "card",
                "reason": "Extra SPA",
                "scope": "extra",
                "note": "Demo: extra parziale",
            },
            actor,
            "demo-payment-current-extra",
        )
        services.record_payment(
            {
                "group": tour,
                "amount": Decimal("150.00"),
                "method": "transfer",
                "reason": "Acconto gruppo",
                "scope": "all",
                "note": "Demo: referente gruppo",
            },
            actor,
            "demo-payment-tour",
        )
        services.manual_income(
            {
                "amount": Decimal("80.00"),
                "method": "cash",
                "reason": in_reason,
                "description": "Demo: reintegro fondo cassa",
            },
            actor,
        )
        services.manual_expense(
            {
                "amount": Decimal("18.50"),
                "method": "cash",
                "reason": out_reason,
                "description": "Demo: acquisto urgente",
            },
            actor,
        )

        stocks = [
            ("DEMO-MINI-ACQUA", "Acqua minibar", "bottiglie", "24", "8", "5"),
            ("DEMO-MINI-CAFFE", "Capsule caffè", "pz", "60", "20", "14"),
            ("DEMO-LINEN", "Set biancheria", "set", "12", "5", "2"),
            ("DEMO-SOAP", "Sapone ospiti", "pz", "40", "15", "7"),
        ]
        for code, name, unit, incoming, minimum, outgoing in stocks:
            item, created = StockItem.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "unit": unit,
                    "quantity": Decimal("0"),
                    "minimum_stock": Decimal(minimum),
                },
            )
            if created:
                services.stock_movement(
                    {
                        "item": item,
                        "direction": "in",
                        "quantity": Decimal(incoming),
                        "reason": "Demo: carico iniziale",
                    },
                    actor,
                )
                services.stock_movement(
                    {
                        "item": item,
                        "direction": "out",
                        "quantity": Decimal(outgoing),
                        "reason": "Demo: utilizzo struttura",
                    },
                    actor,
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Dati demo inseriti: 12 camere, listino, gruppi, extra, scorte, soggiorni, incassi e cassa."
            )
        )
