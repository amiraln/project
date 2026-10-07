"""Раздел оплат: /payments/… (только администратор)."""
from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.index, name="index"),
    path("child/<int:p_id>/", views.child_detail, name="child_detail"),
    path("changelog/", views.changelog, name="changelog"),
    path("debts/", views.debts, name="debts"),
    path("parents/", views.parents_page, name="parents"),
    path("print/<int:gid>/", views.print_group, name="print_group"),
    path("logout/", views.logout_view, name="logout"),
    # для страниц раздела
    path("api/payment/", views.save_payment, name="save_payment"),
    path("api/absence/", views.save_absence, name="save_absence"),
    path("api/clear/", views.clear_data, name="clear_data"),
    # закладки на e-orda: окно-приёмник и куда оно сохраняет данные
    path("eorda/", views.eorda_bridge, name="eorda_bridge"),
    path("api/receive/", views.receive_data, name="receive_data"),
    path("api/guardians/", views.guardians_import, name="guardians_import"),
]
