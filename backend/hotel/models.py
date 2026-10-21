from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

METHODS = [(x, x) for x in ("cash", "card", "transfer")]
BOARD = [(x, x) for x in ("RO", "BB", "HB", "FB")]


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=[("operator", "Operatore"), ("admin", "Admin"), ("superadmin", "Superadmin")],
        default="operator",
    )

    class Meta(AbstractUser.Meta):
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_case_insensitive_unique")]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class HotelSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=160, default="La mia struttura")
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    check_in_time = models.TimeField(default="14:00")
    check_out_time = models.TimeField(default="10:00")
    currency = models.CharField(max_length=3, default="EUR")
    timezone = models.CharField(max_length=60, default="Europe/Rome")


class PlatformLicense(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=True)
    expires_on = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class RecoveryBackup(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    signed_data = models.TextField()


class Group(models.Model):
    name = models.CharField(max_length=150)
    label = models.CharField(max_length=20, blank=True)
    color = models.CharField(max_length=7, default="#7c3aed")
    reference_name = models.CharField(max_length=150)
    reference_email = models.EmailField(blank=True)
    reference_phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)


class Room(models.Model):
    number = models.CharField(max_length=20, unique=True)
    floor = models.CharField(max_length=30, blank=True)
    room_type = models.CharField(max_length=80)
    capacity = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)
    default_group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["number"]
        constraints = [models.CheckConstraint(condition=Q(capacity__gt=0), name="room_capacity_positive")]


class Rate(models.Model):
    name = models.CharField(max_length=120)
    room_type = models.CharField(max_length=80)
    board = models.CharField(max_length=2, choices=BOARD)
    start_date = models.DateField()
    end_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    basis = models.CharField(
        max_length=10, choices=[("room", "Camera"), ("person", "Persona")], default="room"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="rate_dates_valid"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="rate_amount_positive"),
        ]


class Stay(models.Model):
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="stays")
    guest_name = models.CharField(max_length=160)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=50, blank=True)
    guest_count = models.PositiveSmallIntegerField(default=1)
    board = models.CharField(max_length=2, choices=BOARD, default="RO")
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.PROTECT, related_name="stays")
    arrival = models.DateTimeField()
    departure = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        default="reserved",
        choices=[(x, x) for x in ("reserved", "checked_in", "checked_out", "cancelled", "no_show")],
    )
    is_day_use = models.BooleanField(default=False)
    nightly_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-arrival", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(departure__gt=F("arrival")), name="stay_dates_valid")
        ]


class StaySegment(models.Model):
    stay = models.ForeignKey(Stay, on_delete=models.CASCADE, related_name="segments")
    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    arrival = models.DateTimeField()
    departure = models.DateTimeField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["arrival"]
        indexes = [models.Index(fields=["room", "active", "arrival", "departure"])]
        constraints = [
            models.CheckConstraint(condition=Q(departure__gt=F("arrival")), name="segment_dates_valid")
        ]


class ExtraCategory(models.Model):
    """Configurable grouping for the extra and services catalogue."""

    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="extra_category_name_case_insensitive_unique")
        ]


class PriceItem(models.Model):
    description = models.CharField(max_length=160)
    category = models.ForeignKey(
        ExtraCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="price_items",
    )
    unit = models.CharField(max_length=30, default="pz")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(price__gte=0), name="item_price_positive")]


class Charge(models.Model):
    stay = models.ForeignKey(Stay, on_delete=models.PROTECT, related_name="charges")
    kind = models.CharField(max_length=10, choices=[("room", "Camera"), ("extra", "Extra")])
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    service_date = models.DateField(null=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0), name="charge_amount_positive")]


class CashReason(models.Model):
    name = models.CharField(max_length=100)
    direction = models.CharField(max_length=3, choices=[("in", "Entrata"), ("out", "Uscita")])
    is_active = models.BooleanField(default=True)


class Shift(models.Model):
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_shifts"
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="closed_shifts", null=True
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True)
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2)
    counted_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    expected_at_close = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                models.Value(1), condition=Q(closed_at__isnull=True), name="one_open_shift"
            )
        ]


class Payment(models.Model):
    stay = models.ForeignKey(Stay, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    kind = models.CharField(
        max_length=12,
        choices=[("settlement", "Pagamento conto"), ("tip", "Solo mancia")],
        default="settlement",
    )
    # A tip is money collected alongside a payment, but it must never reduce
    # the guest's balance or be mixed with the structure's revenue.
    tip_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    method = models.CharField(max_length=10, choices=METHODS)
    reason = models.CharField(max_length=150, blank=True)
    scope = models.CharField(max_length=10, choices=[(x, x) for x in ("all", "room", "extra")], default="all")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    shift = models.ForeignKey(Shift, null=True, on_delete=models.PROTECT)
    reverses = models.ForeignKey("self", null=True, on_delete=models.PROTECT, related_name="refunds")

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(stay__isnull=False, group__isnull=True) | Q(stay__isnull=True, group__isnull=False)
                ),
                name="payment_one_target",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0) | Q(tip_amount__gt=0), name="payment_value_positive"
            ),
            models.CheckConstraint(condition=Q(tip_amount__gte=0), name="payment_tip_nonnegative"),
        ]


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    charge = models.ForeignKey(Charge, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=12, decimal_places=2)


class CashMovement(models.Model):
    direction = models.CharField(max_length=3, choices=[("in", "Entrata"), ("out", "Uscita")])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # `amount` is the physical movement (therefore it includes the tip);
    # this field lets reports keep the tip separate from ordinary income.
    tip_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    method = models.CharField(max_length=10, choices=METHODS)
    reason = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    payment = models.OneToOneField(Payment, null=True, on_delete=models.PROTECT)
    shift = models.ForeignKey(Shift, null=True, on_delete=models.PROTECT, related_name="movements")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="movement_positive"),
            models.CheckConstraint(condition=Q(tip_amount__gte=0) & Q(tip_amount__lte=F("amount")), name="movement_tip_valid"),
        ]


class StockItem(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=30, default="pz")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=0), name="stock_nonnegative")]


class StockMovement(models.Model):
    item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="movements")
    direction = models.CharField(max_length=3, choices=[("in", "Carico"), ("out", "Scarico")])
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=50)
    object_id = models.PositiveBigIntegerField()
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class IdempotencyRecord(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor", "key"], name="idempotency_actor_key")]
