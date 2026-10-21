import json

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import backups
from .. import models as m
from ..permissions import IsSuperadmin, license_status
from ..services import audit, mutex


class LicenseInput(serializers.ModelSerializer):
    class Meta:
        model = m.PlatformLicense
        fields = ["enabled", "expires_on"]


class LicenseStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(license_status())


class LicenseView(APIView):
    permission_classes = [IsSuperadmin]

    def get(self, request):
        return Response(license_status())

    @transaction.atomic
    def patch(self, request):
        mutex()
        obj, _ = m.PlatformLicense.objects.get_or_create(pk=1)
        serializer = LicenseInput(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit(request.user, "license.updated", obj, dict(serializer.data))
        return Response(license_status())


def backup_response(signed_data, name):
    response = HttpResponse(
        json.dumps({"format": "hotel-business-backup-v1", "signed_data": signed_data}),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="{name}.hotel-backup.json"'
    response["Cache-Control"] = "no-store"
    return response


class BackupView(APIView):
    permission_classes = [IsSuperadmin]

    @transaction.atomic
    def get(self, request):
        settings = mutex()
        signed_data = backups.snapshot()
        audit(request.user, "backup.exported", settings)
        return backup_response(signed_data, timezone.now().strftime("hotel-%Y%m%d-%H%M%S"))


class RestoreView(APIView):
    permission_classes = [IsSuperadmin]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "restore"

    def post(self, request):
        if request.data.get("confirmation") != "RIPRISTINA":
            raise ValidationError(
                {"confirmation": "Scrivi RIPRISTINA per confermare la sostituzione dei dati."}
            )
        if not request.user.check_password(request.data.get("password", "")):
            raise ValidationError({"password": "Password del superadmin non valida."})
        payload = backups.read_backup(request.FILES.get("file"))
        recovery = backups.restore(payload, request.user)
        return Response(
            {
                "detail": "Ripristino completato. Account, licenza e registro attività conservati.",
                "recovery_backup_id": recovery.pk,
            }
        )


class RecoveryBackupsView(APIView):
    permission_classes = [IsSuperadmin]

    def get(self, request, pk=None):
        if pk is not None:
            backup = get_object_or_404(m.RecoveryBackup, pk=pk)
            return backup_response(backup.signed_data, f"sicurezza-{backup.pk}")
        return Response(
            list(m.RecoveryBackup.objects.order_by("-created_at").values("id", "created_at")[:100])
        )
