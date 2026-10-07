"""Журналы 12, 16 и 17 — по утверждённым формам 1, 3 и 2.

Прежние записи переносятся в новые графы; то, чему в форме нет графы, дописывается
в «Примечание» (журнал 12, 16) или в наименование блюда (журнал 17), чтобы ничего не потерялось.
"""
import datetime

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone

MEALS = {"BREAKFAST": "Завтрак", "BRUNCH": "Второй завтрак", "LUNCH": "Обед", "SNACK": "Полдник", "DINNER": "Ужин"}
GRADES = {"5": "отлично", "4": "хорошо", "3": "удовлетворительно", "2": "неудовлетворительно"}


def at(day, time):
    value = datetime.datetime.combine(day, time or datetime.time())
    return timezone.make_aware(value) if settings.USE_TZ else value


def join(*parts, sep="; "):
    return sep.join(p for p in parts if p)


def to_official_forms(apps, schema_editor):
    for r in apps.get_model("medjournal", "PerishableFoodBrakerage").objects.all():
        r.used_days = f"{r.used_at:%d.%m.%Y}" if r.used_at else ""
        r.notes = join(
            r.notes,
            r.packaging and f"Упаковка: {r.packaging}",
            r.supplier and f"Поставщик: {r.supplier}",
            r.documents and f"Документ: {r.documents}",
            r.production_date and f"Дата изготовления: {r.production_date:%d.%m.%Y}",
            r.storage and f"Хранение: {r.storage}",
            "" if r.accepted else "Не принято (возврат)",
        )
        r.save(update_fields=["used_days", "notes"])

    for r in apps.get_model("medjournal", "DishQualityAssessment").objects.all():
        dish = f"{MEALS[r.meal]}: {r.dish}" if r.meal in MEALS else r.dish
        r.dish = join(dish, r.output_g and f"выход {r.output_g} г", sep=", ")[:255]
        r.organoleptic = join(r.organoleptic, r.grade in GRADES and f"оценка «{GRADES[r.grade]}»", sep=", ")
        r.made_at = at(r.date, r.time_checked)
        r.permitted_at = (r.serve_time or r.time_checked) if r.permitted else None
        r.inspected_by = r.commission[:255]
        r.notes = join(r.notes, "" if r.permitted else f"Не допущено к реализации: {r.dish}")
        r.save(update_fields=["dish", "organoleptic", "made_at", "permitted_at", "inspected_by", "notes"])

    for r in apps.get_model("medjournal", "VitaminCRecord").objects.all():
        r.prepared_at = at(r.date, r.time_added)
        r.portion_mg = r.mg_per_child
        r.total_mg = r.mg_per_child * r.children_count
        r.dish = join(r.dish, r.group_name and f"группа {r.group_name}", f"{r.children_count} порц.", r.notes,
                      sep=", ")[:255]
        r.save(update_fields=["prepared_at", "portion_mg", "total_mg", "dish"])


