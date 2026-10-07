import datetime
import io
import re
from collections import defaultdict

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count
from django.forms import inlineformset_factory, modelform_factory
from django.http import FileResponse, Http404, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from payments.models import Child, Guardian

from . import word
from .journals import BY_SLUG, JOURNALS, SECTIONS
from .models import JournalPeriod
from .utils import cell, label, title_date

# Поля подписи: в новой записи заполняются именем сотрудника
SIGNATURE_FIELDS = {"responsible", "nurse", "medical_worker", "inspected_by"}
# Поля, которые в новой записи заполняются из e-orda, как только выбран ребёнок, — в любом журнале, где они есть
CHILD_FACT_FIELDS = ("mother", "father", "address", "admission_date")
# «Заполнить период»: не больше года записей за раз
MAX_PERIOD_DAYS = 366
# Журналы с детьми делятся по группам: фильтр ?group=, «-» — дети без группы; колонка группы — когда показаны все
NO_GROUP = "-"
GROUP_COLUMN = "group"


class PeriodForm(forms.Form):
    """Новая запись с теми же данными на каждый день: с даты записи по последний день включительно."""
    until = forms.DateField(label="Последний день", required=False,
                            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    skip_weekends = forms.BooleanField(label="Без субботы и воскресенья", required=False, initial=True)

    def days(self, start):
        """Дни, на которые заводятся записи (период не задан — только день записи); None — ошибка в периоде."""
        first = timezone.localtime(start).date() if isinstance(start, datetime.datetime) else start
        until = self.cleaned_data["until"] or first
        if until < first:
            self.add_error("until", "Последний день раньше даты записи.")
        elif (until - first).days >= MAX_PERIOD_DAYS:
            self.add_error("until", "Период — не больше года.")
        else:
            days = [first + datetime.timedelta(n) for n in range((until - first).days + 1)]
            if self.cleaned_data["until"] and self.cleaned_data["skip_weekends"]:
                days = [d for d in days if d.weekday() < 5]
            if days:
                return days
            self.add_error("skip_weekends", "В периоде только суббота и воскресенье.")
        return None


# ------------------------------------------------------------------ helpers
def _get_journal(request, slug, action):
    journal = BY_SLUG.get(slug)
    if journal is None:
        raise Http404
    if not request.user.has_perm(journal.perm_prefix % action):
        raise PermissionDenied
    return journal


def _children():
    """В списках выбора — только посещающие дети; записи выбывших остаются."""
    return Child.objects.filter(is_active=True)


def _group_label(name):
    return name or "Без группы"


def _by_group(children):
    """Дети по группам для списков выбора: [(группа, [дети])], группы по алфавиту, «Без группы» — в конце."""
    groups = defaultdict(list)
    for child in children:
        groups[child.group_name].append(child)
    return [(_group_label(name), groups[name]) for name in sorted(groups, key=lambda n: (n == "", n))]


def _formfield(db_field, **kwargs):
    if isinstance(db_field, models.DateTimeField):
        kwargs["widget"] = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
    elif isinstance(db_field, models.DateField):
        kwargs["widget"] = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    elif isinstance(db_field, models.TimeField):
        kwargs["widget"] = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    elif isinstance(db_field, models.TextField):
        kwargs["widget"] = forms.Textarea(attrs={"rows": 2})
    field = db_field.formfield(**kwargs)
    if db_field.name == "child" and isinstance(field, forms.ModelChoiceField):
        field.queryset = _children()
        empty = [("", field.empty_label)] if field.empty_label is not None else []
        field.choices = empty + [(group, [(c.pk, c.fio) for c in kids]) for group, kids in _by_group(field.queryset)]
    return field


def _child_facts(journal, children):
    """Данные детей из e-orda для полей журнала из CHILD_FACT_FIELDS: {id ребёнка: {поле: значение}}.
    Мать и отец — «ФИО, телефоны» первого родителя с таким полом, дата зачисления — дата подписания договора."""
    fields = [f for f in journal.model._meta.fields if f.name in CHILD_FACT_FIELDS]
    if not fields:
        return {}
    by_pid, by_iin = defaultdict(list), defaultdict(list)
    for g in Guardian.objects.exclude(gender=None).order_by("pk"):
        by_pid[g.child_pid].append(g)
        if g.child_iin:
            by_iin[g.child_iin].append(g)
    facts = {}
    for child in children:
        parents = {}
        for g in by_pid[child.p_id] + (by_iin[child.iin] if child.iin else []):
            parents.setdefault(g.gender, g.contact)
        values = {
            "mother": parents.get(Guardian.MOTHER, ""),
            "father": parents.get(Guardian.FATHER, ""),
            "address": child.address,
            "admission_date": child.contract_date.isoformat() if child.contract_date else "",
        }
        facts[child.pk] = {f.name: values[f.name][:f.max_length] for f in fields}
    return facts


def _repeatable(journal):
    """«Заполнить период» — в журналах с обязательной датой записи и без вложенных таблиц."""
    return (journal.date_field is not None and not journal.inlines
            and not journal.model._meta.get_field(journal.date_field).blank)


def _on_day(value, day):
    """Дата записи, перенесённая на другой день; у даты со временем время остаётся прежним."""
    if isinstance(value, datetime.datetime):
        return timezone.localtime(value).replace(year=day.year, month=day.month, day=day.day)
    return day


def _fillable(journal):
    """«Заполнить всех» — только в журналах, где на ребёнка заводится одна запись и кроме ребёнка обязательных
    полей нет (медкарта, паспорт здоровья). В журналах событий нужны дата, диагноз и т. п. — их вносят вручную."""
    if not journal.child_field:
        return False
    known = {journal.child_field, *SIGNATURE_FIELDS}
    return all(f.name in known for f in journal.model._meta.fields
               if f.editable and not f.primary_key and not f.blank and not f.has_default())


def _fill_plan(journal, user):
    """Что сделает «Заполнить всех»: новые записи для посещающих детей, у которых записи ещё нет,
    и пустые поля существующих записей, которые известны из e-orda. Неизвестное остаётся пустым,
    заполненное вручную не меняется. Возвращает (новые записи, [(запись, изменённые поля)])."""
    children = list(_children())
    facts = _child_facts(journal, children)
    fields = {f.name: f for f in journal.model._meta.fields}
    signature = {f: user.get_full_name() or user.get_username() for f in SIGNATURE_FIELDS if f in fields}
    child_id = f"{journal.child_field}_id"
    existing = defaultdict(list)
    for obj in journal.model._default_manager.filter(**{f"{child_id}__in": [c.pk for c in children]}):
        existing[getattr(obj, child_id)].append(obj)

    new, changed = [], []
    for child in children:
        values = {name: fields[name].to_python(v) for name, v in facts.get(child.pk, {}).items() if v}
        if child.pk not in existing:
            new.append(journal.model(**{journal.child_field: child}, created_by=user, **signature, **values))
        for obj in existing.get(child.pk, []):
            empty = [name for name in values if getattr(obj, name) in (None, "")]
            for name in empty:
                setattr(obj, name, values[name])
            if empty:
                changed.append((obj, empty))
    return new, changed


def _filtered_qs(journal, params):
    """Записи журнала по фильтрам страницы (?date_from, date_to, group, child)."""
    qs = journal.model._default_manager.all()
    if journal.child_field:
        qs = qs.select_related(journal.child_field)
    f = {key: params.get(key, "") for key in ("date_from", "date_to", "group", "child")}
    if journal.date_field:
        is_dt = isinstance(journal.model._meta.get_field(journal.date_field), models.DateTimeField)
        lookup = f"{journal.date_field}__date" if is_dt else journal.date_field
        if f["date_from"]:
            qs = qs.filter(**{f"{lookup}__gte": f["date_from"]})
        if f["date_to"]:
            qs = qs.filter(**{f"{lookup}__lte": f["date_to"]})
    if journal.child_field and f["group"]:
        qs = qs.filter(**{f"{journal.child_field}__group_name": "" if f["group"] == NO_GROUP else f["group"]})
    if journal.child_field and f["child"].isdigit():
        qs = qs.filter(**{f"{journal.child_field}_id": f["child"]})
    return qs, f


def _group_tabs(journal, params):
    """Вкладки групп над журналом с детьми: группы посещающих детей и детей с записями, у каждой — число записей."""
    counts = dict(journal.model._default_manager.order_by()
                  .values_list(f"{journal.child_field}__group_name").annotate(n=Count("pk")))
    names = set(counts) | set(_children().values_list("group_name", flat=True))
    query = params.copy()
    for key in ("group", "child", "page"):
        query.pop(key, None)
    tabs = [{"value": "", "label": "Все группы", "count": sum(counts.values())}]
    tabs += [{"value": name or NO_GROUP, "label": _group_label(name), "count": counts.get(name, 0)}
             for name in sorted(names, key=lambda n: (n == "", n))]
    for tab in tabs:
        tab_query = query.copy()
        if tab["value"]:
            tab_query["group"] = tab["value"]
        tab["query"] = tab_query.urlencode()
    return tabs


def _columns(journal, filters):
    """Колонки таблицы; в журнале с детьми, когда показаны все группы, после ребёнка — его группа."""
    columns = list(journal.columns)
    if journal.child_field and not filters["group"]:
        at = columns.index(journal.child_field) + 1 if journal.child_field in columns else 0
        columns.insert(at, GROUP_COLUMN)
    return columns


def _as_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _rows(journal, objects, columns):
    def value(obj, col):
        return getattr(obj, journal.child_field).group_name if col == GROUP_COLUMN else cell(obj, col)
    return [(obj, [value(obj, c) for c in columns]) for obj in objects]


def _headers(journal, columns):
    return ["Группа" if c == GROUP_COLUMN else label(journal.model, c) for c in columns]


def _org_context():
    return {"org_name": settings.MEDJOURNAL_ORG_NAME, "org_head": settings.MEDJOURNAL_ORG_HEAD}


# ------------------------------------------------------------------ views
@login_required
def index(request):
    sections = []
    for key, title in SECTIONS:
        items = [(j, j.model._default_manager.count()) for j in JOURNALS
                 if j.section == key and request.user.has_perm(j.perm_prefix % "view")]
        if items:
            sections.append((title, items))
    return render(request, "medjournal/index.html", {"sections": sections})


@login_required
def journal_list(request, slug):
    journal = _get_journal(request, slug, "view")
    qs, filters = _filtered_qs(journal, request.GET)
    columns = _columns(journal, filters)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    children = None
    if journal.child_field:
        children = _children()
        if filters["group"]:
            children = children.filter(group_name="" if filters["group"] == NO_GROUP else filters["group"])
        children = _by_group(children)
    return render(request, "medjournal/list.html", {
        "journal": journal, "headers": _headers(journal, columns), "rows": _rows(journal, page.object_list, columns),
        "page": page, "filters": filters, "query": query.urlencode(),
        "children": children, "group_tabs": _group_tabs(journal, request.GET) if journal.child_field else None,
        "can_add": request.user.has_perm(journal.perm_prefix % "add"),
        "can_change": request.user.has_perm(journal.perm_prefix % "change"),
        "can_fill_all": _fillable(journal) and request.user.has_perms(
            [journal.perm_prefix % "add", journal.perm_prefix % "change"]),
        "can_delete": request.user.has_perm(journal.perm_prefix % "delete"),
        "can_bulk": request.user.has_perm(journal.perm_prefix % "change")
        or request.user.has_perm(journal.perm_prefix % "delete"),
    })


@login_required
def journal_print(request, slug):
    journal = _get_journal(request, slug, "view")
    return render(request, "medjournal/print_list.html", {
        **_journal_sheet(journal, request.GET),
        "query": request.GET.urlencode(),
        "can_change": request.user.has_perm(journal.perm_prefix % "change"),
    })


@login_required
def journal_word(request, slug):
    """Журнал в Word — то же, что на печатной форме, с теми же фильтрами."""
    journal = _get_journal(request, slug, "view")
    sheet = _journal_sheet(journal, request.GET)
    name = f"{journal.number}. {journal.title}"
    if sheet["group"]:
        name += f" — {sheet['group']}"
    return _word_response(word.journal_document(sheet), f"{name} {sheet['printed_at']:%d.%m.%Y}")


def _journal_sheet(journal, params):
    """Всё, что попадает на печатную форму журнала (и в Word): шапка, графы и строки по фильтрам списка."""
    qs, filters = _filtered_qs(journal, params)
    columns = _columns(journal, filters)
    objects = qs.order_by(*([journal.date_field, "pk"] if journal.date_field else ["pk"]))
    period = JournalPeriod.objects.filter(journal=journal.slug).first() or JournalPeriod(journal=journal.slug)
    group = filters["group"]
    headers = [f"{h} *" if c == journal.footnote_column else h for c, h in zip(columns, _headers(journal, columns))]
    return {
        "journal": journal, "headers": headers, "rows": _rows(journal, objects, columns),
        "group": _group_label("" if group == NO_GROUP else group) if group else "",
        "filters": filters, "printed_at": timezone.localtime(), **_org_context(),
        "period": period, "started": title_date(period.started), "finished": title_date(period.finished),
        "shown_from": _as_date(filters["date_from"]), "shown_to": _as_date(filters["date_to"]),
    }


def _word_response(document, name):
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    filename = re.sub(r'[\\/:*?"<>|]+', "", name).strip()[:120] + ".docx"  # без знаков, запрещённых в именах файлов
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type=word.CONTENT_TYPE)


