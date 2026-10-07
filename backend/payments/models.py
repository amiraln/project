"""Табель посещаемости и оплаты (перенесено из отдельной системы timesheet_project)."""
import re
from collections import defaultdict

from django.conf import settings
from django.db import models
from django.db.models import Q

# Ежемесячная оплата по умолчанию, ₸
DEFAULT_MONTHLY = 60000
LARGE_FAMILY_MONTHLY = 51000  # многодетная семья
OLD_DEFAULT_MONTHLY = 51000  # по умолчанию до появления многодетных семей — так считаны прошлые месяцы


def default_monthly(large_family):
    return LARGE_FAMILY_MONTHLY if large_family else DEFAULT_MONTHLY


class ChildRecord(models.Model):
    """Строка табеля ребёнка за конкретный месяц."""

    month = models.CharField(max_length=7, db_index=True, default="")  # 'YYYY-MM'
    p_id = models.BigIntegerField(db_index=True)
    iin = models.CharField(max_length=20, blank=True)
    fio = models.CharField(max_length=200)
    age = models.CharField(max_length=40, blank=True)
    group_id = models.BigIntegerField(db_index=True)
    group_name = models.CharField(max_length=120, blank=True)
    tmsh_id = models.BigIntegerField(null=True, blank=True)
    days_json = models.TextField(default="{}")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["group_name", "fio"]
        unique_together = [("month", "p_id")]
        verbose_name = "Ребёнок в табеле"
        verbose_name_plural = "Табель: дети по месяцам"

    def __str__(self):
        return f"{self.fio} ({self.group_name}, {self.month})"


class Child(models.Model):
    """Воспитанник: одна запись на ребёнка (в табеле — строка на каждый месяц).
    Заполняется из табеля; на него ссылаются журналы медицинской документации."""

    p_id = models.BigIntegerField("ID в табеле", unique=True)
    iin = models.CharField("ИИН", max_length=20, blank=True)
    fio = models.CharField("ФИО", max_length=200)
    group_name = models.CharField("Группа", max_length=120, blank=True)
    last_month = models.CharField("Последний месяц в табеле", max_length=7, blank=True)
    is_active = models.BooleanField(
        "Посещает детский сад", default=True,
        help_text="У выбывших снимите галочку: в журналах их не будет в списке детей, записи останутся.",
    )
    # Из e-orda, закладкой «Родители»: адрес — из карточки ребёнка, договор — из его списка договоров
    address = models.CharField("Домашний адрес", max_length=255, blank=True)
    contract_number = models.CharField("Номер договора", max_length=60, blank=True)
    contract_date = models.DateField("Дата подписания договора", null=True, blank=True,
                                     help_text="Она же дата зачисления в медицинских журналах.")
    large_family = models.BooleanField(
        "Многодетная семья", null=True, blank=True,
        choices=[(None, "Определять по родителям"), (True, "Да"), (False, "Нет")],
        help_text="По родителям — многодетная, если в табеле за месяц есть ещё ребёнок того же родителя "
                  "(по ИИН родителя из e-orda). «Да» — например, если остальные дети в сад не ходят.",
    )

    class Meta:
        ordering = ["fio"]
        verbose_name = "Воспитанник"
        verbose_name_plural = "Воспитанники"

    def __str__(self):
        return self.fio

    def guardians(self):
        return Guardian.objects.filter(guardian_match(self.p_id, self.iin))


def guardian_match(p_id, iin):
    # в табеле у ребёнка может быть другой id, чем в списке группы e-orda, поэтому ищем и по ИИН
    return Q(child_pid=p_id) | Q(child_iin=iin) if iin else Q(child_pid=p_id)


def sync_children(p_ids=None):
    """Обновить воспитанников по табелю: ФИО, ИИН и группа — из последнего месяца, где есть ребёнок.
    Галочку «Посещает» не трогает."""
    qs = ChildRecord.objects.order_by("month")
    if p_ids is not None:
        qs = qs.filter(p_id__in=p_ids)
    latest = {}
    for rec in qs.only("p_id", "iin", "fio", "group_name", "month"):
        latest[rec.p_id] = rec
    Child.objects.bulk_create(
        [Child(p_id=r.p_id, iin=r.iin, fio=r.fio, group_name=r.group_name, last_month=r.month) for r in latest.values()],
        update_conflicts=True, unique_fields=["p_id"], update_fields=["iin", "fio", "group_name", "last_month"],
    )


