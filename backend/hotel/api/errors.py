from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework.exceptions import NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    if isinstance(exc, NotAuthenticated):
        return Response({"detail": "Autenticazione richiesta.", "code": "not_authenticated"}, status=401)
    if isinstance(exc, ObjectDoesNotExist):
        return Response({"detail": "Risorsa non trovata."}, status=404)
    if isinstance(exc, IntegrityError):
        return Response(
            {"detail": "Operazione in conflitto con dati esistenti.", "code": "conflict"}, status=409
        )
    return drf_exception_handler(exc, context)
