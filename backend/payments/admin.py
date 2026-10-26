"""Админка раздела оплат. Прав на эти модели нет ни у одной группы — их видят только суперпользователи."""
from django.contrib import admin

from .models import ChangeLog, Child, ChildRecord, Guardian, PaymentImport, PaymentInfo


class ReadOnlyAdmin(admin.ModelAdmin):
    """Записи появляются автоматически — в админке их только смотрят."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ("fio", "group_name", "iin", "contract_number", "contract_date", "last_month", "is_active", "large_family")
    list_editable = ("is_active", "large_family")
    list_filter = ("is_active", "large_family", "group_name")
    search_fields = ("fio", "iin", "contract_number", "address")
    readonly_fields = ("p_id", "last_month")

    def has_add_permission(self, request):
        return False  # воспитанники появляются из табеля


@admin.register(ChildRecord)
class ChildRecordAdmin(admin.ModelAdmin):
    list_display = ("fio", "iin", "group_name", "month", "updated_at")
    list_filter = ("month", "group_name")
    search_fields = ("fio", "iin")


@admin.register(PaymentInfo)
class PaymentInfoAdmin(admin.ModelAdmin):
    list_display = ("child", "last_payment", "method", "monthly")
    list_filter = ("method",)
    search_fields = ("child__fio", "child__iin")
    list_select_related = ("child",)

    @admin.display(description="Ежемесячная оплата", ordering="monthly_payment")
    def monthly(self, obj):
        return "по умолчанию" if obj.monthly_payment is None else obj.monthly_payment


@admin.register(ChangeLog)
class ChangeLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "username", "child_fio", "group_name", "month", "day_num", "old_status", "new_status")
    list_filter = ("month", "username", "group_name")
    search_fields = ("child_fio", "username")
    date_hierarchy = "created_at"


@admin.register(PaymentImport)
class PaymentImportAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "receipt_no", "iin", "payer_fio", "amount", "month", "child")
    list_filter = ("month",)
    search_fields = ("receipt_no", "iin", "payer_fio")
    list_select_related = ("child",)


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ("child_fio", "fio", "gender", "phone", "email", "iin", "updated_at")
    list_filter = ("gender",)
    search_fields = ("child_fio", "child_iin", "fio", "phone", "email", "iin")
    readonly_fields = ("updated_at",)
