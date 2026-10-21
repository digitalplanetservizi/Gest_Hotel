"""Explicit domain commands. Lock order: hotel mutex, account, room, charges.

The singleton mutex serializes writes for this single-property installation,
including empty-table operations (first cash shift / first overlapping rate).
PostgreSQL holds the row lock until the surrounding transaction commits.
"""

import hashlib
import json
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    AuditEvent,
    CashMovement,
    Charge,
    HotelSettings,
    IdempotencyRecord,
    Payment,
    PaymentAllocation,
    PriceItem,
    Rate,
    Room,
    Shift,
    Stay,
    StaySegment,
    StockItem,
    StockMovement,
)
from .permissions import is_administrator

ZERO = Decimal("0.00")


def money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def mutex():
    HotelSettings.objects.get_or_create(pk=1)
    return HotelSettings.objects.select_for_update().get(pk=1)


def audit(actor, action, obj, data=None):
    AuditEvent.objects.create(
        actor=actor, action=action, object_type=obj.__class__.__name__, object_id=obj.pk, data=data or {}
    )


def local(value):
    zone = HotelSettings.objects.get_or_create(pk=1)[0].timezone
    return value.astimezone(ZoneInfo(zone))


def allocation_total(charge):
    cache = getattr(charge, "_prefetched_objects_cache", {})
    if "allocations" in cache:
        return sum((a.amount for a in cache["allocations"]), ZERO)
    return charge.allocations.aggregate(total=Sum("amount"))["total"] or ZERO


def statement(charges):
    total = paid = room_balance = extras_balance = ZERO
    for c in charges:
        if c.voided_at:
            continue
        allocated = allocation_total(c)
        total += c.amount
        paid += allocated
        if c.kind == "room":
            room_balance += c.amount - allocated
        else:
            extras_balance += c.amount - allocated
    return {
        "total": money(total),
        "paid": money(paid),
        "balance": money(total - paid),
        "room_balance": money(room_balance),
        "extras_balance": money(extras_balance),
    }


def validate_interval(data, room, exclude=None, segment_only=False):
    arrival, departure = data["arrival"], data["departure"]
    if departure <= arrival:
        raise ValidationError({"departure": "La partenza deve seguire l'arrivo."})
    if data.get("guest_count", 1) > room.capacity:
        raise ValidationError({"guest_count": "Capienza della camera superata."})
    if not room.is_active:
        raise ValidationError({"room": "Camera disattivata."})
    if (
        not segment_only
        and (local(departure).date() - local(arrival).date()).days == 0
        and not data.get("is_day_use")
    ):
        raise ValidationError({"is_day_use": "Per arrivo e partenza nello stesso giorno scegliere day use."})
    conflicts = StaySegment.objects.filter(
        room=room, active=True, arrival__lt=departure, departure__gt=arrival
    )
    if exclude:
        conflicts = conflicts.exclude(stay=exclude)
    if conflicts.exists():
        raise ValidationError({"room": "La camera è già impegnata nell'intervallo indicato."})


def quote(data):
    room = data["room"]
    arrival, departure = local(data["arrival"]), local(data["departure"])
    if departure <= arrival:
        raise ValidationError({"departure": "Intervallo non valido."})
    nights = (departure.date() - arrival.date()).days
    if data.get("is_day_use"):
        if arrival.date() != departure.date():
            raise ValidationError({"is_day_use": "Il day use deve concludersi nello stesso giorno."})
        nights = 1
    if nights < 1 or nights > 730:
        raise ValidationError({"departure": "Il soggiorno deve avere da 1 a 730 notti."})
    rates = list(
        Rate.objects.filter(
            room_type=room.room_type,
            board=data.get("board", "RO"),
            is_active=True,
            start_date__lte=departure.date(),
            end_date__gte=arrival.date(),
        )
    )
    lines = []
    for n in range(nights):
        day = arrival.date() + timedelta(days=n)
        override = data.get("nightly_rate")
        if override is not None:
            price = money(override)
        else:
            found = [r for r in rates if r.start_date <= day <= r.end_date]
            if len(found) != 1:
                raise ValidationError(
                    {"nightly_rate": f"Listino mancante o ambiguo il {day}: inserire una tariffa manuale."}
                )
            rate = found[0]
            price = money(rate.amount * (data.get("guest_count", 1) if rate.basis == "person" else 1))
        lines.append(
            {
                "date": day.isoformat(),
                "description": f"{'Day use' if data.get('is_day_use') else 'Pernottamento'} {day}",
                "amount": str(price),
            }
        )
    return {
        "nights": nights,
        "total": str(money(sum((Decimal(x["amount"]) for x in lines), ZERO))),
        "lines": lines,
    }


