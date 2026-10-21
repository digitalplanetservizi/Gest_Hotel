"""Django inspection console. Business writes remain in the transactional application APIs."""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .services import audit


def can_access_backend(user):
    # Staff flags and individually granted Django permissions never bypass the role.
    return bool(user.is_authenticated and user.is_active and user.role == "superadmin")


class SuperadminAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not can_access_backend(user):
            raise ValidationError(
                "Il pannello Django è riservato ai superadmin attivi.", code="invalid_login"
            )


class SuperadminSite(admin.AdminSite):
    site_header = "Hotel Tempio · Backend Django"
    site_title = "Backend Hotel Tempio"
    index_title = "Consultazione dati · Solo superadmin"
    site_url = "/superadmin"
    login_form = SuperadminAuthenticationForm

    def has_permission(self, request):
        return can_access_backend(request.user)

    def login(self, request, extra_context=None):
        response = super().login(request, extra_context)
        if request.method == "POST" and response.status_code == 302 and self.has_permission(request):
            audit(request.user, "auth.logged_in", request.user, {"source": "django_admin"})
        return response

    def logout(self, request, extra_context=None):
        if request.method == "POST" and self.has_permission(request):
            audit(request.user, "auth.logged_out", request.user, {"source": "django_admin"})
        return super().logout(request, extra_context)


class InspectionAdmin(admin.ModelAdmin):
    actions = None
    list_per_page = 50

    def has_module_permission(self, request):
        return can_access_backend(request.user)

    def has_view_permission(self, request, obj=None):
        return can_access_backend(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_exclude(self, request, obj=None):
        # Neither password hashes nor signed recovery payloads are useful in the console.
        return [field.name for field in self.model._meta.fields if field.name in ("password", "signed_data")]


backend_admin = SuperadminSite(name="backend_admin")
for model in apps.get_app_config("hotel").get_models():
    backend_admin.register(model, InspectionAdmin)
