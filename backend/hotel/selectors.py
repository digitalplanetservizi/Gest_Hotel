from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import F, Prefetch, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import models as m
from .services import ZERO


def stays():
    return m.Stay.objects.select_related("room", "group").prefetch_related(
        "segments__room", "charges__allocations"
    )


def outstanding_balance():
    """Current credits with constant memory and exactly two independent sums.

    Keeping charge totals separate from allocation totals avoids multiplying
    charge amounts when a charge has several partial receipts or refunds.
    """
    charges = m.Charge.objects.filter(voided_at__isnull=True).aggregate(total=Sum("amount"))["total"] or ZERO
    allocations = (
        m.PaymentAllocation.objects.filter(charge__voided_at__isnull=True).aggregate(total=Sum("amount"))[
            "total"
        ]
        or ZERO
    )
    return charges - allocations


def period(params, max_days=366):
    settings = m.HotelSettings.objects.get_or_create(pk=1)[0]
    zone = ZoneInfo(settings.timezone)
    today = timezone.now().astimezone(zone).date()
    try:
        start = datetime.fromisoformat(params.get("start", today.replace(day=1).isoformat())).date()
        end = datetime.fromisoformat(params.get("end", (today + timedelta(days=1)).isoformat())).date()
    except (ValueError, TypeError) as exc:
        raise ValidationError("Date richieste nel formato YYYY-MM-DD.") from exc
    if end <= start or (end - start).days > max_days:
        raise ValidationError(f"Specificare un intervallo crescente fino a {max_days} giorni; fine esclusa.")
    return datetime.combine(start, time.min, zone), datetime.combine(end, time.min, zone)


def tip_period(params):
    """Return the requested local calendar period for the tips dashboard."""
    settings = m.HotelSettings.objects.get_or_create(pk=1)[0]
    zone = ZoneInfo(settings.timezone)
    try:
        anchor = datetime.fromisoformat(
            params.get("date", timezone.now().astimezone(zone).date().isoformat())
        ).date()
    except (ValueError, TypeError) as exc:
        raise ValidationError({"date": "Data richiesta nel formato YYYY-MM-DD."}) from exc
    name = params.get("period", "month")
    if name == "week":
        start_date = anchor - timedelta(days=anchor.weekday())
        end_date = start_date + timedelta(days=7)
    elif name == "month":
        start_date = anchor.replace(day=1)
        end_date = (
            start_date.replace(year=start_date.year + 1, month=1)
            if start_date.month == 12
            else start_date.replace(month=start_date.month + 1)
        )
    elif name == "year":
        start_date = anchor.replace(month=1, day=1)
        end_date = start_date.replace(year=start_date.year + 1)
    else:
        raise ValidationError({"period": "Scegliere week, month oppure year."})
    return name, datetime.combine(start_date, time.min, zone), datetime.combine(end_date, time.min, zone)


def tips(params):
    name, start, end = tip_period(params)
    payments = m.Payment.objects.select_related("created_by").filter(
        created_at__gte=start,
        created_at__lt=end,
        tip_amount__gt=0,
        reverses__isnull=True,
    )
    return {
        "period": name,
        "start_date": start.date().isoformat(),
        "end_date": (end - timedelta(days=1)).date().isoformat(),
        "total": str(payments.aggregate(total=Sum("tip_amount"))["total"] or ZERO),
        "count": payments.count(),
        "payments": payments,
    }


def filtered_movements(params):
    start, end = period(params)
    qs = m.CashMovement.objects.select_related("created_by").filter(created_at__gte=start, created_at__lt=end)
    if params.get("method"):
        if params["method"] not in dict(m.METHODS):
            raise ValidationError({"method": "Metodo non valido."})
        qs = qs.filter(method=params["method"])
    if params.get("operator"):
        try:
            operator = int(params["operator"])
        except ValueError as exc:
            raise ValidationError({"operator": "Identificativo non valido."}) from exc
        if operator < 1:
            raise ValidationError({"operator": "Identificativo non valido."})
        qs = qs.filter(created_by_id=operator)
    if params.get("shift"):
        try:
            shift = int(params["shift"])
        except ValueError as exc:
            raise ValidationError({"shift": "Identificativo non valido."}) from exc
        if shift < 1:
            raise ValidationError({"shift": "Identificativo non valido."})
        qs = qs.filter(shift_id=shift)
    if params.get("direction"):
        if params["direction"] not in ("in", "out"):
            raise ValidationError({"direction": "Scegliere in oppure out."})
        qs = qs.filter(direction=params["direction"])
    return qs