def stay_data(stay):
    return {
        field: getattr(stay, field)
        for field in ("room", "arrival", "departure", "guest_count", "board", "is_day_use", "nightly_rate")
    }


def replace_room_charges(stay, user, quote_result):
    old = stay.charges.filter(kind="room", voided_at__isnull=True)
    if any(allocation_total(c) != 0 for c in old):
        raise ValidationError("Tariffa già incassata: rimborsare prima di modificare date o tariffa.")
    old.update(voided_at=timezone.now(), void_reason="Ricalcolo soggiorno")
    Charge.objects.bulk_create(
        [
            Charge(
                stay=stay,
                kind="room",
                description=line["description"],
                quantity=1,
                unit_price=line["amount"],
                amount=line["amount"],
                service_date=line["date"],
                created_by=user,
            )
            for line in quote_result["lines"]
        ]
    )


@transaction.atomic
def save_stay(data, user, instance=None):
    mutex()
    if instance:
        stay = Stay.objects.select_for_update().get(pk=instance.pk)
        if stay.status != "reserved":
            raise ValidationError(
                "Solo le prenotazioni possono essere modificate; usare le azioni del soggiorno."
            )
        merged = stay_data(stay) | data
        if (
            "group" in data
            and data["group"] != stay.group
            and any(allocation_total(c) != 0 for c in stay.charges.all())
        ):
            raise ValidationError(
                {"group": "Rimborsare gli incassi prima di cambiare il referente del conto."}
            )
        if stay.segments.count() != 1:
            raise ValidationError("Soggiorno con trasferimenti: usare le azioni dedicate.")
    else:
        stay = None
        merged = data.copy()
    room = Room.objects.select_for_update().get(pk=data.get("room", stay.room if stay else None).pk)
    merged["room"] = room
    if not stay:
        if "group" not in merged:
            merged["group"] = room.default_group
    validate_interval(merged, room, stay)
    economic_fields = {"room", "arrival", "departure", "guest_count", "board", "is_day_use", "nightly_rate"}
    recalculate = not stay or any(key in data and getattr(stay, key) != data[key] for key in economic_fields)
    result = quote(merged) if recalculate else None
    if stay:
        for key, value in data.items():
            setattr(stay, key, value)
        stay.save()
        stay.segments.update(room=room, arrival=stay.arrival, departure=stay.departure)
    else:
        stay = Stay.objects.create(**merged, created_by=user)
        StaySegment.objects.create(stay=stay, room=room, arrival=stay.arrival, departure=stay.departure)
    if recalculate:
        replace_room_charges(stay, user, result)
    audit(user, "stay.updated" if instance else "stay.created", stay)
    return stay