@login_required
@require_POST
def journal_period(request, slug):
    """Даты «Начат» и «Окончен» для печати журнала — запоминаются, чтобы не вводить их каждый раз."""
    _get_journal(request, slug, "change")
    period = JournalPeriod.objects.filter(journal=slug).first() or JournalPeriod(journal=slug)
    form = modelform_factory(JournalPeriod, fields=["started", "finished"])(request.POST, instance=period)
    if not form.is_valid():
        errors = [e for field_errors in form.errors.values() for e in field_errors]
        return JsonResponse({"ok": False, "error": " ".join(errors)}, status=400)
    form.save()
    return JsonResponse({"ok": True, "started": title_date(period.started), "finished": title_date(period.finished)})


@login_required
def record_edit(request, slug, pk=None):
    journal = _get_journal(request, slug, "change" if pk else "add")
    instance = get_object_or_404(journal.model, pk=pk) if pk else None
    Form = modelform_factory(journal.model, fields="__all__", formfield_callback=_formfield)

    initial, facts = {}, {}
    if instance is None:
        name = request.user.get_full_name() or request.user.get_username()
        initial = {f: name for f in SIGNATURE_FIELDS}
        if journal.child_field:
            facts = _child_facts(journal, _children())
            if request.GET.get("child", "").isdigit():
                initial[journal.child_field] = request.GET["child"]
                initial.update(facts.get(int(request.GET["child"]), {}))

    data = request.POST if request.method == "POST" else None
    form = Form(data, instance=instance, initial=initial)
    period = PeriodForm(data, prefix="period") if instance is None and _repeatable(journal) else None
    formsets = [
        (inl, inlineformset_factory(journal.model, inl.model, fields=inl.fields, extra=inl.extra,
                                    can_delete=True, formfield_callback=_formfield)(
            data, instance=instance, prefix=inl.model._meta.model_name))
        for inl in journal.inlines
    ]

    valid = data is not None and form.is_valid() and all(fs.is_valid() for _, fs in formsets)
    days = [None]  # None — дата записи как в форме
    if valid and period is not None:
        days = period.days(form.cleaned_data[journal.date_field]) if period.is_valid() else None
        valid = days is not None
    if valid:
        with transaction.atomic():
            obj = form.save(commit=False)
            if instance is None:
                obj.created_by = request.user
            entered = getattr(obj, journal.date_field) if journal.date_field else None
            for n, day in enumerate(days):
                if day is not None:
                    setattr(obj, journal.date_field, _on_day(entered, day))
                if n:  # те же данные — отдельной записью на каждый следующий день периода
                    obj.pk, obj._state.adding = None, True
                obj.save()
            for _, fs in formsets:
                fs.instance = obj
                fs.save()
        messages.success(request, "Запись сохранена." if len(days) == 1 else
                         f"Создано записей: {len(days)}, с {days[0]:%d.%m.%Y} по {days[-1]:%d.%m.%Y}.")
        if "save_add" in request.POST:
            return redirect("medjournal:add", slug=slug)
        return redirect("medjournal:list", slug=slug)

    autofill = None
    if facts:
        names = [f for f in CHILD_FACT_FIELDS if f in form.fields]
        autofill = {"child": journal.child_field, "fields": names, "facts": facts,
                    "labels": [str(form.fields[f].label) for f in names]}
    return render(request, "medjournal/form.html", {
        "journal": journal, "form": form, "formsets": formsets, "object": instance, "autofill": autofill,
        "period": period,
    })


