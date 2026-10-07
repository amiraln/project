"""Доступ к разделу оплат: только администратор."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import render


def is_payments_admin(user):
    """Раздел оплат видит только администратор: активный сотрудник-суперпользователь."""
    return bool(user and user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)


def admin_required(view):
    """Страница раздела: гостя — на вход сотрудников, остальным — 403."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_payments_admin(request.user):
            return render(request, "payments/forbidden.html", status=403)
        return view(request, *args, **kwargs)

    return wrapper


def admin_api(view):
    """JSON-эндпоинт для страниц раздела: без редиректов, сразу 403."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_payments_admin(request.user):
            return JsonResponse({"ok": False, "error": "Нет доступа"}, status=403)
        return view(request, *args, **kwargs)

    return wrapper