@transaction.atomic
def stay_action(stay_id, action, data, user):
    mutex()
    stay = Stay.objects.select_for_update().get(pk=stay_id)
    audit_data = {key: str(value.pk if hasattr(value, "pk") else value) for key, value in data.items()}
    if action == "check-in":
        if stay.status != "reserved":
            raise ValidationError("È possibile effettuare il check-in solo di una prenotazione.")
        if "nightly_rate" in data:
            stay.nightly_rate = data["nightly_rate"]
            replace_room_charges(stay, user, quote(stay_data(stay)))
        stay.status = "checked_in"
    elif action == "check-out":
        if stay.status != "checked_in":
            raise ValidationError("Il soggiorno non è in corso.")
        balance = statement(stay.charges.select_for_update().prefetch_related("allocations"))["balance"]
        if balance > ZERO and not is_administrator(user):
            raise ValidationError(
                {
                    "detail": (
                        "Impossibile effettuare il check-out con un saldo residuo di "
                        f"{balance:.2f} €. Registra prima il pagamento completo."
                    ),
                    "code": "checkout_balance_due",
                }
            )
        if balance > ZERO:
            audit_data["outstanding_balance"] = str(balance)
            audit_data["debt_override"] = True
        stay.status = "checked_out"
        now = timezone.now()
        for segment in stay.segments.filter(active=True):
            if segment.arrival >= now:
                segment.active = False
            elif segment.departure > now:
                segment.departure = now
            segment.save()
    elif action in ("cancel", "no-show"):
        if stay.status != "reserved":
            raise ValidationError("Azione consentita solo per prenotazioni.")
        if any(allocation_total(c) != 0 for c in stay.charges.all()):
            raise ValidationError("Rimborsare gli incassi prima di annullare la prenotazione.")
        stay.status = "cancelled" if action == "cancel" else "no_show"
        stay.segments.update(active=False)
        stay.charges.filter(voided_at__isnull=True).update(voided_at=timezone.now(), void_reason=stay.status)
    elif action == "extend":
        if stay.status not in ("reserved", "checked_in"):
            raise ValidationError("Il soggiorno non può essere prorogato.")
        departure = data["departure"]
        if departure <= stay.departure:
            raise ValidationError({"departure": "La nuova partenza deve essere successiva a quella attuale."})
        last = stay.segments.select_for_update().order_by("-departure").first()
        validate_interval(
            stay_data(stay) | {"arrival": last.arrival, "departure": departure}, last.room, stay
        )
        extra_data = stay_data(stay) | {"arrival": stay.departure, "departure": departure}
        # Bill extra nights using the original scheduled departure calendar date.
        additional = quote(extra_data)
        for line in additional["lines"]:
            Charge.objects.create(
                stay=stay,
                kind="room",
                description=line["description"],
                quantity=1,
                unit_price=line["amount"],
                amount=line["amount"],
                service_date=line["date"],
                created_by=user,
            )
        last.departure = departure
        last.save()
        stay.departure = departure
    elif action == "move":
        if stay.status not in ("reserved", "checked_in"):
            raise ValidationError("Il soggiorno non può essere trasferito.")
        room = Room.objects.select_for_update().get(pk=data["room"].pk)
        effective = data["effective_at"]
        if not stay.arrival <= effective < stay.departure:
            raise ValidationError({"effective_at": "Il trasferimento deve ricadere nel soggiorno."})
        if room.pk == stay.room_id:
            raise ValidationError({"room": "Selezionare una camera diversa."})
        validate_interval(stay_data(stay) | {"arrival": effective}, room, stay, segment_only=True)
        segment = stay.segments.filter(active=True, arrival__lte=effective, departure__gt=effective).first()
        if not segment or stay.segments.filter(arrival__gt=effective).exists():
            raise ValidationError("Trasferimento non valido rispetto ai segmenti esistenti.")
        if effective == segment.arrival:
            segment.room = room
            segment.save()
        else:
            end = segment.departure
            segment.departure = effective
            segment.save()
            StaySegment.objects.create(stay=stay, room=room, arrival=effective, departure=end)
        stay.room = room
    stay.save()
    audit(user, f"stay.{action}", stay, audit_data)
    return stay


@transaction.atomic
def add_charge(stay, data, user):
    mutex()
    stay = Stay.objects.select_for_update().get(pk=stay.pk)
    if stay.status in ("cancelled", "no_show"):
        raise ValidationError("Impossibile addebitare un soggiorno annullato.")
    item = data.get("price_item")
    if item:
        item = PriceItem.objects.get(pk=item.pk)
    if item and not item.is_active:
        raise ValidationError("Articolo disattivato.")
    description = data.get("description") or (item.description if item else "")
    price = data.get("unit_price", item.price if item else None)
    if not description or price is None:
        raise ValidationError("Specificare articolo oppure descrizione e prezzo.")
    charge = Charge.objects.create(
        stay=stay,
        kind="extra",
        consumed_at=data.get("consumed_at") or timezone.now(),
        description=description,
        quantity=data["quantity"],
        unit_price=price,
        amount=money(price * data["quantity"]),
        created_by=user,
    )
    audit(user, "charge.created", charge)
    return charge