@login_required
def fill_all(request, slug):
    """«Заполнить всех»: запись на каждого посещающего ребёнка с данными из e-orda; сначала — подтверждение."""
    journal = _get_journal(request, slug, "add")
    if not _fillable(journal):
        raise Http404
    if not request.user.has_perm(journal.perm_prefix % "change"):
        raise PermissionDenied
    new, changed = _fill_plan(journal, request.user)
    if request.method == "POST":
        with transaction.atomic():
            for obj in new:
                obj.save()
            for obj, names in changed:
                obj.save(update_fields=[*names, "updated_at"])
        messages.success(request, f"Добавлено записей: {len(new)}, дополнено: {len(changed)}. "
                                  "Поля, которых нет в e-orda, остались пустыми — их заполняют вручную.")
        return redirect("medjournal:list", slug=slug)
    names = {f.name for f in journal.model._meta.fields}
    filled = [journal.child_field, *(f for f in CHILD_FACT_FIELDS if f in names)]
    return render(request, "medjournal/confirm_fill.html", {
        "journal": journal, "new": len(new), "changed": len(changed),
        "filled": [label(journal.model, f) for f in filled],
    })


def _selected(journal, post):
    """Отмеченные записи: id из формы (списком или через запятую) или все записи по фильтру списка."""
    if post.get("all") == "1":
        return _filtered_qs(journal, QueryDict(post.get("query", "")))[0]
    ids = [int(x) for value in post.getlist("ids") for x in value.split(",") if x.strip().isdigit()]
    return journal.model._default_manager.filter(pk__in=ids)


