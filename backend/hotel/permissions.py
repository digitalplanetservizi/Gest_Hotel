from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated

from .models import HotelSettings, PlatformLicense


def is_superadmin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == "superadmin"))


def is_administrator(user):
    return bool(user and user.is_authenticated and (is_superadmin(user) or user.role == "admin"))


def license_status():
    license, _ = PlatformLicense.objects.get_or_create(pk=1)
    zone = HotelSettings.objects.filter(pk=1).values_list("timezone", flat=True).first() or "Europe/Rome"
    today = timezone.now().astimezone(ZoneInfo(zone)).date()
    expired = license.expires_on is not None and license.expires_on < today
    return {
        "enabled": license.enabled,
        "expires_on": license.expires_on,
        "active": license.enabled and not expired,
        "status": "disabled" if not license.enabled else "expired" if expired else "active",
        "timezone": zone,
    }


class IsLicensedAuthenticated(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not is_superadmin(request.user) and not license_status()["active"]:
            raise PermissionDenied(
                {
                    "detail": "Licenza scaduta o disattivata. Contatta il superadmin.",
                    "code": "license_inactive",
                }
            )
        return True


class IsAdministrator(IsLicensedAuthenticated):
    message = "Questa funzione è riservata agli amministratori."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_administrator(request.user)


class AdministratorOrReadOnly(IsLicensedAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (
            request.method in SAFE_METHODS or is_administrator(request.user)
        )


class IsSuperadmin(IsAuthenticated):
    message = "Questa funzione è riservata ai superadmin."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_superadmin(request.user)
