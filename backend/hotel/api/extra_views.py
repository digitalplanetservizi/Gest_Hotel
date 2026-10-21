from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from ..extra_statements import render_extra_statement
from ..models import Charge, Group, HotelSettings, Stay


class ExtraStatementView(APIView):
    """Authenticated, read-only exports. The hotel timezone defines each day."""

    def get(self, request, pk, scope="stay"):
        hotel = HotelSettings.objects.get_or_create(pk=1)[0]
        charges = (
            Charge.objects.filter(kind="extra")
            .select_related("stay__room")
            .prefetch_related("stay__segments__room")
        )
        if scope == "group":
            group = get_object_or_404(Group, pk=pk)
            charges = charges.filter(stay__group=group)
            heading = f"Gruppo: {group.name}"
            subtitle = f"Referente: {group.reference_name} - Conto gruppo #{group.pk}"
            filename = f"extra-gruppo-{pk}.pdf"
        else:
            stay = get_object_or_404(Stay.objects.select_related("room"), pk=pk)
            charges = charges.filter(stay=stay)
            heading = f"Camera {stay.room.number} - {stay.guest_name}"
            subtitle = f"Soggiorno #{stay.pk}"
            filename = f"extra-soggiorno-{pk}.pdf"
        content = render_extra_statement(hotel=hotel, heading=heading, subtitle=subtitle, charges=charges)
        response = HttpResponse(content, content_type="application/pdf")
        # Numeric IDs keep the header safe even for arbitrary room/group names.
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response