def _bulk_form(journal, data=None, only=None):
    """Поля, которые можно поменять сразу во многих записях, — все, кроме ребёнка."""
    form = forms.Form(data, use_required_attribute=False)  # поля других колонок скрыты и не заполняются
    form.fields = {f.name: _formfield(f) for f in journal.model._meta.fields
                   if f.editable and not f.primary_key and f.name != journal.child_field and only in (None, f.name)}
    return form


@login_required
@require_POST
def bulk(request, slug):
    """Отмеченные записи журнала: удалить или поменять одно поле во всех. Сначала — страница подтверждения."""
    action = request.POST.get("action")
    if action not in ("delete", "edit"):
        raise Http404
    journal = _get_journal(request, slug, "delete" if action == "delete" else "change")
    query = request.POST.get("query", "")
    back = reverse("medjournal:list", args=[slug]) + (f"?{query}" if query else "")
    objects = list(_selected(journal, request.POST))
    if not objects:
        messages.error(request, "Не отмечено ни одной записи.")
        return redirect(back)
    confirmed = "confirm" in request.POST
    context = {"journal": journal, "action": action, "count": len(objects), "sample": objects[:10],
               "more": max(0, len(objects) - 10), "ids": ",".join(str(o.pk) for o in objects),
               "query": query, "back": back}

    if action == "delete":
        if confirmed:
            try:
                with transaction.atomic():
                    journal.model._default_manager.filter(pk__in=[o.pk for o in objects]).delete()
            except models.ProtectedError:
                messages.error(request, "Ничего не удалено: на некоторые записи ссылаются другие журналы.")
            else:
                messages.success(request, f"Удалено записей: {len(objects)}.")
            return redirect(back)
        return render(request, "medjournal/bulk.html", context)

    name = request.POST.get("field", "")
    form = _bulk_form(journal, request.POST if confirmed else None)
    value_errors, record_errors = None, []
    if confirmed and name in form.fields:
        value_form = _bulk_form(journal, request.POST, only=name)
        if value_form.is_valid():
            value = value_form.cleaned_data[name]
            others = [f.name for f in journal.model._meta.fields if f.name != name]
            for obj in objects:
                setattr(obj, name, value)
                try:  # правила журнала: например, «допущен к работе» только без нарушений
                    obj.full_clean(exclude=others, validate_unique=False, validate_constraints=False)
                except ValidationError as e:
                    record_errors.append((obj, " ".join(e.messages)))
            if not record_errors:
                with transaction.atomic():
                    for obj in objects:
                        obj.save()
                shown = cell(objects[0], name) or "пусто"
                messages.success(request, f"Изменено записей: {len(objects)}. «{form.fields[name].label}» — {shown}.")
                return redirect(back)
        else:
            value_errors = value_form.errors[name]
    return render(request, "medjournal/bulk.html", {
        **context, "form": form, "field": name, "value_errors": value_errors,
        "record_errors": record_errors[:10], "record_errors_count": len(record_errors),
    })


