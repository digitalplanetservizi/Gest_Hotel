import re
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as s

from . import models as m
from .permissions import is_superadmin
from .services import allocation_total, expected_cash, statement


def person_name(user):
    return user.get_full_name() or user.email


class UserSerializer(s.ModelSerializer):
    password = s.CharField(write_only=True, required=False, trim_whitespace=False)

    def to_representation(self, instance):
        result = super().to_representation(instance)
        if is_superadmin(instance):
            result["role"] = "superadmin"
        return result

    class Meta:
        model = m.User
        fields = ["id", "email", "first_name", "last_name", "role", "is_active", "password"]

    def validate_email(self, value):
        value = value.strip().lower()
        if len(value) > 150:
            raise s.ValidationError("Email troppo lunga: massimo 150 caratteri.")
        existing = m.User.objects.filter(email__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise s.ValidationError("Esiste già un account con questa email.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        actor = request.user if request else None
        if (
            actor
            and not is_superadmin(actor)
            and (attrs.get("role") == "superadmin" or (self.instance and is_superadmin(self.instance)))
        ):
            raise s.ValidationError({"role": "Solo un superadmin può gestire un superadmin."})
        if self.instance and actor and actor.pk == self.instance.pk:
            current_role = "superadmin" if is_superadmin(self.instance) else self.instance.role
            if "role" in attrs and attrs["role"] != current_role:
                raise s.ValidationError({"role": "Non è possibile cambiare il proprio ruolo."})
        if not self.instance and not attrs.get("password"):
            raise s.ValidationError({"password": "Password obbligatoria."})
        candidate = self.instance or m.User(email=attrs.get("email", ""))
        if "password" in attrs:
            try:
                password_validation.validate_password(attrs["password"], candidate)
            except DjangoValidationError as exc:
                raise s.ValidationError({"password": exc.messages}) from exc
        if self.instance and attrs.get("is_active") is False and actor and actor.pk == self.instance.pk:
            raise s.ValidationError({"is_active": "Non è possibile disattivare il proprio account."})
        return attrs

    def create(self, data):
        password = data.pop("password")
        return m.User.objects.create_user(username=data["email"], password=password, **data)

    def update(self, instance, data):
        password = data.pop("password", None)
        if "role" in data and data["role"] != "superadmin":
            instance.is_superuser = False
            instance.is_staff = False
        for key, value in data.items():
            setattr(instance, key, value)
        if "email" in data:
            instance.username = data["email"]
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class HotelSettingsSerializer(s.ModelSerializer):
    class Meta:
        model = m.HotelSettings
        exclude = ["id"]

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise s.ValidationError("Fuso orario IANA non valido.") from exc
        return value

    def validate_currency(self, value):
        if value != "EUR":
            raise s.ValidationError("La prima versione contabilizza esclusivamente EUR.")
        return value


class GroupSerializer(s.ModelSerializer):
    class Meta:
        model = m.Group
        fields = "__all__"

    def validate_color(self, value):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise s.ValidationError("Usare un colore esadecimale #RRGGBB.")
        return value


class RoomSerializer(s.ModelSerializer):
    class Meta:
        model = m.Room
        fields = "__all__"

    def validate_capacity(self, value):
        if value < 1:
            raise s.ValidationError("La capienza deve essere positiva.")
        return value

    def validate_default_group(self, value):
        if value and not value.is_active:
            raise s.ValidationError("Gruppo disattivato.")
        return value


class RateSerializer(s.ModelSerializer):
    class Meta:
        model = m.Rate
        fields = "__all__"

    def validate(self, attrs):
        fields = ["room_type", "board", "start_date", "end_date", "is_active"]
        merged = {key: attrs.get(key, getattr(self.instance, key, None)) for key in fields}
        if merged["start_date"] and merged["end_date"] and merged["end_date"] < merged["start_date"]:
            raise s.ValidationError({"end_date": "La fine stagione precede l'inizio."})
        if merged["is_active"] is not False:
            overlap = m.Rate.objects.filter(
                room_type=merged["room_type"],
                board=merged["board"],
                is_active=True,
                start_date__lte=merged["end_date"],
                end_date__gte=merged["start_date"],
            )
            if self.instance:
                overlap = overlap.exclude(pk=self.instance.pk)
            if overlap.exists():
                raise s.ValidationError(
                    "Esiste già un listino attivo per questa tipologia, trattamento e periodo."
                )
        return attrs

    def validate_amount(self, value):
        if value < 0:
            raise s.ValidationError("Importo negativo non ammesso.")
        return value


class PriceItemSerializer(s.ModelSerializer):
    category_name = s.CharField(source="category.name", read_only=True)

    class Meta:
        model = m.PriceItem
        fields = ["id", "description", "category", "category_name", "unit", "price", "is_active"]

    def validate_price(self, value):
        if value < 0:
            raise s.ValidationError("Prezzo negativo non ammesso.")
        return value

    def validate_category(self, value):
        if value and not value.is_active:
            raise s.ValidationError("Categoria disattivata.")
        return value


class ExtraCategorySerializer(s.ModelSerializer):
    class Meta:
        model = m.ExtraCategory
        fields = "__all__"

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise s.ValidationError("Inserire il nome della categoria.")
        duplicates = m.ExtraCategory.objects.filter(name__iexact=value)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise s.ValidationError("Esiste già una categoria con questo nome.")
        return value


class AuditEventSerializer(s.ModelSerializer):
    actor_name = s.SerializerMethodField()
    actor_email = s.EmailField(source="actor.email", read_only=True)
    action_label = s.SerializerMethodField()
    object_label = s.SerializerMethodField()

    class Meta:
        model = m.AuditEvent
        fields = [
            "id",
            "actor",
            "actor_name",
            "actor_email",
            "action",
            "action_label",
            "object_type",
            "object_id",
            "object_label",
            "data",
            "created_at",
        ]

    def get_actor_name(self, obj):
        return person_name(obj.actor) if obj.actor else "Sistema"

    def get_action_label(self, obj):
        labels = {
            "auth.logged_in": "Accesso effettuato",
            "auth.logged_out": "Uscita effettuata",
            "backup.exported": "Archivio dati scaricato",
            "backup.restored": "Backup ripristinato",
            "license.updated": "Licenza aggiornata",
            "settings.updated": "Impostazioni modificate",
            "resource.created": "Configurazione creata",
            "resource.updated": "Configurazione modificata",
            "resource.deleted": "Elemento eliminato",
            "stay.created": "Soggiorno creato",
            "stay.updated": "Soggiorno modificato",
            "stay.check-in": "Check-in",
            "stay.check-out": "Check-out",
            "stay.cancel": "Soggiorno annullato",
            "stay.no-show": "No-show registrato",
            "stay.move": "Camera cambiata",
            "stay.extend": "Soggiorno prorogato",
            "charge.created": "Addebito inserito",
            "charge.voided": "Addebito stornato",
            "payment.created": "Pagamento registrato",
            "payment.refunded": "Rimborso registrato",
            "shift.opened": "Turno aperto",
            "shift.closed": "Turno chiuso",
            "cash.income": "Entrata di cassa registrata",
            "cash.expense": "Uscita di cassa registrata",
            "stock.movement": "Movimento di magazzino",
        }
        return labels.get(obj.action, obj.action)

    def get_object_label(self, obj):
        labels = {
            "ExtraCategory": "Categoria extra",
            "PriceItem": "Extra o servizio",
            "Stay": "Soggiorno",
            "Charge": "Addebito",
            "Payment": "Pagamento",
            "Shift": "Turno di cassa",
            "CashMovement": "Movimento di cassa",
            "StockMovement": "Movimento di magazzino",
            "HotelSettings": "Impostazioni struttura",
            "User": "Account utente",
            "Room": "Camera",
            "Rate": "Tariffa soggiorno",
            "Group": "Gruppo",
            "CashReason": "Causale di cassa",
            "StockItem": "Articolo di magazzino",
            "PlatformLicense": "Licenza piattaforma",
            "RecoveryBackup": "Copia di sicurezza",
        }
        return f"{labels.get(obj.object_type, obj.object_type)} #{obj.object_id}"


class ReasonSerializer(s.ModelSerializer):
    class Meta:
        model = m.CashReason
        fields = "__all__"


class SegmentSerializer(s.ModelSerializer):
    room_number = s.CharField(source="room.number", read_only=True)

    class Meta:
        model = m.StaySegment
        fields = ["id", "room", "room_number", "arrival", "departure", "active"]


class StayWriteSerializer(s.ModelSerializer):
    class Meta:
        model = m.Stay
        fields = [
            "room",
            "guest_name",
            "guest_email",
            "guest_phone",
            "guest_count",
            "board",
            "group",
            "arrival",
            "departure",
            "is_day_use",
            "nightly_rate",
            "notes",
        ]

    def validate_guest_count(self, value):
        if value < 1:
            raise s.ValidationError("Specificare almeno un ospite.")
        return value

    def validate_nightly_rate(self, value):
        if value is not None and value < 0:
            raise s.ValidationError("Tariffa negativa non ammessa.")
        return value

    def validate_group(self, value):
        if value and not value.is_active:
            raise s.ValidationError("Gruppo disattivato.")
        return value


class StaySerializer(s.ModelSerializer):
    room_number = s.CharField(source="room.number", read_only=True)
    group_name = s.CharField(source="group.name", read_only=True, default=None)
    group_color = s.CharField(source="group.color", read_only=True, default=None)
    group_label = s.CharField(source="group.label", read_only=True, default=None)
    segments = SegmentSerializer(many=True, read_only=True)

    class Meta:
        model = m.Stay
        fields = [
            "id",
            "room",
            "room_number",
            "guest_name",
            "guest_email",
            "guest_phone",
            "guest_count",
            "board",
            "group",
            "group_name",
            "group_color",
            "group_label",
            "arrival",
            "departure",
            "status",
            "is_day_use",
            "nightly_rate",
            "notes",
            "segments",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update({key: str(value) for key, value in statement(instance.charges.all()).items()})
        return data


class ChargeSerializer(s.ModelSerializer):
    created_by = s.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = m.Charge
        fields = [
            "id",
            "stay",
            "kind",
            "description",
            "quantity",
            "unit_price",
            "amount",
            "service_date",
            "consumed_at",
            "created_at",
            "created_by",
            "voided_at",
            "void_reason",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        paid = allocation_total(instance)
        data.update(
            paid=str(paid), balance=str(Decimal("0.00") if instance.voided_at else instance.amount - paid)
        )
        return data


class AddChargeSerializer(s.Serializer):
    consumed_at = s.DateTimeField(required=False)
    price_item = s.PrimaryKeyRelatedField(queryset=m.PriceItem.objects.all(), required=False, allow_null=True)
    description = s.CharField(max_length=200, required=False)
    quantity = s.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"), default=1)
    unit_price = s.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)


class PaymentWriteSerializer(s.Serializer):
    stay = s.PrimaryKeyRelatedField(queryset=m.Stay.objects.all(), required=False, allow_null=True)
    group = s.PrimaryKeyRelatedField(queryset=m.Group.objects.all(), required=False, allow_null=True)
    amount = s.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))
    kind = s.ChoiceField(choices=["settlement", "tip"], default="settlement")
    tip_amount = s.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"), required=False, default=Decimal("0.00")
    )
    method = s.ChoiceField(choices=m.METHODS)
    reason = s.CharField(max_length=150, required=False, allow_blank=True, default="")
    scope = s.ChoiceField(choices=["all", "room", "extra"], default="all")
    note = s.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["kind"] == "tip":
            if attrs["amount"] != Decimal("0.00"):
                raise s.ValidationError({"amount": "Per una mancia singola l'importo del conto deve essere zero."})
            if attrs["tip_amount"] <= Decimal("0.00"):
                raise s.ValidationError({"tip_amount": "Inserire una mancia maggiore di zero."})
        elif attrs["amount"] <= Decimal("0.00"):
            raise s.ValidationError({"amount": "Inserire un pagamento maggiore di zero."})
        return attrs


