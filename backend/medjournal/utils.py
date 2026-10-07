import datetime
from decimal import Decimal

from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone

EXTRA_LABELS = {
    "days": "Дней болезни",
    "bmi": "ИМТ",
    "actual_g": "Факт на 1 реб., г",
    "percent": "Выполнение, %",
}


MONTHS_GENITIVE = ["", "января", "февраля", "марта", "апреля", "мая", "июня",
                   "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def title_date(d):
    """Дата для титула журнала: «01» сентября 2025 г.; нет даты — пустые строки, чтобы вписать от руки."""
    if not d:
        return "«___» __________ 20__ г."
    return f"«{d:%d}» {MONTHS_GENITIVE[d.month]} {d.year} г."


def label(model, name):
    try:
        return str(model._meta.get_field(name).verbose_name)
    except FieldDoesNotExist:
        attr = getattr(model, name, None)
        return str(getattr(attr, "short_description", None) or EXTRA_LABELS.get(name, name))


def fmt(val):
    if val is None or val == "":
        return ""
    if isinstance(val, bool):
        return "да" if val else "нет"
    if isinstance(val, datetime.datetime):
        if timezone.is_aware(val):
            val = timezone.localtime(val)
        return val.strftime("%d.%m.%Y %H:%M")
    if isinstance(val, datetime.date):
        return val.strftime("%d.%m.%Y")
    if isinstance(val, datetime.time):
        return val.strftime("%H:%M")
    if isinstance(val, Decimal):
        s = format(val.normalize(), "f")
        return s.replace(".", ",")
    return str(val)


def cell(obj, name):
    try:
        f = obj._meta.get_field(name)
    except FieldDoesNotExist:
        f = None
    if f is not None and f.choices:
        return fmt(getattr(obj, f"get_{name}_display")())
    val = getattr(obj, name, None)
    if callable(val):
        val = val()
    return fmt(val)
