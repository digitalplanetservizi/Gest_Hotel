import csv
import io
import itertools
import json
import zipfile
from datetime import timedelta

from django.apps import apps
from django.contrib.auth import authenticate, login, logout
from django.core import serializers as django_serializers
from django.db import connection, transaction
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers as drfs
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import models as m
from .. import selectors
from .. import serializers as s
from .. import services as domain
from ..pdf_reports import build_cash_report_pdf
from ..permissions import AdministratorOrReadOnly, IsAdministrator, is_administrator


def validated(cls, data, **kwargs):
    serializer = cls(data=data, **kwargs)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def page(request, queryset, serializer):
    try:
        size = min(max(int(request.query_params.get("page_size", 100)), 1), 500)
        number = max(int(request.query_params.get("page", 1)), 1)
    except ValueError as exc:
        raise ValidationError("Paginazione non valida.") from exc
    count = queryset.count()
    return Response(
        {"count": count, "results": serializer(queryset[(number - 1) * size : number * size], many=True).data}
    )


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return Response({"status": "ok", "database": "ok"})
        except Exception:
            return Response({"status": "unavailable"}, status=503)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginInput(drfs.Serializer):
    email = drfs.EmailField()
    password = drfs.CharField(trim_whitespace=False)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        data = validated(LoginInput, request.data)
        account = m.User.objects.filter(email__iexact=data["email"]).first()
        user = authenticate(
            request, username=account.username if account else data["email"], password=data["password"]
        )
        if not user:
            return Response({"detail": "Credenziali non valide."}, status=400)
        login(request, user)
        domain.audit(user, "auth.logged_in", user)
        return Response(s.UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        domain.audit(request.user, "auth.logged_out", request.user)
        logout(request)
        return Response(status=204)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(s.UserSerializer(request.user).data)


class SettingsView(APIView):
    permission_classes = [AdministratorOrReadOnly]

    def get(self, request):
        obj, _ = m.HotelSettings.objects.get_or_create(pk=1)
        return Response(s.HotelSettingsSerializer(obj).data)

    @transaction.atomic
    def patch(self, request):
        obj = domain.mutex()
        serializer = s.HotelSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        domain.audit(request.user, "settings.updated", obj, {"fields": list(request.data)})
        return Response(serializer.data)


class ResourceView(APIView):
    """Shared thin APIView for simple configurable catalog resources."""

    model = None
    serializer = None

    def get(self, request, pk=None):
        if pk:
            return Response(self.serializer(get_object_or_404(self.model, pk=pk)).data)
        qs = self.model.objects.all().order_by("pk")
        if request.query_params.get("search"):
            field = "email" if self.model == m.User else "number" if self.model == m.Room else "name"
            if self.model == m.PriceItem:
                field = "description"
            qs = qs.filter(**{f"{field}__icontains": request.query_params["search"]})
        return page(request, qs, self.serializer)

    @transaction.atomic
    def post(self, request, pk=None):
        if pk:
            return Response(status=405)
        domain.mutex()
        serializer = self.serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        domain.audit(request.user, "resource.created", obj)
        return Response(self.serializer(obj).data, status=201)

    @transaction.atomic
    def patch(self, request, pk):
        domain.mutex()
        obj = get_object_or_404(self.model.objects.select_for_update(), pk=pk)
        if self.model == m.Room:
            if (
                request.data.get("is_active") is False
                and m.StaySegment.objects.filter(room=obj, active=True, departure__gt=timezone.now()).exists()
            ):
                raise ValidationError("Impossibile disattivare una camera con soggiorni correnti o futuri.")
            if "capacity" in request.data:
                try:
                    capacity = int(request.data["capacity"])
                except (ValueError, TypeError) as exc:
                    raise ValidationError({"capacity": "Valore non valido."}) from exc
                if m.StaySegment.objects.filter(
                    room=obj, active=True, departure__gt=timezone.now(), stay__guest_count__gt=capacity
                ).exists():
                    raise ValidationError({"capacity": "Capienza incompatibile con prenotazioni esistenti."})
        serializer = self.serializer(obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        domain.audit(request.user, "resource.updated", obj, {"fields": list(request.data)})
        return Response(self.serializer(obj).data)

    @transaction.atomic
    def delete(self, request, pk):
        if self.model not in (m.PriceItem, m.ExtraCategory):
            return Response(status=405)
        if not is_administrator(request.user):
            raise PermissionDenied("L'eliminazione dal listino è riservata agli amministratori.")
        domain.mutex()
        obj = get_object_or_404(self.model.objects.select_for_update(), pk=pk)
        if self.model == m.ExtraCategory and obj.price_items.exists():
            raise ValidationError(
                {"detail": "Sposta o elimina prima gli extra collegati a questa categoria."}
            )
        label = obj.description if self.model == m.PriceItem else obj.name
        domain.audit(request.user, "resource.deleted", obj, {"label": label})
        obj.delete()
        return Response(status=204)


class RoomsView(ResourceView):
    permission_classes = [AdministratorOrReadOnly]
    model, serializer = m.Room, s.RoomSerializer


class GroupsView(ResourceView):
    model, serializer = m.Group, s.GroupSerializer


class RatesView(ResourceView):
    permission_classes = [AdministratorOrReadOnly]
    model, serializer = m.Rate, s.RateSerializer


class PriceItemsView(ResourceView):
    permission_classes = [AdministratorOrReadOnly]
    model, serializer = m.PriceItem, s.PriceItemSerializer

    def get(self, request, pk=None):
        if pk:
            return Response(self.serializer(get_object_or_404(self.model, pk=pk)).data)
        qs = self.model.objects.select_related("category").all().order_by("pk")
        if request.query_params.get("search"):
            qs = qs.filter(description__icontains=request.query_params["search"])
        category = request.query_params.get("category")
        if category:
            if not category.isdigit():
                raise ValidationError({"category": "Identificativo categoria non valido."})
            qs = qs.filter(category_id=category)
        return page(request, qs, self.serializer)


class ExtraCategoriesView(ResourceView):
    permission_classes = [AdministratorOrReadOnly]
    model, serializer = m.ExtraCategory, s.ExtraCategorySerializer


class AuditEventsView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        qs = m.AuditEvent.objects.select_related("actor").order_by("-created_at", "-pk")
        actor = request.query_params.get("actor")
        if actor:
            if not actor.isdigit():
                raise ValidationError({"actor": "Identificativo operatore non valido."})
            qs = qs.filter(actor_id=actor)
        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action__icontains=action)
        return page(request, qs, s.AuditEventSerializer)


class BackupExportView(APIView):
    """Portable administrative export of every business model in the hotel app."""

    permission_classes = [IsAdministrator]

    @transaction.atomic
    def get(self, request):
        domain.mutex()
        domain.audit(request.user, "backup.exported", request.user)
        models = apps.get_app_config("hotel").get_models()
        objects = itertools.chain.from_iterable(
            model._default_manager.all().order_by("pk") for model in models
        )
        payload = {
            "format": "hotel-tempio-backup",
            "version": 1,
            "exported_at": timezone.now().isoformat(),
            "objects": json.loads(django_serializers.serialize("json", objects)),
        }
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as file:
            file.writestr("hotel-backup.json", json.dumps(payload, ensure_ascii=False, indent=2))
        filename = f"backup-hotel-{timezone.localtime():%Y%m%d-%H%M%S}.zip"
        response = HttpResponse(archive.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ReasonsView(ResourceView):
    permission_classes = [AdministratorOrReadOnly]
    model, serializer = m.CashReason, s.ReasonSerializer


class StockItemsView(ResourceView):
    model, serializer = m.StockItem, s.StockItemSerializer


class UsersView(ResourceView):
    permission_classes = [IsAdministrator]
    model, serializer = m.User, s.UserSerializer


class StaysView(APIView):
    def get(self, request, pk=None):
        qs = selectors.stays()
        if pk:
            return Response(s.StaySerializer(get_object_or_404(qs, pk=pk)).data)
        for field in ("status", "room", "group"):
            if request.query_params.get(field):
                value = request.query_params[field]
                if field != "status" and not value.isdigit():
                    raise ValidationError({field: "Identificativo non valido."})
                qs = qs.filter(**{field: value})
        if request.query_params.get("search"):
            qs = qs.filter(guest_name__icontains=request.query_params["search"])
        return page(request, qs, s.StaySerializer)

    def post(self, request):
        data = validated(s.StayWriteSerializer, request.data)
        stay = domain.save_stay(data, request.user)
        return Response(s.StaySerializer(stay).data, status=201)

    def patch(self, request, pk):
        stay = get_object_or_404(m.Stay, pk=pk)
        data = validated(s.StayWriteSerializer, request.data, instance=stay, partial=True)
        return Response(s.StaySerializer(domain.save_stay(data, request.user, stay)).data)


class QuoteView(APIView):
    def post(self, request):
        data = validated(s.StayWriteSerializer, request.data)
        return Response(domain.quote(data))


class StayActionView(APIView):
    def post(self, request, pk, action):
        cls = {"check-in": s.CheckInInput, "move": s.MoveInput, "extend": s.ExtendInput}.get(action)
        data = validated(cls, request.data) if cls else {}
        return Response(s.StaySerializer(domain.stay_action(pk, action, data, request.user)).data)


class PlanningView(APIView):
    def get(self, request):
        start, end = selectors.period(request.query_params, max_days=93)
        qs = selectors.stays().filter(segments__arrival__lt=end, segments__departure__gt=start).distinct()
        return Response(
            {
                "rooms": s.RoomSerializer(m.Room.objects.all(), many=True).data,
                "stays": s.StaySerializer(qs, many=True).data,
                "groups": s.GroupSerializer(m.Group.objects.filter(is_active=True), many=True).data,
            }
        )


class DashboardView(APIView):
    def get(self, request):
        bounds = selectors.today_bounds()
        result = selectors.dashboard(bounds)
        arrivals, departures = selectors.dashboard_stays(bounds)
        result["arrivals"] = s.StaySerializer(arrivals, many=True).data
        result["departures"] = s.StaySerializer(departures, many=True).data
        return Response(result)


class GroupStatementView(APIView):
    def get(self, request, pk):
        group = get_object_or_404(m.Group, pk=pk)
        qs = selectors.stays().filter(group=group)
        charges = m.Charge.objects.filter(stay__group=group).prefetch_related("allocations")
        result = {key: str(value) for key, value in domain.statement(charges).items()}
        result.update(
            group=s.GroupSerializer(group).data,
            stays=s.StaySerializer(qs, many=True).data,
            charges=s.ChargeSerializer(charges.select_related("created_by"), many=True).data,
            payments=s.PaymentSerializer(group.payments.select_related("created_by"), many=True).data,
        )
        return Response(result)


class ChargesView(APIView):
    def get(self, request, pk):
        stay = get_object_or_404(m.Stay, pk=pk)
        return page(
            request,
            stay.charges.select_related("created_by").prefetch_related("allocations"),
            s.ChargeSerializer,
        )

    def post(self, request, pk):
        stay = get_object_or_404(m.Stay, pk=pk)
        data = validated(s.AddChargeSerializer, request.data)
        return Response(s.ChargeSerializer(domain.add_charge(stay, data, request.user)).data, status=201)


class VoidChargeView(APIView):
    def post(self, request, pk):
        charge = get_object_or_404(m.Charge, pk=pk)
        data = validated(s.ReasonInput, request.data)
        return Response(s.ChargeSerializer(domain.void_charge(charge, data["reason"], request.user)).data)


class PaymentsView(APIView):
    def get(self, request):
        qs = m.Payment.objects.select_related("created_by")
        for field in ("stay", "group"):
            if request.query_params.get(field):
                if not request.query_params[field].isdigit():
                    raise ValidationError({field: "Identificativo non valido."})
                qs = qs.filter(**{field: request.query_params[field]})
        return page(request, qs, s.PaymentSerializer)

    def post(self, request):
        data = validated(s.PaymentWriteSerializer, request.data)
        result = domain.record_payment(data, request.user, request.headers.get("Idempotency-Key"))
        return Response(s.PaymentSerializer(result).data, status=201)


class RefundView(APIView):
    def post(self, request, pk):
        payment = get_object_or_404(m.Payment, pk=pk)
        data = validated(s.RefundSerializer, request.data)
        result = domain.refund_payment(payment, data, request.user, request.headers.get("Idempotency-Key"))
        return Response(s.PaymentSerializer(result).data, status=201)


class TipsView(APIView):
    """Dedicated read model for tips, independent from room-account balances."""

    def get(self, request):
        result = selectors.tips(request.query_params)
        payments = result.pop("payments")
        result["payments"] = s.PaymentSerializer(payments[:1000], many=True).data
        return Response(result)


class ShiftsView(APIView):
    def get(self, request):
        return page(request, m.Shift.objects.select_related("opened_by"), s.ShiftSerializer)

    def post(self, request):
        data = validated(s.OpenShiftSerializer, request.data)
        return Response(s.ShiftSerializer(domain.open_shift(data, request.user)).data, status=201)


class CloseShiftView(APIView):
    def post(self, request, pk):
        shift = get_object_or_404(m.Shift, pk=pk)
        data = validated(s.CloseShiftSerializer, request.data)
        return Response(s.ShiftSerializer(domain.close_shift(shift, data, request.user)).data)


class MovementsView(APIView):
    def get(self, request):
        return page(request, selectors.filtered_movements(request.query_params), s.MovementSerializer)

    def post(self, request):
        data = validated(s.ExpenseSerializer, request.data)
        return Response(s.MovementSerializer(domain.manual_expense(data, request.user)).data, status=201)


class IncomeView(APIView):
    def post(self, request):
        data = validated(s.IncomeSerializer, request.data)
        return Response(s.MovementSerializer(domain.manual_income(data, request.user)).data, status=201)


class StockMovementsView(APIView):
    def get(self, request):
        qs = m.StockMovement.objects.select_related("created_by", "item").order_by("-created_at")
        return page(request, qs, s.StockMovementSerializer)

    def post(self, request):
        data = validated(s.StockMovementSerializer, request.data)
        return Response(s.StockMovementSerializer(domain.stock_movement(data, request.user)).data, status=201)


class ReportsView(APIView):
    def get(self, request):
        result = selectors.report(request.query_params)
        qs = selectors.filtered_movements(request.query_params)
        result["movements"] = s.MovementSerializer(qs[:1000], many=True).data
        result["movements_count"] = qs.count()
        return Response(result)


class ExportReportView(APIView):
    def get(self, request):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        start, end = selectors.period(request.query_params)
        report = selectors.report(request.query_params)
        writer.writerow(["RAPPORTO DI CASSA"])
        writer.writerow(["Periodo", start.date().isoformat(), (end - timedelta(days=1)).date().isoformat()])
        writer.writerow(["Generato il", timezone.localtime().strftime("%d/%m/%Y %H:%M")])
        writer.writerow([])

        def safe(value):
            value = str(value)
            return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value

        for section in report["sections"]:
            writer.writerow([section["label"].upper(), f"Totale: {section['total']} EUR"])
            writer.writerow(
                ["Data e ora", "Camera / conto", "Direzione", "Importo EUR", "Metodo", "Causale", "Descrizione", "Operatore", "Turno"]
            )
            for row in section["rows"]:
                writer.writerow(
                    [
                        row["display_date"],
                        safe(row["account"]),
                        "Entrata" if row["direction"] == "in" else "Uscita",
                        row["amount"],
                        row["method"],
                        safe(row["reason"]),
                        safe(row["description"]),
                        safe(row["operator_name"]),
                        f"#{row['shift']}" if row["shift"] else "",
                    ]
                )
            writer.writerow([])
        response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="report-cassa.csv"'
        return response


class PdfReportView(APIView):
    def get(self, request):
        start, end = selectors.period(request.query_params)
        report = selectors.report(request.query_params)
        hotel, _ = m.HotelSettings.objects.get_or_create(pk=1)
        content = build_cash_report_pdf(
            hotel=hotel,
            report=report,
            sections=report["sections"],
            start=start,
            end=end,
            generated_at=timezone.now().astimezone(start.tzinfo),
            filters=request.query_params,
        )
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="rapporto-cassa.pdf"'
        return response