class PaymentSerializer(s.ModelSerializer):
    operator_name = s.SerializerMethodField()

    class Meta:
        model = m.Payment
        fields = [
            "id",
            "stay",
            "group",
            "amount",
            "kind",
            "tip_amount",
            "method",
            "reason",
            "scope",
            "note",
            "created_at",
            "operator_name",
            "shift",
            "reverses",
        ]

    def get_operator_name(self, obj):
        return person_name(obj.created_by)


class RefundSerializer(s.Serializer):
    amount = s.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    reason = s.CharField(max_length=150)
    note = s.CharField(required=False, allow_blank=True, default="")


class ShiftSerializer(s.ModelSerializer):
    operator_name = s.SerializerMethodField()
    expected_cash = s.SerializerMethodField()
    difference = s.SerializerMethodField()
    status = s.SerializerMethodField()

    class Meta:
        model = m.Shift
        fields = [
            "id",
            "operator_name",
            "opened_at",
            "closed_at",
            "opening_cash",
            "expected_cash",
            "counted_cash",
            "difference",
            "status",
            "note",
        ]

    def get_operator_name(self, obj):
        return person_name(obj.opened_by)

    def get_expected_cash(self, obj):
        return str(obj.expected_at_close if obj.closed_at else expected_cash(obj))

    def get_difference(self, obj):
        return str(obj.counted_cash - obj.expected_at_close) if obj.closed_at else None

    def get_status(self, obj):
        return "closed" if obj.closed_at else "open"


