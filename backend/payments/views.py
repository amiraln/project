"""Табель и оплаты: страницы раздела /payments/ и JSON-API для них (только администратор)."""
import calendar
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import admin_api, admin_required
from .models import DEFAULT_MONTHLY, ChangeLog, Child, ChildRecord, Guardian, PaymentInfo, guardian_match, sync_children

# Расчёт оплаты: отпуск (ОР) вычитается по дням, больничный (БР) — фиксированно, если дней больше порога
WORK_DAYS = 22
SICK_THRESHOLD = 8
SICK_DEDUCTION = 1000

MONTH_NAMES = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
               "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTH_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")

# Коды причин отсутствия, как в e-orda
ABSENCE_LABELS = {
    "ОР": "Отпуск родителя", "БР": "Болезнь ребёнка", "БП": "Без причины",
    "СО": "Оздоровление ребёнка", "ЛР": "Лечение ребёнка", "Р": "Ремонт",
    "СД": "Санитарный день", "ЧП": "Чрезвычайное происшествие", "К": "Карантин",
    "СЭ": "Санитарно-противоэпидемические мероприятия",
}
# Отметки, которые можно поставить вручную: присутствие, выходной, причина отсутствия или «очистить»
DAY_STATUSES = {"present", "weekend", "clear", *ABSENCE_LABELS}


# ---------- месяцы ----------

def is_month(value):
    return isinstance(value, str) and MONTH_RE.fullmatch(value) is not None


def shift_month(ym, delta):
    y, m = divmod(int(ym[:4]) * 12 + int(ym[5:7]) - 1 + delta, 12)
    return f"{y:04d}-{m + 1:02d}"


def month_label(ym):
    return f"{MONTH_NAMES[int(ym[5:7])]} {ym[:4]}" if is_month(ym) else ym


def days_in_month(ym):
    return calendar.monthrange(int(ym[:4]), int(ym[5:7]))[1] if is_month(ym) else 31


def available_months():
    """Месяцы, за которые загружен табель, — новые первыми."""
    return list(ChildRecord.objects.exclude(month="").order_by("-month").values_list("month", flat=True).distinct())


def resolve_month(request):
    """Месяц из ?month=, иначе последний загруженный, иначе текущий."""
    months = available_months()
    month = request.GET.get("month")
    if not is_month(month):
        month = months[0] if months else date.today().strftime("%Y-%m")
    return month, months


# ---------- отметки дней ----------

def parse_day(raw):
    """Отметка дня в формате e-orda (JSON-строка) → (тип, код причины).

    Типы: present, absent_reason, weekend, absent, empty, unknown.
    """
    if not raw:
        return "empty", ""
    try:
        mark = json.loads(raw)
    except (TypeError, ValueError):
        return "unknown", ""
    if not isinstance(mark, dict):
        return "unknown", ""
    if "cId" in mark:
        code = mark.get("ct") or ""
        return ("absent_reason", code) if mark.get("a") and code else ("present", "")
    color = mark.get("cl", "")
    if "255, 0, 0" in color:
        return "weekend", ""
    if "211, 211, 211" in color:
        return "absent", ""
    return "unknown", ""


def day_json(status):
    """Отметка для сохранения в табеле (в формате e-orda); None — день без отметки."""
    if status == "present":
        return json.dumps({"cId": 1, "a": False, "ch": True})
    if status == "weekend":
        return json.dumps({"cl": "RGBA(255, 0, 0, 0.4)"})
    if status in ABSENCE_LABELS:
        return json.dumps({"cId": 1, "a": True, "ct": status, "cl": "RGBA(255, 165, 0, 0.9)"})
    return None


def day_label(kind, code):
    """Отметка дня словами — для журнала изменений."""
    if kind == "present":
        return "Присутствовал"
    if kind == "weekend":
        return "Выходной"
    if kind == "absent_reason":
        return f"{code} ({ABSENCE_LABELS.get(code, code)})"
    return "Нет отметки"


# ---------- расчёт ----------

def calc_due(monthly, vacation_days, sick_days):
    due = monthly - monthly / WORK_DAYS * vacation_days
    if sick_days > SICK_THRESHOLD:
        due -= SICK_DEDUCTION * sick_days
    return round(due, 2)