def operator_shift_totals(movements, zone):
    """Count actual receipts once; refunds and manual expenses only reduce cash.

    Charge allocations split incoming receipts into camera/extra without joining
    the movement queryset, which would multiply payment totals across its lines.
    Prefetching the allocations keeps the query count independent of receipts.
    """
    movements = movements.select_related("payment").prefetch_related(
        Prefetch("payment__allocations", queryset=m.PaymentAllocation.objects.select_related("charge"))
    )
    grouped = {}
    for movement in movements:
        day = movement.created_at.astimezone(zone).date().isoformat()
        key = (movement.created_by_id, movement.shift_id, day)
        if key not in grouped:
            grouped[key] = {
                "operator_id": movement.created_by_id,
                "operator_name": movement.created_by.get_full_name() or movement.created_by.email,
                "shift": movement.shift_id,
                "day": day,
                "movements_count": 0,
                "room_income": ZERO,
                "extra_income": ZERO,
                "income": ZERO,
                "expenses": ZERO,
            }
        row = grouped[key]
        row["movements_count"] += 1
        if movement.direction == "out":
            row["expenses"] += movement.amount
            continue
        # Tips remain in the cash/card movement for reconciliation, while this
        # report represents revenue earned by the structure.
        row["income"] += movement.amount - movement.tip_amount
        if movement.payment_id and not movement.payment.reverses_id:
            for allocation in movement.payment.allocations.all():
                row[f"{allocation.charge.kind}_income"] += allocation.amount
    result = []
    for row in sorted(grouped.values(), key=lambda row: (row["day"], row["operator_id"], row["shift"] or 0)):
        row["balance"] = row["income"] - row["expenses"]
        for key in ("room_income", "extra_income", "income", "expenses", "balance"):
            row[key] = format(row[key], ".2f")
        result.append(row)
    return result


REPORT_SECTION_META = (
    ("rooms", "Camere"),
    ("extras", "Extra"),
    ("tips", "Mance"),
    ("expenses", "Spese e rimborsi"),
    ("other_income", "Altre entrate"),
)


def payment_account(payment):
    if payment.stay_id:
        return f"Camera {payment.stay.room.number}"
    rooms = sorted({stay.room.number for stay in payment.group.stays.all()})
    return f"Gruppo {payment.group.name} - camere {', '.join(rooms) or '-'}"


def report_sections(movements, zone):
    """Split every movement once into the business section it belongs to.

    A payment spanning rooms and extras is split by its allocations. Tips and
    outgoing refunds/expenses are independent sections, so the final report is
    readable without counting any amount twice.
    """
    movements = movements.select_related(
        "created_by", "payment__stay__room", "payment__group"
    ).prefetch_related(
        Prefetch(
            "payment__allocations",
            queryset=m.PaymentAllocation.objects.select_related("charge__stay__room"),
        ),
        "payment__group__stays__room",
    )
    rows = {key: [] for key, _ in REPORT_SECTION_META}

    def append(section, movement, amount, account="-"):
        rows[section].append(
            {
                "id": f"{movement.pk}-{section}-{len(rows[section])}",
                "created_at": movement.created_at.astimezone(zone).isoformat(),
                "display_date": movement.created_at.astimezone(zone).strftime("%d/%m/%Y %H:%M"),
                "account": account,
                "direction": movement.direction,
                "amount": str(amount),
                "method": movement.method,
                "reason": movement.reason,
                "description": movement.description,
                "operator_name": movement.created_by.get_full_name() or movement.created_by.email,
                "shift": movement.shift_id,
            }
        )

    for movement in movements:
        if movement.direction == "out":
            append("expenses", movement, movement.amount)
            continue
        if not movement.payment_id:
            append("other_income", movement, movement.amount)
            continue
        for allocation in movement.payment.allocations.all():
            section = "rooms" if allocation.charge.kind == "room" else "extras"
            append(section, movement, allocation.amount, f"Camera {allocation.charge.stay.room.number}")
        if movement.tip_amount:
            append("tips", movement, movement.tip_amount, payment_account(movement.payment))

    result = []
    for key, label in REPORT_SECTION_META:
        section_rows = rows[key]
        if key == "other_income" and not section_rows:
            continue
        result.append(
            {
                "key": key,
                "label": label,
                "total": str(sum((Decimal(row["amount"]) for row in section_rows), ZERO)),
                "rows": section_rows,
            }
        )
    return result


