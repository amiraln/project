import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from payments.access import is_payments_admin

logger = logging.getLogger("accounts")


def user_payload(user):
    return {
        "authenticated": True,
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "is_superuser": user.is_superuser,
        "admin_url": "/" + settings.ADMIN_URL,
        "can_view_appeals": user.has_perm("content.view_appeal"),
        "can_access_payments": is_payments_admin(user),
        "can_access_medjournal": user.has_module_perms("medjournal"),
    }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Ставит cookie csrftoken — React вызывает перед первым POST."""

    def get(self, request):
        return Response({"ok": True})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(request, **ser.validated_data)
        # Одинаковый ответ для «нет пользователя», «неверный пароль» и «не сотрудник»
        if user is None or not user.is_staff:
            logger.warning("Неудачный вход: %s", ser.validated_data["username"])
            return Response({"detail": "invalid_credentials"}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)  # новая сессия + новый CSRF-токен
        logger.info("Вход: %s", user.username)
        return Response(user_payload(user))


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        user = request.user
        if user.is_authenticated and user.is_staff:
            return Response(user_payload(user))
        return Response({"authenticated": False})