@login_required
def record_delete(request, slug, pk):
    journal = _get_journal(request, slug, "delete")
    obj = get_object_or_404(journal.model, pk=pk)
    if request.method == "POST":
        try:
            obj.delete()
        except models.ProtectedError:
            messages.error(request, "Нельзя удалить: на запись ссылаются другие журналы.")
        else:
            messages.success(request, "Запись удалена.")
        return redirect("medjournal:list", slug=slug)
    return render(request, "medjournal/confirm_delete.html", {"journal": journal, "object": obj})


@login_required
def record_print(request, slug, pk):
    """Печать одной записи целиком (медкарта, паспорт здоровья, ведомость, курс химиопрофилактики)."""
    journal = _get_journal(request, slug, "view")
    obj = get_object_or_404(journal.model, pk=pk)
    return render(request, "medjournal/print_detail.html", _record_sheet(journal, obj))


@login_required
def record_word(request, slug, pk):
    """Одна запись целиком в Word."""
    journal = _get_journal(request, slug, "view")
    sheet = _record_sheet(journal, get_object_or_404(journal.model, pk=pk))
    return _word_response(word.record_document(sheet), f"{sheet['record_title']} — {sheet['object']}")


def _record_sheet(journal, obj):
    """Всё, что попадает на печатную форму одной записи (и в Word): поля и вложенные таблицы."""
    fields = [(str(f.verbose_name), cell(obj, f.name)) for f in journal.model._meta.fields
              if f.editable and not f.primary_key]
    inlines = []
    for inl in journal.inlines:
        fk = next(f.name for f in inl.model._meta.fields if f.related_model is journal.model)
        cols = inl.fields + inl.computed
        inlines.append({
            "title": inl.title or inl.model._meta.verbose_name_plural,
            "headers": [label(inl.model, c) for c in cols],
            "rows": [[cell(i, c) for c in cols] for i in inl.model._default_manager.filter(**{fk: obj})],
        })
    return {
        "journal": journal, "object": obj, "fields": fields, "inlines": inlines,
        "record_title": str(journal.model._meta.verbose_name),
        "printed_at": timezone.localtime(), **_org_context(),
    }