@transaction.atomic
def void_charge(charge, reason, user):
    mutex()
    charge = Charge.objects.select_for_update().get(pk=charge.pk)
    if charge.voided_at:
        raise ValidationError("Addebito già stornato.")
    if allocation_total(charge) != 0:
        raise ValidationError("Rimborsare prima le quote già incassate.")
    charge.voided_at, charge.void_reason = timezone.now(), reason
    charge.save()
    audit(user, "charge.voided", charge, {"reason": reason})
    return charge


def current_shift(method):
    if method != "cash":
        return Shift.objects.filter(closed_at__isnull=True).first()
    shift = Shift.objects.select_for_update().filter(closed_at__isnull=True).first()
    if not shift:
        raise ValidationError("Aprire un turno di cassa prima di movimentare contanti.")
    return shift


def fingerprint(data, operation):
    payload = {k: (v.pk if hasattr(v, "pk") else str(v)) for k, v in data.items()}
    return hashlib.sha256(
        json.dumps({"operation": operation, "payload": payload}, sort_keys=True).encode()
    ).hexdigest()


def existing_payment(user, key, digest):
    if not key or len(key) > 100:
        raise ValidationError({"Idempotency-Key": "Header obbligatorio, massimo 100 caratteri."})
    record = IdempotencyRecord.objects.filter(actor=user, key=key).first()
    if record:
        if record.fingerprint != digest:
            raise ValidationError("Idempotency-Key già utilizzata per un'operazione diversa.")
        return record.payment


@transaction.atomic
def record_payment(data, user, key):
    mutex()
    digest = fingerprint(data, "payment")
    existing = existing_payment(user, key, digest)
    if existing:
        return existing
    stay, group = data.get("stay"), data.get("group")
    if bool(stay) == bool(group):
        raise ValidationError("Scegliere un solo conto: soggiorno oppure gruppo.")
    if stay:
        stay = Stay.objects.select_for_update().get(pk=stay.pk)
        data["stay"] = stay
    if stay and stay.group_id:
        raise ValidationError("Il soggiorno appartiene a un gruppo: incassare sul referente unico.")
    charges = Charge.objects.select_for_update().filter(voided_at__isnull=True)
    charges = charges.filter(stay=stay) if stay else charges.filter(stay__group=group)
    if data.get("scope", "all") != "all":
        charges = charges.filter(kind=data["scope"])
    charges = list(charges.order_by("created_at", "pk"))
    balances = [(c, c.amount - allocation_total(c)) for c in charges]
    if data["amount"] > sum((b for _, b in balances), ZERO):
        raise ValidationError(
            {"amount": "L'importo supera il saldo disponibile per il conto e l'ambito selezionati."}
        )
    shift = current_shift(data["method"])
    payment = Payment.objects.create(**data, created_by=user, shift=shift)
    left = payment.amount
    for charge, balance in balances:
        amount = min(left, balance)
        if amount > 0:
            PaymentAllocation.objects.create(payment=payment, charge=charge, amount=amount)
            left -= amount
    CashMovement.objects.create(
        direction="in",
        amount=payment.amount + payment.tip_amount,
        tip_amount=payment.tip_amount,
        method=payment.method,
        reason=payment.reason or "Incasso soggiorno",
        description=payment.note,
        payment=payment,
        shift=shift,
        created_by=user,
    )
    IdempotencyRecord.objects.create(actor=user, key=key, fingerprint=digest, payment=payment)
    audit(
        user,
        "payment.created",
        payment,
        {"kind": payment.kind, "tip_amount": str(payment.tip_amount)},
    )
    return payment


