"""Signed business-data backups, restored atomically under the property write mutex."""

import json
from datetime import datetime

from django.core import serializers, signing
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import models as m
from .services import audit, mutex

MAX_BACKUP_BYTES = 20 * 1024 * 1024
SALT = "hotel.business-backup.v1"


class BackupJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        # Django's default encoder truncates datetimes to milliseconds.
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Dependency order. Users, license, sessions, recovery copies and audit remain untouched.
MODELS = [
    m.Group,
    m.Room,
    m.Rate,
    m.ExtraCategory,
    m.PriceItem,
    m.CashReason,
    m.StockItem,
    m.Stay,
    m.StaySegment,
    m.Charge,
    m.Shift,
    m.Payment,
    m.PaymentAllocation,
    m.CashMovement,
    m.StockMovement,
    m.IdempotencyRecord,
]


def snapshot():
    objects = [m.HotelSettings.objects.get(pk=1)]
    for model in MODELS:
        objects.extend(model.objects.order_by("pk"))
    payload = {
        "version": 1,
        "created_at": timezone.now().isoformat(),
        "users": list(m.User.objects.order_by("pk").values("id", "email")),
        "objects": json.loads(serializers.serialize("json", objects, cls=BackupJSONEncoder)),
    }
    signed = signing.dumps(payload, salt=SALT)
    if len(signed.encode("utf-8")) + 100 > MAX_BACKUP_BYTES:
        raise ValidationError("Backup superiore a 20 MB: utilizzare il backup PostgreSQL da server.")
    return signed


def read_backup(upload):
    if not upload or upload.size > MAX_BACKUP_BYTES:
        raise ValidationError({"file": "Seleziona un backup applicativo di massimo 20 MB."})
    try:
        envelope = json.loads(upload.read(MAX_BACKUP_BYTES + 1))
        if not isinstance(envelope, dict) or not isinstance(envelope.get("signed_data"), str):
            raise ValueError
        payload = signing.loads(envelope["signed_data"], salt=SALT)
        if payload["version"] != 1 or not isinstance(payload["objects"], list):
            raise ValueError
        allowed = {model._meta.label_lower for model in MODELS} | {"hotel.hotelsettings"}
        seen = set()
        for obj in payload["objects"]:
            key = (obj["model"], obj["pk"])
            if obj["model"] not in allowed or key in seen:
                raise ValueError
            seen.add(key)
        if ("hotel.hotelsettings", 1) not in seen:
            raise ValueError
        if any(obj["model"] == "hotel.hotelsettings" and obj["pk"] != 1 for obj in payload["objects"]):
            raise ValueError
        return payload
    except (ValueError, KeyError, TypeError, RecursionError, signing.BadSignature) as exc:
        raise ValidationError({"file": "Backup non valido, alterato o di un'altra installazione."}) from exc


@transaction.atomic
def restore(payload, actor):
    mutex()
    current_users = dict(m.User.objects.values_list("id", "email"))
    if any(current_users.get(user["id"]) != user["email"] for user in payload["users"]):
        raise ValidationError("Gli account del backup non corrispondono a questa installazione.")
    recovery = m.RecoveryBackup.objects.create(created_by=actor, signed_data=snapshot())
    # Raw deletes avoid Django PROTECT on references that are all replaced together.
    # PostgreSQL FKs are deferred until all restored rows are in place.
    with connection.cursor() as cursor:
        for model in reversed(MODELS):
            cursor.execute(f"DELETE FROM {connection.ops.quote_name(model._meta.db_table)}")
    try:
        for obj in serializers.deserialize("json", json.dumps(payload["objects"]), ignorenonexistent=False):
            obj.save()
        connection.check_constraints()
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                for model in MODELS:
                    table = model._meta.db_table
                    cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", [table, model._meta.pk.column])
                    sequence = cursor.fetchone()[0]
                    # Sequence names come from PostgreSQL metadata, never from the backup.
                    cursor.execute(f"SELECT last_value FROM {sequence}")
                    previous = cursor.fetchone()[0]
                    cursor.execute(f"SELECT COALESCE(MAX(id), 1) FROM {connection.ops.quote_name(table)}")
                    maximum = cursor.fetchone()[0]
                    # PostgreSQL sequences are not transactional: never lower them on restore.
                    cursor.execute(
                        "SELECT setval(%s::regclass, %s, true)", [sequence, max(previous, maximum)]
                    )
    except (serializers.base.DeserializationError, ValueError, TypeError) as exc:
        raise ValidationError("Dati del backup incompatibili: nessuna modifica applicata.") from exc
    audit(actor, "backup.restored", recovery, {"backup_created_at": payload["created_at"]})
    return recovery