class Migration(migrations.Migration):

    dependencies = [
        ("medjournal", "0002_journal_period"),
    ]

    operations = [
        # 1. новые графы (пока необязательные) и более длинные поля — чтобы было куда переносить
        migrations.AddField("perishablefoodbrakerage", "used_days", models.TextField(blank=True, default="")),
        migrations.AlterField("perishablefoodbrakerage", "notes", models.TextField(blank=True)),
        migrations.AddField("dishqualityassessment", "made_at", models.DateTimeField(null=True)),
        migrations.AddField("dishqualityassessment", "permitted_at", models.TimeField(null=True, blank=True)),
        migrations.AddField("dishqualityassessment", "executor", models.CharField(max_length=255, blank=True, default="")),
        migrations.AddField("dishqualityassessment", "inspected_by", models.CharField(max_length=255, default="")),
        migrations.AlterField("dishqualityassessment", "dish", models.CharField(max_length=255)),
        migrations.AlterField("dishqualityassessment", "organoleptic", models.TextField()),
        migrations.AlterField("dishqualityassessment", "notes", models.TextField(blank=True)),
        migrations.AddField("vitamincrecord", "prepared_at", models.DateTimeField(null=True)),
        migrations.AddField("vitamincrecord", "total_mg", models.DecimalField(max_digits=8, decimal_places=1, null=True)),
        migrations.AddField("vitamincrecord", "portion_mg", models.DecimalField(max_digits=6, decimal_places=1, null=True)),
        migrations.AlterField("vitamincrecord", "dish", models.CharField(max_length=255)),

        # 2. перенос прежних записей
        migrations.RunPython(to_official_forms),

        # 3. графы, которых нет в формах
        *[migrations.RemoveField("perishablefoodbrakerage", name) for name in
          ("packaging", "supplier", "documents", "production_date", "storage", "used_at", "accepted")],
        *[migrations.RemoveField("dishqualityassessment", name) for name in
          ("date", "time_checked", "meal", "output_g", "grade", "permitted", "serve_time", "commission")],
        *[migrations.RemoveField("vitamincrecord", name) for name in
          ("date", "group_name", "age_group", "children_count", "mg_per_child", "time_added", "serve_time", "notes")],

        # 4. окончательный вид граф — названия как в формах
        migrations.AlterModelOptions("dishqualityassessment", options={
            "ordering": ["-made_at"], "verbose_name": "Оценка блюда",
            "verbose_name_plural": "16. Журнал органолептической оценки качества блюд и кулинарных изделий"}),
        migrations.AlterModelOptions("vitamincrecord", options={
            "ordering": ["-prepared_at"], "verbose_name": "С-витаминизация",
            "verbose_name_plural": "17. Журнал «С-витаминизации»"}),
        migrations.AlterField("perishablefoodbrakerage", "received_at", models.DateTimeField(
            verbose_name="Дата и час поступления продовольственного сырья и пищевых продуктов")),
        migrations.AlterField("perishablefoodbrakerage", "product", models.CharField(
            max_length=200, verbose_name="Наименование пищевых продуктов")),
        migrations.AlterField("perishablefoodbrakerage", "quantity", models.CharField(
            max_length=50, verbose_name="Количество поступившего продовольственного сырья и пищевых продуктов "
                                        "(в килограммах, литрах, штуках)")),
        migrations.AlterField("perishablefoodbrakerage", "organoleptic", models.CharField(
            max_length=255, verbose_name="Результаты органолептической оценки поступившего продовольственного сырья "
                                         "и пищевых продуктов")),
        migrations.AlterField("perishablefoodbrakerage", "shelf_life_until", models.DateTimeField(
            blank=True, null=True,
            verbose_name="Конечный срок реализации продовольственного сырья и пищевых продуктов")),
        migrations.AlterField("perishablefoodbrakerage", "used_days", models.TextField(
            blank=True, help_text="Каждый день — с новой строки, например: 21.09.2026 12:00 — 5 кг",
            verbose_name="Дата и час фактической реализации продовольственного сырья и пищевых продуктов по дням")),
        migrations.AlterField("perishablefoodbrakerage", "responsible", models.CharField(
            max_length=150, verbose_name="Ф.И.О. (при наличии) подпись ответственного лица")),
        migrations.AlterField("perishablefoodbrakerage", "notes", models.TextField(
            blank=True, help_text="Факты списания, возврата продуктов", verbose_name="Примечание")),
        migrations.AlterField("dishqualityassessment", "made_at", models.DateTimeField(
            verbose_name="Дата, время изготовления блюд и кулинарных изделий")),
        migrations.AlterField("dishqualityassessment", "dish", models.CharField(
            max_length=255, verbose_name="Наименование блюд и кулинарных изделий")),
        migrations.AlterField("dishqualityassessment", "organoleptic", models.TextField(
            verbose_name="Органолептическая оценка, включая оценку степени готовности блюд и кулинарных изделий")),
        migrations.AlterField("dishqualityassessment", "permitted_at", models.TimeField(
            blank=True, null=True,
            help_text="Блюдо не допущено — оставьте пустым и впишите его в «Примечание».",
            verbose_name="Разрешение к реализации (время)")),
        migrations.AlterField("dishqualityassessment", "executor", models.CharField(
            blank=True, max_length=255,
            verbose_name="Ответственный исполнитель (Ф.И.О. (при его наличии), должность)")),
        migrations.AlterField("dishqualityassessment", "inspected_by", models.CharField(
            max_length=255, verbose_name="Ф.И.О. (при его наличии), лица проводившего бракераж")),
        migrations.AlterField("dishqualityassessment", "notes", models.TextField(
            blank=True, help_text="Наименования готовой продукции, не допущенной к реализации",
            verbose_name="Примечание")),
        migrations.AlterField("vitamincrecord", "prepared_at", models.DateTimeField(
            verbose_name="Дата и час приготовления блюда")),
        migrations.AlterField("vitamincrecord", "dish", models.CharField(
            max_length=255, verbose_name="Наименование блюда")),
        migrations.AlterField("vitamincrecord", "total_mg", models.DecimalField(
            decimal_places=1, help_text="В миллиграммах", max_digits=8,
            verbose_name="Общее количество добавленного витамина")),
        migrations.AlterField("vitamincrecord", "portion_mg", models.DecimalField(
            decimal_places=1, help_text="В миллиграммах", max_digits=6,
            verbose_name="Содержание витамина «С» в одной порции")),
        migrations.AlterField("vitamincrecord", "responsible", models.CharField(
            max_length=150, verbose_name="Подпись ответственного лица")),
    ]