class OpenShiftSerializer(s.Serializer):
    opening_cash = s.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class CloseShiftSerializer(s.Serializer):
    counted_cash = s.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    note = s.CharField(required=False, allow_blank=True, default="")


class MovementSerializer(s.ModelSerializer):
    operator_name = s.SerializerMethodField()

    class Meta:
        model = m.CashMovement
        fields = [
            "id",
            "direction",
            "amount",
            "tip_amount",
            "method",
            "reason",
            "description",
            "operator_name",
            "created_at",
            "shift",
            "payment",
        ]

    def get_operator_name(self, obj):
        return person_name(obj.created_by)


class ExpenseSerializer(s.Serializer):
    amount = s.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = s.ChoiceField(choices=m.METHODS)
    reason = s.PrimaryKeyRelatedField(queryset=m.CashReason.objects.all())
    description = s.CharField(required=False, allow_blank=True, default="")


class IncomeSerializer(ExpenseSerializer):
    """Manual income mirrors expenses; the selected reason sets its permitted direction."""


class StockItemSerializer(s.ModelSerializer):
    class Meta:
        model = m.StockItem
        fields = "__all__"
        read_only_fields = ["quantity"]

    def validate_minimum_stock(self, value):
        if value < 0:
            raise s.ValidationError("Scorta minima negativa non ammessa.")
        return value


class StockMovementSerializer(s.ModelSerializer):
    item_name = s.CharField(source="item.name", read_only=True)
    operator_name = s.CharField(source="created_by.email", read_only=True)
    quantity_after = s.DecimalField(source="item.quantity", max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = m.StockMovement
        fields = [
            "id",
            "item",
            "item_name",
            "direction",
            "quantity",
            "quantity_after",
            "reason",
            "created_at",
            "operator_name",
        ]
        read_only_fields = ["created_at"]

    def validate_quantity(self, value):
        if value <= 0:
            raise s.ValidationError("La quantità deve essere positiva.")
        return value


class ReasonInput(s.Serializer):
    reason = s.CharField(max_length=255)


class CheckInInput(s.Serializer):
    nightly_rate = s.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )


class MoveInput(s.Serializer):
    room = s.PrimaryKeyRelatedField(queryset=m.Room.objects.all())
    effective_at = s.DateTimeField()


class ExtendInput(s.Serializer):
    departure = s.DateTimeField()