def summarize(rec):
    """Строка табеля: отметки по дням, счётчики и расчёт оплаты за месяц."""
    marks = json.loads(rec.days_json or "{}")
    days = []
    for num in range(1, days_in_month(rec.month) + 1):
        kind, code = parse_day(marks.get(f"d{num}"))
        days.append({"num": num, "type": kind, "ct": code, "label": ABSENCE_LABELS.get(code, code)})
    reasons = Counter(d["ct"] for d in days if d["type"] == "absent_reason")
    vacation, sick = reasons["ОР"], reasons["БР"]
    pay = getattr(rec, "payment", None)
    monthly = pay.monthly_payment if pay else DEFAULT_MONTHLY
    paid = pay.last_payment if pay else 0
    total = calc_due(monthly, vacation, sick)
    return {
        "pId": rec.p_id, "fio": rec.fio, "iin": rec.iin, "age": rec.age,
        "group": rec.group_name, "group_id": rec.group_id, "month": rec.month,
        "days": days, "present": sum(d["type"] == "present" for d in days),
        "vacation_days": vacation, "sick_days": sick,
        "monthly": monthly, "last_payment": paid, "total": total, "overpay": round(paid - total, 2),
    }


def absences(days):
    """Дни отсутствия по причинам: [{code, label, days: [...]}, ...]."""
    by_code = defaultdict(list)
    for d in days:
        if d["type"] == "absent_reason":
            by_code[d["ct"]].append(d["num"])
    return [{"code": code, "label": ABSENCE_LABELS.get(code, code), "days": nums} for code, nums in by_code.items()]


def child_totals(rec):
    """Итоги месяца для карточки ребёнка — отдаются после каждого изменения."""
    s = summarize(rec)
    totals = {key: s[key] for key in ("present", "vacation_days", "sick_days", "total", "overpay")}
    return {**totals, "absences": absences(s["days"])}


def balances():
    """Внесено и начислено по каждому ребёнку за все месяцы; самый большой долг — первым."""
    children = {}
    for rec in ChildRecord.objects.select_related("payment").order_by("month"):
        s = summarize(rec)
        child = children.setdefault(rec.p_id, {"pId": rec.p_id, "months": []})
        child.update(fio=rec.fio, iin=rec.iin, group=rec.group_name, month=rec.month)  # данные последнего месяца
        child["months"].append({"label": month_label(rec.month), "paid": s["last_payment"],
                                "due": s["total"], "diff": s["overpay"]})
    for child in children.values():
        child["paid"] = round(sum(m["paid"] for m in child["months"]), 2)
        child["due"] = round(sum(m["due"] for m in child["months"]), 2)
        child["net"] = round(child["paid"] - child["due"], 2)  # > 0 переплата, < 0 долг
        child["owed"] = max(0, -child["net"])
    return sorted(children.values(), key=lambda c: (c["net"], c["fio"]))


# ---------- страницы ----------

@admin_required
def index(request):
    month, months = resolve_month(request)
    records = list(ChildRecord.objects.filter(month=month).select_related("payment"))

    counts = Counter((r.group_id, r.group_name) for r in records)
    groups = sorted(({"gid": str(gid), "name": name, "count": n} for (gid, name), n in counts.items()),
                    key=lambda g: g["name"])
    group = next((g for g in groups if g["gid"] == request.GET.get("group")), None)
    if group:
        records = [r for r in records if str(r.group_id) == group["gid"]]

    def url(ym):
        return "?" + urlencode({"month": ym, **({"group": group["gid"]} if group else {})})

    if month not in months:
        months = sorted([month, *months], reverse=True)
    return render(request, "payments/index.html", {
        "records": [summarize(r) for r in records],
        "groups": groups,
        "group": group,
        "total_all": sum(g["count"] for g in groups),
        "month": month,
        "month_label": month_label(month),
        "months": [{"value": m, "label": month_label(m), "url": url(m)} for m in months],
        "prev_url": url(shift_month(month, -1)),
        "next_url": url(shift_month(month, 1)),
        "day_nums": range(1, days_in_month(month) + 1),
    })


@admin_required
def child_detail(request, p_id):
    month = resolve_month(request)[0]
    rec = ChildRecord.objects.filter(p_id=p_id, month=month).select_related("payment").first()
    context = {"month": month, "month_label": month_label(month)}
    if rec:
        child = summarize(rec)
        context.update({
            "child": child,
            "pupil": Child.objects.filter(p_id=rec.p_id).first(),  # адрес и договор из e-orda
            "absences": absences(child["days"]),
            "blank_days": range(date(int(month[:4]), int(month[5:7]), 1).weekday()),  # пустые клетки до 1-го числа
            "guardians": Guardian.objects.filter(guardian_match(rec.p_id, rec.iin)),
            "absence_labels": ABSENCE_LABELS,
        })
    return render(request, "payments/child.html", context)


@admin_required
def changelog(request):
    month = request.GET.get("month", "")
    logs = ChangeLog.objects.all()
    if is_month(month):
        logs = logs.filter(month=month)
    else:
        month = ""
    shown = list(logs[:500])
    for log in shown:
        log.month_label = month_label(log.month)
    return render(request, "payments/changelog.html", {
        "logs": shown,
        "total": logs.count(),
        "month": month,
        "months": [{"value": m, "label": month_label(m)} for m in available_months()],
    })


