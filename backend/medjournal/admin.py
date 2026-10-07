from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist

from .journals import JOURNALS
from .utils import cell, label


def _column(model, col):
    """Колонка списка в админке: поле как есть, остальное — через общий форматтер."""
    try:
        model._meta.get_field(col)
        return col, None
    except FieldDoesNotExist:
        fn = admin.display(description=label(model, col))(lambda self, obj, c=col: cell(obj, c))
        return f"col_{col}", fn


def _make_admin(journal):
    attrs = {"list_per_page": 50, "list_display": []}
    for col in journal.columns[:8]:
        name, fn = _column(journal.model, col)
        attrs["list_display"].append(name)
        if fn:
            attrs[name] = fn
    attrs["inlines"] = [
        type(f"{inl.model.__name__}Inline", (admin.TabularInline,),
             {"model": inl.model, "fields": inl.fields, "extra": 1})
        for inl in journal.inlines
    ]
    if journal.date_field:
        attrs["date_hierarchy"] = journal.date_field
    if journal.child_field:
        attrs["list_select_related"] = [journal.child_field]
    return type(f"{journal.model.__name__}Admin", (admin.ModelAdmin,), attrs)


for _j in JOURNALS:
    admin.site.register(_j.model, _make_admin(_j))