def report(params):
    start, end = period(params)
    movements = filtered_movements(params)
    incoming = movements.filter(direction="in")
    income = (incoming.aggregate(s=Sum("amount"))["s"] or ZERO) - (
        incoming.aggregate(s=Sum("tip_amount"))["s"] or ZERO
    )
    expenses = movements.filter(direction="out").aggregate(s=Sum("amount"))["s"] or ZERO
    outstanding = outstanding_balance()
    segments = m.StaySegment.objects.filter(active=True, arrival__lt=end, departure__gt=start)
    occupied_seconds = sum(
        (
            Decimal(
                str(
                    (
                        min(x.departure, end).astimezone(UTC) - max(x.arrival, start).astimezone(UTC)
                    ).total_seconds()
                )
            )
            for x in segments
        ),
        ZERO,
    )
    room_count = m.Room.objects.filter(is_active=True).count()
    available = Decimal(str((end.astimezone(UTC) - start.astimezone(UTC)).total_seconds())) * room_count
    occupancy = str((occupied_seconds / available * 100).quantize(Decimal("0.01"))) if available else "0.00"
    operators = list(
        movements.values("created_by_id", "created_by__email", "direction").annotate(
            amount=Sum("amount"), tips=Sum("tip_amount")
        )
    )
    for operator in operators:
        amount = operator["amount"] - (operator["tips"] or ZERO) if operator["direction"] == "in" else operator["amount"]
        operator["amount"] = format(amount, ".2f")
        del operator["tips"]
    return {
        "income": str(income),
        "expenses": str(expenses),
        "balance": str(income - expenses),
        "outstanding": str(outstanding),
        "occupancy": occupancy,
        "operators": operators,
        "by_operator_shift": operator_shift_totals(movements, start.tzinfo),
        "sections": report_sections(movements, start.tzinfo),
    }


def today_bounds():
    settings = m.HotelSettings.objects.get_or_create(pk=1)[0]
    zone = ZoneInfo(settings.timezone)
    now = timezone.now()
    today = now.astimezone(zone).date()
    start = datetime.combine(today, time.min, zone)
    end = start + timedelta(days=1)
    return now, start, end


def dashboard_stays(bounds=None):
    _, start, end = bounds or today_bounds()
    arrivals = (
        stays()
        .filter(arrival__gte=start, arrival__lt=end, status__in=["reserved", "checked_in"])
        .order_by("arrival", "pk")
    )
    departures = (
        stays()
        .filter(
            departure__gte=start,
            departure__lt=end,
            status__in=["reserved", "checked_in", "checked_out"],
        )
        .order_by("departure", "pk")
    )
    return arrivals, departures


def dashboard(bounds=None):
    now, start, end = bounds or today_bounds()
    outstanding = outstanding_balance()
    incoming_movements = m.CashMovement.objects.filter(
        direction="in", created_at__gte=start, created_at__lt=end
    )
    incoming = (incoming_movements.aggregate(s=Sum("amount"))["s"] or ZERO) - (
        incoming_movements.aggregate(s=Sum("tip_amount"))["s"] or ZERO
    )
    return {
        "rooms_total": m.Room.objects.filter(is_active=True).count(),
        "rooms_occupied": m.StaySegment.objects.filter(
            active=True, arrival__lte=now, departure__gt=now, stay__status="checked_in"
        )
        .values("room")
        .distinct()
        .count(),
        "arrivals_today": m.Stay.objects.filter(
            arrival__gte=start, arrival__lt=end, status__in=["reserved", "checked_in"]
        ).count(),
        "departures_today": m.Stay.objects.filter(
            departure__gte=start, departure__lt=end, status__in=["reserved", "checked_in", "checked_out"]
        ).count(),
        "outstanding": str(outstanding),
        "income_today": str(incoming),
        "low_stock_count": m.StockItem.objects.filter(
            is_active=True, quantity__lte=F("minimum_stock")
        ).count(),
    }