@admin_required
def debts(request):
    rows = balances()
    return render(request, "payments/debts.html", {
        "rows": rows,
        "total_owed": sum(r["owed"] for r in rows),
        "total_overpaid": sum(r["net"] for r in rows if r["net"] > 0),
    })


@admin_required
def parents_page(request):
    by_pid, by_iin = defaultdict(list), defaultdict(list)
    for g in Guardian.objects.all():
        by_pid[g.child_pid].append(g)
        if g.child_iin:
            by_iin[g.child_iin].append(g)
    rows = balances()
    for row in rows:
        found = by_pid[row["pId"]] + (by_iin[row["iin"]] if row["iin"] else [])
        row["guardians"] = list({g.pk: g for g in found}.values())
    return render(request, "payments/parents.html", {
        "rows": rows,
        "with_contacts": sum(1 for r in rows if r["guardians"]),
        "total_guardians": sum(len(r["guardians"]) for r in rows),
    })


@admin_required
def print_group(request, gid):
    month = resolve_month(request)[0]
    records = [summarize(r) for r in ChildRecord.objects.filter(month=month, group_id=gid).select_related("payment")]
    return render(request, "payments/print.html", {
        "records": records,
        "group_name": records[0]["group"] if records else "Группа",
        "month": month,
        "month_label": month_label(month),
        "day_nums": range(1, days_in_month(month) + 1),
        "absence_labels": ABSENCE_LABELS,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect_to_login(reverse("payments:index"))


# ---------- JSON-API страниц раздела ----------

def load_json(request):
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def find_record(data):
    """Строка табеля по pId и month из запроса или None."""
    try:
        p_id = int(data.get("pId"))
    except (TypeError, ValueError):
        return None
    month = data.get("month")
    if not is_month(month):
        return None
    return ChildRecord.objects.filter(p_id=p_id, month=month).select_related("payment").first()


def parse_amount(value):
    """Сумма из поля ввода («51 000», «51000,5») или None."""
    try:
        amount = float(re.sub(r"\s", "", str(value)).replace(",", "."))
    except ValueError:
        return None
    return amount if math.isfinite(amount) else None


@require_POST
@admin_api
def save_payment(request):
    data = load_json(request)
    rec = find_record(data)
    if rec is None:
        return error("Ребёнок не найден в табеле за этот месяц", 404)
    pay, _ = PaymentInfo.objects.get_or_create(child=rec)
    if "last_payment" in data:
        paid = parse_amount(data["last_payment"] or 0)
        if paid is None or paid < 0:
            return error("Оплата — неотрицательное число")
        pay.last_payment = paid
    if "monthly" in data:
        monthly = parse_amount(data["monthly"] or DEFAULT_MONTHLY)
        if monthly is None or monthly <= 0:
            return error("Ежемесячная оплата — положительное число")
        pay.monthly_payment = monthly
    pay.save()
    rec.payment = pay
    return JsonResponse({"ok": True, "totals": child_totals(rec)})


@require_POST
@admin_api
def save_absence(request):
    data = load_json(request)
    rec = find_record(data)
    if rec is None:
        return error("Ребёнок не найден в табеле за этот месяц", 404)
    try:
        day = int(data.get("day"))
    except (TypeError, ValueError):
        day = 0
    if not 1 <= day <= days_in_month(rec.month):
        return error("Нет такого дня в месяце")
    status = data.get("status")
    if status not in DAY_STATUSES:
        return error("Неизвестная отметка")

    marks = json.loads(rec.days_json or "{}")
    key = f"d{day}"
    old = day_label(*parse_day(marks.get(key)))
    marks[key] = day_json(status)
    rec.days_json = json.dumps(marks, ensure_ascii=False)
    rec.save(update_fields=["days_json", "updated_at"])

    kind, code = parse_day(marks[key])
    new = day_label(kind, code)
    if old != new:  # в журнал — только реальные изменения
        ChangeLog.objects.create(
            user=request.user, username=request.user.username,
            month=rec.month, p_id=rec.p_id, child_fio=rec.fio, group_name=rec.group_name,
            day_num=day, old_status=old, new_status=new,
        )
    return JsonResponse({"ok": True, "type": kind, "ct": code, "label": ABSENCE_LABELS.get(code, ""),
                         "totals": child_totals(rec)})


@require_POST
@admin_api
def clear_data(request):
    month = load_json(request).get("month")
    if not is_month(month):
        return error("Не указан месяц")
    ChildRecord.objects.filter(month=month).delete()
    return JsonResponse({"ok": True})


# ---------- закладки e-orda ----------

def keep_opener(view):
    """Окно открывает страница e-orda; с COOP same-origin (по умолчанию в Django) связь с ней теряется."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response["Cross-Origin-Opener-Policy"] = "unsafe-none"
        return response

    return wrapper


@keep_opener
@admin_required
def eorda_bridge(request):
    months = available_months()
    return render(request, "payments/eorda_bridge.html", {
        "eorda_origins": settings.PAYMENTS_EORDA_ORIGINS,
        # С чего закладке «Родители» начать: дети и группы из табеля (id совпадают с id в e-orda)
        "timesheet": {
            "children": list(Child.objects.filter(is_active=True).values_list("p_id", flat=True)),
            "groups": sorted(set(ChildRecord.objects.filter(month=months[0]).values_list("group_id", flat=True)))
            if months else [],
        },
    })


def text(value, limit):
    return str(value or "")[:limit]


@require_POST
@admin_api
def receive_data(request):
    """Табель из e-orda: строки детей за месяц."""
    data = load_json(request)
    month, rows = data.get("month"), data.get("result")
    if not is_month(month) or not isinstance(rows, list) or not rows:
        return error("Нет данных табеля")
    if not all(isinstance(r, dict) and r.get("pId") is not None and r.get("gId") is not None for r in rows):
        return error("Табель в неожиданном формате — обновите закладку")
    with transaction.atomic():
        for r in rows:
            ChildRecord.objects.update_or_create(
                p_id=r["pId"], month=month,
                defaults={
                    "iin": text(r.get("i"), 20), "fio": text(r.get("fio"), 200), "age": text(r.get("pa"), 40),
                    "group_id": r["gId"], "group_name": text(r.get("gn"), 120), "tmsh_id": r.get("tmshId"),
                    "days_json": json.dumps({f"d{i}": r.get(f"d{i}") for i in range(1, 32)}, ensure_ascii=False),
                },
            )
        sync_children({r["pId"] for r in rows})
    return JsonResponse({"ok": True, "count": len(rows), "month": month})


@require_POST
@admin_api
def guardians_import(request):
    """Контакты родителей из e-orda: заменяют прежние контакты этих детей.
    Заодно у воспитанников обновляются адрес и договор — если закладка их прислала."""
    pupils = [p for p in load_json(request).get("pupils") or [] if isinstance(p, dict) and p.get("p_id") is not None]
    saved = 0
    with transaction.atomic():
        for p in pupils:
            iin = text(p.get("iin"), 20)
            Guardian.objects.filter(guardian_match(p["p_id"], iin)).delete()
            saved += len(Guardian.objects.bulk_create([
                Guardian(child_pid=p["p_id"], child_iin=iin, child_fio=text(p.get("fio"), 200),
                         gender=guardian_gender(g.get("gender")),
                         fio=text(g.get("fio"), 200), iin=text(g.get("iin"), 20),
                         phone=text(g.get("phone"), 160), email=text(g.get("email"), 254))
                for g in p.get("guardians") or [] if isinstance(g, dict)
            ]))

            facts = {}
            if "address" in p:
                facts["address"] = text(p["address"], 255)
            if isinstance(p.get("contracts"), list):  # нет списка — договоры не открылись, прежние не трогаем
                facts["contract_number"], facts["contract_date"] = latest_contract(p["contracts"])
            if facts:
                Child.objects.filter(Q(p_id=p["p_id"]) | Q(iin=iin) if iin else Q(p_id=p["p_id"])).update(**facts)
    return JsonResponse({"ok": True, "guardians": saved})


def guardian_gender(value):
    """Gender в e-orda: 1 — отец, 2 — мать; остальное — неизвестно."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value in (Guardian.FATHER, Guardian.MOTHER) else None


def latest_contract(contracts):
    """Номер и дата подписания последнего договора; у ребёнка без договоров — ("", None)."""
    found = [(text(c.get("number"), 60), eorda_date(c.get("date"))) for c in contracts if isinstance(c, dict)]
    found = [c for c in found if c[0] or c[1]]
    return max(found, key=lambda c: c[1] or date.min) if found else ("", None)


def eorda_date(value):
    """Дата из e-orda: «/Date(1693526400000)/» или те же миллисекунды числом,
    «2023-09-01T10:20:30» (со смещением или без) или «01.09.2023»."""
    s = str(value or "").strip()
    try:
        if m := re.fullmatch(r"/Date\((-?\d+)[^)]*\)/|(\d{12,13})", s):
            return datetime.fromtimestamp(int(m[1] or m[2]) / 1000, timezone.get_default_timezone()).date()
        if m := re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?", s):
            day, time, tz = m.groups()
            if not tz:
                return date.fromisoformat(day)
            tz = "+00:00" if tz == "Z" else f"{tz[:3]}:{tz[-2:]}"
            return datetime.fromisoformat(f"{day}T{time}{tz}").astimezone(timezone.get_default_timezone()).date()
        if m := re.match(r"(\d{2})\.(\d{2})\.(\d{4})", s):
            return date(int(m[3]), int(m[2]), int(m[1]))
    except (ValueError, OverflowError, OSError):
        pass
    return None
