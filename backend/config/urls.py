from django.urls import include, path

from hotel.admin import backend_admin

urlpatterns = [
    path("admin/", backend_admin.urls),
    path("api/v1/", include("hotel.api.urls")),
]