@transaction.atomic
def refund_payment(payment, data, user, key):
    mutex()
    digest = fingerprint(data, f"refund:{payment.pk}")
    existing = existing_payment(user, key, digest)
    if existing:
        return existing
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.reverses_id:
        raise ValidationError("Non è possibile rimborsare un rimborso.")
    if payment.kind == "tip":
        raise ValidationError("La registrazione Solo mancia non è rimborsabile dal rimborso del conto.")
    refunded = payment.refunds.aggregate(total=Sum("amount"))["total"] or ZERO
    if data["amount"] > payment.amount - refunded:
        raise ValidationError({"amount": "Importo superiore al residuo rimborsabile."})
    shift = current_shift(payment.method)
    refund = Payment.objects.create(
        stay=payment.stay,
        group=payment.group,
        method=payment.method,
        scope=payment.scope,
        reverses=payment,
        amount=data["amount"],
        reason=data["reason"],
        note=data.get("note", ""),
        created_by=user,
        shift=shift,
    )
    left = refund.amount
    for allocation in payment.allocations.select_related("charge").order_by("-pk"):
        reversed_amount = (
            PaymentAllocation.objects.filter(payment__reverses=payment, charge=allocation.charge).aggregate(
                total=Sum("amount")
            )["total"]
            or ZERO
        )
        amount = min(left, allocation.amount + reversed_amount)
        if amount > 0:
            PaymentAllocation.objects.create(payment=refund, charge=allocation.charge, amount=-amount)
            left -= amount
    if left:
        raise ValidationError("Allocazioni del pagamento incoerenti.")
    CashMovement.objects.create(
        direction="out",
        amount=refund.amount,
        method=refund.method,
        reason=refund.reason,
        description=refund.note,
        payment=refund,
        shift=shift,
        created_by=user,
    )
    IdempotencyRecord.objects.create(actor=user, key=key, fingerprint=digest, payment=refund)
    audit(user, "payment.refunded", refund)
    return refund


def expected_cash(shift):
    incoming = shift.movements.filter(method="cash", direction="in").aggregate(s=Sum("amount"))["s"] or ZERO
    outgoing = shift.movements.filter(method="cash", direction="out").aggregate(s=Sum("amount"))["s"] or ZERO
    return shift.opening_cash + incoming - outgoing


@transaction.atomic
def open_shift(data, user):
    mutex()
    if Shift.objects.filter(closed_at__isnull=True).exists():
        raise ValidationError("Esiste già un turno aperto.")
    shift = Shift.objects.create(opening_cash=data["opening_cash"], opened_by=user)
    audit(user, "shift.opened", shift)
    return shift


@transaction.atomic
def close_shift(shift, data, user):
    mutex()
    shift = Shift.objects.select_for_update().get(pk=shift.pk)
    if shift.closed_at:
        if shift.counted_cash == data["counted_cash"] and shift.note == data.get("note", ""):
            return shift
        raise ValidationError("Turno già chiuso.")
    shift.expected_at_close = expected_cash(shift)
    shift.counted_cash, shift.note = data["counted_cash"], data.get("note", "")
    shift.closed_at, shift.closed_by = timezone.now(), user
    shift.save()
    audit(user, "shift.closed", shift, {"difference": str(shift.counted_cash - shift.expected_at_close)})
    return shift


@transaction.atomic
def manual_cash_movement(data, user, direction):
    mutex()
    reason = data["reason"]
    if direction not in {"in", "out"}:
        raise ValueError("Direzione movimento di cassa non valida.")
    if not reason.is_active or reason.direction != direction:
        label = "entrata" if direction == "in" else "uscita"
        raise ValidationError({"reason": f"Scegliere una causale di {label} attiva."})
    shift = current_shift(data["method"])
    obj = CashMovement.objects.create(
        **(data | {"reason": reason.name}), direction=direction, shift=shift, created_by=user
    )
    action = "cash.income" if direction == "in" else "cash.expense"
    audit(user, action, obj)
    return obj


def manual_expense(data, user):
    return manual_cash_movement(data, user, "out")


def manual_income(data, user):
    return manual_cash_movement(data, user, "in")


@transaction.atomic
def stock_movement(data, user):
    mutex()
    if data["quantity"] <= 0:
        raise ValidationError({"quantity": "La quantità deve essere positiva."})
    item = StockItem.objects.select_for_update().get(pk=data["item"].pk)
    if not item.is_active:
        raise ValidationError("Articolo disattivato.")
    change = data["quantity"] * (1 if data["direction"] == "in" else -1)
    if item.quantity + change < 0:
        raise ValidationError({"quantity": "Giacenza insufficiente."})
    item.quantity += change
    item.save(update_fields=["quantity"])
    obj = StockMovement.objects.create(**data, created_by=user)
    obj.item = item
    audit(user, "stock.movement", obj)
    return obj