class Families:
    """Семьи: дети, у которых общий родитель (по ИИН родителя из контактов e-orda).

    Ребёнок в табеле может быть под разными id, поэтому дети сравниваются по ИИН, а без ИИН — по id."""

    def __init__(self):
        self.children = list(Child.objects.all())
        self.iin_by_pid = {c.p_id: c.iin for c in self.children if c.iin}
        self.parent = {}  # объединение в семьи: ребёнок или родитель → кто-то из той же семьи
        for child_pid, child_iin, parent_iin in Guardian.objects.values_list("child_pid", "child_iin", "iin"):
            if is_person_iin(parent_iin):
                self._join(self.key(child_pid, child_iin), "parent " + parent_iin)
        self.manual = {self.key(c.p_id, c.iin): c.large_family for c in self.children if c.large_family is not None}
        self.members = defaultdict(dict)  # семья → {ребёнок: воспитанник из последнего месяца}
        for c in sorted(self.children, key=lambda c: c.last_month):
            key = self.key(c.p_id, c.iin)
            self.members[self._find(key)][key] = c

    def key(self, p_id, iin=""):
        return iin or self.iin_by_pid.get(p_id) or f"id {p_id}"

    def _find(self, node):
        while (up := self.parent.get(node, node)) != node:
            self.parent[node] = self.parent.get(up, up)
            node = up
        return node

    def _join(self, a, b):
        a, b = self._find(a), self._find(b)
        if a != b:
            self.parent[a] = b

    def large(self, records):
        """(месяц, p_id) детей из многодетных семей среди строк табеля: в табеле за тот же месяц
        есть ещё ребёнок их родителя. Отметка воспитанника «Да»/«Нет» важнее.
        Передавайте строки за весь месяц, а не одной группы: брат или сестра бывают в другой группе."""
        keyed = [(rec, self.key(rec.p_id, rec.iin)) for rec in records]
        kids = defaultdict(set)
        for rec, key in keyed:
            kids[rec.month, self._find(key)].add(key)
        return {(rec.month, rec.p_id) for rec, key in keyed
                if self.manual.get(key, len(kids[rec.month, self._find(key)]) > 1)}

    def siblings(self, p_id, iin=""):
        """Братья и сёстры ребёнка — воспитанники с общим родителем."""
        me = self.key(p_id, iin)
        found = self.members[self._find(me)]
        return sorted((c for key, c in found.items() if key != me), key=lambda c: c.fio)


def is_person_iin(iin):
    """ИИН из 12 цифр; заглушки вроде «000000000000» не считаются — иначе чужие дети стали бы семьёй."""
    return bool(re.fullmatch(r"\d{12}", iin or "")) and len(set(iin)) > 1


class PaymentInfo(models.Model):
    """Оплата ребёнка за месяц: сколько и как внесено, ежемесячная сумма."""

    CASH, ONLINE = "cash", "online"
    METHODS = [(CASH, "Наличные"), (ONLINE, "Онлайн")]

    child = models.OneToOneField(ChildRecord, on_delete=models.CASCADE, related_name="payment")
    last_payment = models.FloatField(default=0)
    method = models.CharField("Способ оплаты", max_length=10, choices=METHODS, blank=True)
    # Пусто — по умолчанию: 51 000 многодетной семье, 60 000 остальным
    monthly_payment = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Оплата за месяц"
        verbose_name_plural = "Оплаты за месяц"

    def __str__(self):
        return f"{self.child.fio}: {self.monthly_payment or 'по умолчанию'}"


def keep_old_monthly(before_month):
    """Строкам табеля до месяца before_month без своей ежемесячной суммы — прежняя сумма по умолчанию:
    так они и были посчитаны, новые суммы по умолчанию не должны менять долги задним числом."""
    PaymentInfo.objects.bulk_create(
        [PaymentInfo(child=rec, monthly_payment=OLD_DEFAULT_MONTHLY)
         for rec in ChildRecord.objects.filter(month__lt=before_month, payment__isnull=True)],
        batch_size=500,
    )


class ChangeLog(models.Model):
    """Журнал: кто, когда и какой день поменял."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="timesheet_changes")
    username = models.CharField(max_length=150, blank=True)  # остаётся, даже если пользователя удалили
    month = models.CharField(max_length=7, db_index=True)
    p_id = models.BigIntegerField()
    child_fio = models.CharField(max_length=200)
    group_name = models.CharField(max_length=120, blank=True)
    day_num = models.IntegerField()
    old_status = models.CharField(max_length=80, blank=True)
    new_status = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Изменение табеля"
        verbose_name_plural = "Журнал изменений табеля"

    def __str__(self):
        return f"{self.username}: {self.child_fio} д.{self.day_num} → {self.new_status}"


class PaymentImport(models.Model):
    """Архив квитанций, которые раньше загружал Telegram-бот. Только для просмотра в админке."""

    receipt_no = models.CharField(max_length=100, unique=True, db_index=True)
    iin = models.CharField(max_length=20)
    amount = models.FloatField()
    paid_at = models.CharField(max_length=60, blank=True)  # дата/время из квитанции (текст)
    payer_fio = models.CharField(max_length=200, blank=True)
    month = models.CharField(max_length=7)  # 'YYYY-MM'
    purpose = models.CharField(max_length=120, default="Оплата за месяц")
    child = models.ForeignKey(ChildRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="imports")
    raw = models.TextField(blank=True)  # исходные данные (на всякий случай)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Квитанция (архив)"
        verbose_name_plural = "Квитанции (архив)"

    def __str__(self):
        return f"{self.receipt_no}: {self.iin} {self.amount} ({self.month})"


class Guardian(models.Model):
    """Родитель/опекун ребёнка, импортируется из e-orda (GetPupil → Guardians)."""

    FATHER, MOTHER = 1, 2  # Gender в e-orda
    GENDERS = [(FATHER, "Отец"), (MOTHER, "Мать")]

    child_pid = models.BigIntegerField(db_index=True)  # p_id ребёнка
    child_iin = models.CharField(max_length=20, blank=True)
    child_fio = models.CharField(max_length=200, blank=True)
    gender = models.PositiveSmallIntegerField("Кем приходится", choices=GENDERS, null=True, blank=True)
    fio = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=160, blank=True)  # номера через запятую
    email = models.CharField(max_length=254, blank=True)
    iin = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["child_fio", "fio"]
        verbose_name = "Родитель / опекун"
        verbose_name_plural = "Родители / опекуны"

    def __str__(self):
        return f"{self.fio} → {self.child_fio}"

    @property
    def phones(self):
        return [p.strip() for p in self.phone.split(",") if p.strip()]

    @property
    def contact(self):
        """«ФИО, телефоны» — так родителя вписывают в медицинские журналы."""
        return ", ".join(filter(None, [self.fio, *self.phones]))
