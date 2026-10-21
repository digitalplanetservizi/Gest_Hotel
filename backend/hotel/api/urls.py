from django.urls import path

from . import views as v
from .extra_views import ExtraStatementView
from .superadmin_views import BackupView, LicenseStatusView, LicenseView, RecoveryBackupsView, RestoreView

urlpatterns = [
    path("license/", LicenseStatusView.as_view()),
    path("superadmin/license/", LicenseView.as_view()),
    path("superadmin/backup/", BackupView.as_view()),
    path("superadmin/restore/", RestoreView.as_view()),
    path("superadmin/recovery-backups/", RecoveryBackupsView.as_view()),
    path("superadmin/recovery-backups/<int:pk>/", RecoveryBackupsView.as_view()),
    path("health/", v.HealthView.as_view()),
    path("auth/csrf/", v.CsrfView.as_view()),
    path("auth/login/", v.LoginView.as_view()),
    path("auth/logout/", v.LogoutView.as_view()),
    path("auth/me/", v.MeView.as_view()),
    path("settings/", v.SettingsView.as_view()),
    path("dashboard/", v.DashboardView.as_view()),
    path("planning/", v.PlanningView.as_view()),
    path("stays/quote/", v.QuoteView.as_view()),
    path("stays/", v.StaysView.as_view()),
    path("stays/<int:pk>/", v.StaysView.as_view()),
    path("stays/<int:pk>/charges/", v.ChargesView.as_view()),
    path("stays/<int:pk>/extras/pdf/", ExtraStatementView.as_view()),
    path("charges/<int:pk>/void/", v.VoidChargeView.as_view()),
    path("groups/<int:pk>/statement/", v.GroupStatementView.as_view()),
    path("groups/<int:pk>/extras/pdf/", ExtraStatementView.as_view(), {"scope": "group"}),
    path("payments/", v.PaymentsView.as_view()),
    path("payments/<int:pk>/refund/", v.RefundView.as_view()),
    path("tips/", v.TipsView.as_view()),
    path("cash/shifts/", v.ShiftsView.as_view()),
    path("cash/shifts/<int:pk>/close/", v.CloseShiftView.as_view()),
    path("cash/movements/", v.MovementsView.as_view()),
    path("cash/movements/income/", v.IncomeView.as_view()),
    path("inventory/movements/", v.StockMovementsView.as_view()),
    path("reports/", v.ReportsView.as_view()),
    path("reports/export/", v.ExportReportView.as_view()),
    path("reports/pdf/", v.PdfReportView.as_view()),
    path("audit-events/", v.AuditEventsView.as_view()),
    path("backup/export/", v.BackupExportView.as_view()),
]
for prefix, view in [
    ("rooms", v.RoomsView),
    ("groups", v.GroupsView),
    ("rates", v.RatesView),
    ("extra-categories", v.ExtraCategoriesView),
    ("price-items", v.PriceItemsView),
    ("cash/reasons", v.ReasonsView),
    ("inventory/items", v.StockItemsView),
    ("users", v.UsersView),
]:
    urlpatterns += [path(f"{prefix}/", view.as_view()), path(f"{prefix}/<int:pk>/", view.as_view())]
for action in ["check-in", "check-out", "cancel", "no-show", "move", "extend"]:
    urlpatterns += [path(f"stays/<int:pk>/{action}/", v.StayActionView.as_view(), {"action": action})]
