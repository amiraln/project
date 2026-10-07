"""
Медицинская документация дошкольной организации (РК).
17 журналов/документов медицинского кабинета и пищеблока.

Журналы ссылаются на воспитанников из табеля (payments.Child).
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .utils import fmt

CHILD_MODEL = "payments.Child"


def child_fk(verbose_name="Ребёнок", **kw):
    kw.setdefault("on_delete", models.PROTECT)
    return models.ForeignKey(CHILD_MODEL, related_name="+", verbose_name=verbose_name, **kw)


def days_between(start, end):
    if start and end:
        return (end - start).days + 1
    return None


class BaseRecord(models.Model):
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
        on_delete=models.SET_NULL, related_name="+", verbose_name="Кто внёс",
    )

    class Meta:
        abstract = True


# ---------------------------------------------------------------- 1
class InfectiousDiseaseRecord(BaseRecord):
    """Журнал учёта инфекционных заболеваний (ф. 060/у)."""
    child = child_fk()
    date_detected = models.DateField("Дата выявления")
    date_onset = models.DateField("Дата заболевания", null=True, blank=True)
    diagnosis = models.CharField("Диагноз", max_length=255)
    diagnosis_confirmed = models.CharField("Диагноз подтверждён (кем, когда)", max_length=255, blank=True)
    lab_confirmation = models.CharField("Лабораторное подтверждение", max_length=255, blank=True)
    date_isolated = models.DateField("Дата изоляции", null=True, blank=True)
    hospitalized_to = models.CharField("Место госпитализации / лечения", max_length=255, blank=True)
    notice_sent_at = models.DateTimeField("Экстренное извещение в ТД СЭК (дата, время)", null=True, blank=True)
    notice_received_by = models.CharField("Извещение принял (ФИО)", max_length=150, blank=True)
    date_returned = models.DateField("Дата возвращения в д/с", null=True, blank=True)
    return_certificate = models.CharField("Справка о допуске (№, кем выдана)", max_length=255, blank=True)
    measures = models.TextField("Проведённые противоэпидемические мероприятия", blank=True)
    responsible = models.CharField("Медработник", max_length=150, blank=True)

    class Meta:
        verbose_name = "Запись журнала инфекционных заболеваний"
        verbose_name_plural = "1. Журнал учёта инфекционных заболеваний"
        ordering = ["-date_detected", "-id"]

    def __str__(self):
        return f"{self.child} — {self.diagnosis} ({self.date_detected:%d.%m.%Y})"


# ---------------------------------------------------------------- 2
class SomaticDiseaseRecord(BaseRecord):
    """Журнал соматической (неинфекционной) заболеваемости."""
    child = child_fk()
    date_start = models.DateField("Дата начала заболевания")
    diagnosis = models.CharField("Диагноз", max_length=255)
    date_end = models.DateField("Дата выздоровления", null=True, blank=True)
    certificate = models.CharField("Справка (№, кем выдана)", max_length=255, blank=True)
    notes = models.TextField("Примечание", blank=True)

    class Meta:
        verbose_name = "Запись журнала соматической заболеваемости"
        verbose_name_plural = "2. Журнал соматической заболеваемости"
        ordering = ["-date_start", "-id"]

    def clean(self):
        if self.date_end and self.date_start and self.date_end < self.date_start:
            raise ValidationError({"date_end": "Дата выздоровления раньше даты начала."})

    @property
    def days(self):
        return days_between(self.date_start, self.date_end)

    def __str__(self):
        return f"{self.child} — {self.diagnosis}"


# ---------------------------------------------------------------- 3
class InfectionContactRecord(BaseRecord):
    """Журнал учёта контактов с острыми инфекционными заболеваниями."""
    child = child_fk("Контактный ребёнок")
    source_case = models.ForeignKey(
        InfectiousDiseaseRecord, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="contacts", verbose_name="Источник (случай заболевания)",
    )
    disease = models.CharField("Инфекция", max_length=255)
    contact_date = models.DateField("Дата последнего контакта")
    place = models.CharField("Место контакта (группа, семья)", max_length=255, blank=True)
    quarantine_start = models.DateField("Начало карантина / наблюдения", null=True, blank=True)
    quarantine_end = models.DateField("Окончание карантина / наблюдения", null=True, blank=True)
    vaccination_status = models.CharField("Прививочный анамнез по данной инфекции", max_length=255, blank=True)
    measures = models.TextField("Мероприятия (осмотры, термометрия, иммунизация, обследование)", blank=True)
    outcome = models.CharField("Исход наблюдения", max_length=255, blank=True)
    responsible = models.CharField("Медработник", max_length=150, blank=True)

    class Meta:
        verbose_name = "Контакт с инфекционным больным"
        verbose_name_plural = "3. Журнал учёта контактов с острыми инфекционными заболеваниями"
        ordering = ["-contact_date", "-id"]

    def __str__(self):
        return f"{self.child} — контакт: {self.disease}"


# ---------------------------------------------------------------- 4
VACCINES = [
    ("BCG", "БЦЖ"), ("HBV", "ВГВ (гепатит B)"), ("OPV", "ОПВ"), ("IPV", "ИПВ"),
    ("DTP", "АКДС / АбКДС"), ("PENTA", "АбКДС+ИПВ+Hib (пентавакцина)"),
    ("HEXA", "АбКДС+Hib+ВГВ+ИПВ (гексавакцина)"), ("HIB", "Hib"),
    ("PCV", "ПКВ (пневмококковая)"), ("MMR", "ККП (корь, краснуха, паротит)"),
    ("DT", "АДС"), ("TD", "АДС-М"), ("HAV", "Гепатит A"), ("VAR", "Ветряная оспа"),
    ("FLU", "Грипп"), ("OTHER", "Другая"),
]
DOSES = [("V1", "V1"), ("V2", "V2"), ("V3", "V3"), ("V4", "V4"),
         ("RV1", "RV1"), ("RV2", "RV2"), ("RV3", "RV3"), ("ONE", "Однократно")]


class VaccinationRecord(BaseRecord):
    """Карта профилактических прививок (ф. 063/у) — одна строка = одна прививка."""
    child = child_fk()
    vaccine = models.CharField("Прививка", max_length=10, choices=VACCINES)
    vaccine_other = models.CharField("Наименование, если «Другая»", max_length=150, blank=True)
    dose = models.CharField("Вакцинация / ревакцинация", max_length=5, choices=DOSES)
    date = models.DateField("Дата")
    drug_name = models.CharField("Препарат (торговое наименование)", max_length=150, blank=True)
    series = models.CharField("Серия", max_length=50, blank=True)
    expiry = models.DateField("Срок годности", null=True, blank=True)
    dose_ml = models.DecimalField("Доза, мл", max_digits=4, decimal_places=2, null=True, blank=True)
    route = models.CharField("Способ введения", max_length=50, blank=True)
    reaction_local = models.CharField("Реакция местная", max_length=150, blank=True)
    reaction_general = models.CharField("Реакция общая", max_length=150, blank=True)
    place = models.CharField("Где проведена (д/с, поликлиника)", max_length=150, blank=True)
    medical_worker = models.CharField("Медработник", max_length=150, blank=True)

    class Meta:
        verbose_name = "Профилактическая прививка"
        verbose_name_plural = "4. Карта профилактических прививок"
        ordering = ["-date", "-id"]

    def vaccine_label(self):
        return self.vaccine_other if self.vaccine == "OTHER" and self.vaccine_other else self.get_vaccine_display()
    vaccine_label.short_description = "Прививка"

    def __str__(self):
        return f"{self.child} — {self.vaccine_label()} {self.dose}"


class VaccinationExemption(BaseRecord):
    """Медицинские отводы и отказы (часть карты прививок)."""
    KIND = [("MED", "Медицинский отвод"), ("REFUSAL", "Отказ родителей")]
    child = child_fk()
    kind = models.CharField("Вид", max_length=10, choices=KIND)
    vaccine = models.CharField("Прививка", max_length=10, choices=VACCINES)
    date_from = models.DateField("С")
    date_to = models.DateField("По (для временного отвода)", null=True, blank=True)
    reason = models.CharField("Причина / основание", max_length=255)
    document = models.CharField("Документ (заключение, письменный отказ)", max_length=255, blank=True)

    class Meta:
        verbose_name = "Медотвод / отказ от прививки"
        verbose_name_plural = "4а. Медотводы и отказы от прививок"
        ordering = ["-date_from"]

    def __str__(self):
        return f"{self.child} — {self.get_kind_display()} ({self.get_vaccine_display()})"


# ---------------------------------------------------------------- 5
class MantouxTest(BaseRecord):
    """Журнал регистрации проб Манту (и Диаскинтеста)."""
    TEST_TYPES = [("MANTOUX", "Манту 2 ТЕ"), ("DST", "Диаскинтест")]
    RESULTS = [("NEG", "отрицательная"), ("DOUBT", "сомнительная"),
               ("POS", "положительная"), ("HYPER", "гиперергическая")]
    PURPOSES = [("SCREEN", "Скрининг"), ("RISK", "Группа риска"), ("CONTROL", "Контроль")]

    child = child_fk()
    test_type = models.CharField("Проба", max_length=10, choices=TEST_TYPES, default="MANTOUX")
    purpose = models.CharField("Цель", max_length=10, choices=PURPOSES, default="SCREEN")
    date_placed = models.DateField("Дата постановки")
    drug_series = models.CharField("Серия препарата", max_length=50, blank=True)
    drug_expiry = models.DateField("Срок годности", null=True, blank=True)
    arm = models.CharField("Рука", max_length=10, choices=[("L", "левая"), ("R", "правая")], blank=True)
    date_read = models.DateField("Дата чтения (через 72 ч)", null=True, blank=True)
    papule_mm = models.PositiveSmallIntegerField("Папула, мм", null=True, blank=True)
    hyperemia_mm = models.PositiveSmallIntegerField("Гиперемия, мм", null=True, blank=True)
    vesicles = models.BooleanField("Везикулы / некроз / лимфангит", default=False)
    result = models.CharField("Результат", max_length=5, choices=RESULTS, blank=True, editable=False)
    bcg_scar_mm = models.PositiveSmallIntegerField("Рубчик БЦЖ, мм", null=True, blank=True)
    previous_papule_mm = models.PositiveSmallIntegerField("Папула в прошлом году, мм", null=True, blank=True)
    nurse = models.CharField("Медсестра", max_length=150, blank=True)
    notes = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Проба Манту"
        verbose_name_plural = "5. Журнал регистрации проб Манту"
        ordering = ["-date_placed", "-id"]

    def compute_result(self):
        p, h = self.papule_mm, self.hyperemia_mm
        if p is None and h is None:
            return ""
        p = p or 0
        if self.test_type == "DST":
            if self.vesicles or p >= 15:
                return "HYPER"
            if p > 0:
                return "POS"
            return "DOUBT" if (h or 0) > 0 else "NEG"
        # Манту 2 ТЕ
        if self.vesicles or p >= 17:
            return "HYPER"
        if p >= 5:
            return "POS"
        if p >= 2 or (h or 0) > 0:
            return "DOUBT"
        return "NEG"

    @property
    def is_turn(self):
        """Нарастание папулы на 6 мм и более за год."""
        if self.papule_mm is not None and self.previous_papule_mm is not None:
            return self.papule_mm - self.previous_papule_mm >= 6
        return False

    def save(self, *args, **kwargs):
        self.result = self.compute_result()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.child} — {self.get_test_type_display()} {self.date_placed:%d.%m.%Y}"


# ---------------------------------------------------------------- 6
TB_RISK_FACTORS = [
    ("CONTACT", "Контакт с больным туберкулёзом"),
    ("NO_BCG", "Не привит БЦЖ / нет рубчика"),
    ("FREQ_ILL", "Часто болеющий"),
    ("CHRONIC", "Хронические заболевания (диабет, ВИЧ, иммуносупрессия и др.)"),
    ("SOCIAL", "Социальный риск (неблагополучная семья, мигранты и др.)"),
    ("HORMONES", "Длительная гормональная / иммуносупрессивная терапия"),
    ("OTHER", "Другое"),
]


class MantouxRiskGroupEntry(BaseRecord):
    """Журнал регистрации детей группы риска, подлежащих обследованию по пробе Манту."""
    child = child_fk()
    risk_factor = models.CharField("Фактор риска", max_length=10, choices=TB_RISK_FACTORS)
    risk_details = models.CharField("Уточнение", max_length=255, blank=True)
    date_included = models.DateField("Дата взятия на учёт")
    planned_test_date = models.DateField("Плановая дата обследования", null=True, blank=True)
    test = models.ForeignKey(MantouxTest, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+", verbose_name="Проведённая проба")
    date_excluded = models.DateField("Дата снятия с учёта", null=True, blank=True)
    notes = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Ребёнок группы риска (туберкулёз)"
        verbose_name_plural = "6. Журнал детей группы риска, подлежащих обследованию по пробе Манту"
        ordering = ["-date_included"]

    def test_result(self):
        if not self.test:
            return ""
        size = f", {self.test.papule_mm} мм" if self.test.papule_mm is not None else ""
        return f"{self.test.get_result_display()}{size}"
    test_result.short_description = "Результат пробы"

    def __str__(self):
        return f"{self.child} — {self.get_risk_factor_display()}"


# ---------------------------------------------------------------- 7
class TuberculinPositiveReferral(BaseRecord):
    """Журнал туберкулино-положительных лиц, подлежащих дообследованию у фтизиопедиатра."""
    REASONS = [
        ("TURN", "Вираж туберкулиновой пробы"),
        ("INCREASE", "Нарастание папулы на 6 мм и более"),
        ("HYPER", "Гиперергическая реакция"),
        ("PERSIST", "Монотонная реакция ≥12 мм 4 года и более"),
        ("DST_POS", "Положительный Диаскинтест"),
        ("OTHER", "Другое"),
    ]
    child = child_fk()
    test = models.ForeignKey(MantouxTest, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+", verbose_name="Проба, по которой направлен")
    reason = models.CharField("Основание направления", max_length=10, choices=REASONS)
    referral_date = models.DateField("Дата направления")
    phthisiatrician_visit = models.DateField("Дата осмотра фтизиопедиатром", null=True, blank=True)
    xray_result = models.CharField("Рентгенография / КТ", max_length=255, blank=True)
    conclusion = models.CharField("Заключение фтизиопедиатра", max_length=255, blank=True)
    dispensary_group = models.CharField("Группа диспансерного учёта", max_length=50, blank=True)
    admitted = models.BooleanField("Допущен в д/с", null=True, blank=True)
    admitted_date = models.DateField("Дата допуска", null=True, blank=True)
    notes = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Направление к фтизиопедиатру"
        verbose_name_plural = "7. Журнал туберкулино-положительных лиц, подлежащих дообследованию у фтизиопедиатра"
        ordering = ["-referral_date"]

    def test_info(self):
        if not self.test:
            return ""
        return f"{self.test.date_placed:%d.%m.%Y}, п. {self.test.papule_mm if self.test.papule_mm is not None else '—'} мм"
    test_info.short_description = "Проба"

    def __str__(self):
        return f"{self.child} — {self.get_reason_display()}"


# ---------------------------------------------------------------- 8
class ChemoprophylaxisCourse(BaseRecord):
    """Журнал проведения контролируемой химиопрофилактики."""
    child = child_fk()
    referral = models.ForeignKey(TuberculinPositiveReferral, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="+", verbose_name="Направление")
    indication = models.CharField("Показание", max_length=255)
    drug = models.CharField("Препарат", max_length=150)
    dose = models.CharField("Доза, кратность", max_length=100)
    prescribed_by = models.CharField("Назначил (фтизиопедиатр)", max_length=150, blank=True)
    date_start = models.DateField("Начало курса")
    date_end_planned = models.DateField("Окончание (план)", null=True, blank=True)
    date_end_actual = models.DateField("Окончание (факт)", null=True, blank=True)
    side_effects = models.CharField("Побочные реакции", max_length=255, blank=True)
    notes = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Курс химиопрофилактики"
        verbose_name_plural = "8. Журнал проведения контролируемой химиопрофилактики"
        ordering = ["-date_start"]

    def doses_given(self):
        total = self.doses.count()
        given = self.doses.filter(taken=True).count()
        return f"{given} из {total}" if total else "—"
    doses_given.short_description = "Принято доз"

    def __str__(self):
        return f"{self.child} — {self.drug} с {self.date_start:%d.%m.%Y}"


class ChemoprophylaxisDose(models.Model):
    course = models.ForeignKey(ChemoprophylaxisCourse, on_delete=models.CASCADE,
                               related_name="doses", verbose_name="Курс")
    date = models.DateField("Дата")
    taken = models.BooleanField("Принял в присутствии медработника", default=True)
    reason_missed = models.CharField("Причина пропуска", max_length=150, blank=True)
    nurse = models.CharField("Медработник", max_length=150, blank=True)

    class Meta:
        verbose_name = "Приём препарата"
        verbose_name_plural = "Приёмы препарата"
        ordering = ["date"]
        unique_together = [("course", "date")]

    def __str__(self):
        return f"{self.date:%d.%m.%Y}"


# ---------------------------------------------------------------- 9
class HelminthExam(BaseRecord):
    """Журнал регистрации лиц, обследованных на гельминты."""
    METHODS = [("SCRAPE", "Соскоб на энтеробиоз"), ("STOOL", "Кал на яйца гельминтов"),
               ("BOTH", "Соскоб + кал"), ("OTHER", "Другое")]
    child = child_fk()
    exam_date = models.DateField("Дата обследования")
    method = models.CharField("Метод", max_length=10, choices=METHODS)
    lab = models.CharField("Лаборатория", max_length=150, blank=True)
    positive = models.BooleanField("Результат положительный", default=False)
    pathogen = models.CharField("Выявлено", max_length=150, blank=True)
    treatment = models.CharField("Лечение (препарат, даты)", max_length=255, blank=True)
    control_date = models.DateField("Контрольное обследование", null=True, blank=True)
    control_result = models.CharField("Результат контроля", max_length=150, blank=True)
    notes = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Обследование на гельминты"
        verbose_name_plural = "9. Журнал регистрации лиц, обследованных на гельминты"
        ordering = ["-exam_date"]

    def result_label(self):
        return f"полож. ({self.pathogen})" if self.positive else "отриц."
    result_label.short_description = "Результат"

    def __str__(self):
        return f"{self.child} — {self.exam_date:%d.%m.%Y}"


# ---------------------------------------------------------------- 10
HEALTH_GROUPS = [("I", "I"), ("II", "II"), ("III", "III"), ("IV", "IV"), ("V", "V")]
PE_GROUPS = [("MAIN", "основная"), ("PREP", "подготовительная"), ("SPEC", "специальная")]


class HealthPassport(BaseRecord):
    """Паспорт здоровья ребёнка."""
    child = models.OneToOneField(CHILD_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="Ребёнок")
    blood_group = models.CharField("Группа крови, резус", max_length=20, blank=True)
    health_group = models.CharField("Группа здоровья", max_length=3, choices=HEALTH_GROUPS, blank=True)
    pe_group = models.CharField("Физкультурная группа", max_length=5, choices=PE_GROUPS, blank=True)
    allergies = models.TextField("Аллергия (пищевая, лекарственная)", blank=True)
    chronic = models.TextField("Хронические заболевания", blank=True)
    dispensary = models.CharField("Диспансерный учёт (у кого, по поводу)", max_length=255, blank=True)
    disability = models.CharField("Инвалидность", max_length=255, blank=True)
    diet = models.CharField("Особенности питания / диета", max_length=255, blank=True)
    polyclinic = models.CharField("Прикреплён к поликлинике", max_length=150, blank=True)
    notes = models.TextField("Примечание", blank=True)

    class Meta:
        verbose_name = "Паспорт здоровья"
        verbose_name_plural = "10. Паспорт здоровья ребёнка"
        ordering = ["-updated_at"]

    def last_measure(self):
        m = self.measurements.order_by("-date").first()
        return f"{m.height_cm} см / {m.weight_kg} кг ({m.date:%d.%m.%Y})" if m else ""
    last_measure.short_description = "Последние рост/вес"

    def __str__(self):
        return f"Паспорт здоровья: {self.child}"


class Anthropometry(models.Model):
    passport = models.ForeignKey(HealthPassport, on_delete=models.CASCADE,
                                 related_name="measurements", verbose_name="Паспорт")
    date = models.DateField("Дата")
    height_cm = models.DecimalField("Рост, см", max_digits=5, decimal_places=1)
    weight_kg = models.DecimalField("Вес, кг", max_digits=5, decimal_places=2)
    physical_development = models.CharField("Физическое развитие", max_length=100, blank=True)
    vision = models.CharField("Острота зрения", max_length=50, blank=True)
    posture = models.CharField("Осанка", max_length=100, blank=True)

    class Meta:
        verbose_name = "Антропометрия"
        verbose_name_plural = "Антропометрия"
        ordering = ["date"]

    @property
    def bmi(self):
        if self.height_cm and self.weight_kg:
            h = Decimal(self.height_cm) / 100
            return round(Decimal(self.weight_kg) / (h * h), 1)
        return None


# ---------------------------------------------------------------- 11
RISK_CATEGORIES = [
    ("FREQ_ILL", "Часто и длительно болеющие"),
    ("ALLERGY", "Аллергические заболевания"),
    ("ANEMIA", "Анемия"),
    ("UNDERWEIGHT", "Дефицит массы тела"),
    ("OBESITY", "Избыточная масса тела / ожирение"),
    ("POSTURE", "Нарушение осанки, плоскостопие"),
    ("VISION", "Нарушение зрения"),
    ("SPEECH", "Нарушение речи"),
    ("NEURO", "Неврологические нарушения"),
    ("DISPENSARY", "Состоящие на диспансерном учёте"),
    ("DISABLED", "Дети с инвалидностью"),
    ("SOCIAL", "Социальный риск"),
    ("OTHER", "Другое"),
]


class RiskGroupEntry(BaseRecord):
    """Списки детей группы риска."""
    child = child_fk()
    category = models.CharField("Группа риска", max_length=12, choices=RISK_CATEGORIES)
    diagnosis = models.CharField("Диагноз / основание", max_length=255, blank=True)
    date_included = models.DateField("Дата включения")
    date_excluded = models.DateField("Дата исключения", null=True, blank=True)
    measures = models.TextField("Оздоровительные мероприятия", blank=True)
    notes = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Ребёнок группы риска"
        verbose_name_plural = "11. Списки детей группы риска"
        ordering = ["category", "-date_included"]

    def __str__(self):
        return f"{self.child} — {self.get_category_display()}"


# ---------------------------------------------------------------- 12
class PerishableFoodBrakerage(BaseRecord):
    """Бракеражный журнал скоропортящейся пищевой продукции и полуфабрикатов (Форма 1, входной контроль)."""
    received_at = models.DateTimeField("Дата и час поступления продовольственного сырья и пищевых продуктов")
    product = models.CharField("Наименование пищевых продуктов", max_length=200)
    quantity = models.CharField(
        "Количество поступившего продовольственного сырья и пищевых продуктов (в килограммах, литрах, штуках)",
        max_length=50)
    organoleptic = models.CharField(
        "Результаты органолептической оценки поступившего продовольственного сырья и пищевых продуктов",
        max_length=255)
    shelf_life_until = models.DateTimeField(
        "Конечный срок реализации продовольственного сырья и пищевых продуктов", null=True, blank=True)
    used_days = models.TextField(
        "Дата и час фактической реализации продовольственного сырья и пищевых продуктов по дням", blank=True,
        help_text="Каждый день — с новой строки, например: 21.09.2026 12:00 — 5 кг")
    responsible = models.CharField("Ф.И.О. (при наличии) подпись ответственного лица", max_length=150)
    notes = models.TextField("Примечание", blank=True, help_text="Факты списания, возврата продуктов")

    class Meta:
        verbose_name = "Бракераж скоропортящейся продукции"
        verbose_name_plural = "12. Бракеражный журнал скоропортящейся пищевой продукции и полуфабрикатов"
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.product} ({timezone.localtime(self.received_at):%d.%m.%Y})"


# ---------------------------------------------------------------- 13
class KitchenStaffInspection(BaseRecord):
    """Журнал результатов осмотра работников пищеблока (журнал «Здоровье»)."""
    date = models.DateField("Дата")
    employee = models.CharField("ФИО работника", max_length=150)
    position = models.CharField("Должность", max_length=100)
    skin_ok = models.BooleanField("Кожа без гнойничков и порезов", default=True)
    throat_ok = models.BooleanField("Нет признаков ОРВИ / ангины", default=True)
    gut_ok = models.BooleanField("Нет кишечных расстройств", default=True)
    family_ok = models.BooleanField("Нет больных кишечными инфекциями в семье", default=True)
    admitted = models.BooleanField("Допущен к работе", default=True)
    measures = models.CharField("Принятые меры", max_length=255, blank=True)
    inspected_by = models.CharField("Осмотрел (медработник)", max_length=150)

    class Meta:
        verbose_name = "Осмотр работника пищеблока"
        verbose_name_plural = "13. Журнал результатов осмотра работников пищеблока"
        ordering = ["-date", "employee"]

    def clean(self):
        if self.admitted and not all([self.skin_ok, self.throat_ok, self.gut_ok, self.family_ok]):
            raise ValidationError({"admitted": "При выявленных нарушениях работник не допускается к работе."})

    def __str__(self):
        return f"{self.employee} — {self.date:%d.%m.%Y}"


# ---------------------------------------------------------------- 14
AGE_GROUPS = [("NURSERY", "ясли (до 3 лет)"), ("GARDEN", "сад (3–7 лет)")]


class FoodNormSheet(BaseRecord):
    """Ведомость контроля за выполнением норм пищевой продукции (за период)."""
    period_start = models.DateField("Период с")
    period_end = models.DateField("Период по")
    age_group = models.CharField("Возрастная группа", max_length=10, choices=AGE_GROUPS)
    child_days = models.PositiveIntegerField("Детодни за период")
    responsible = models.CharField("Составил (медсестра / диетсестра)", max_length=150)
    notes = models.TextField("Выводы, меры по коррекции", blank=True)

    class Meta:
        verbose_name = "Ведомость выполнения норм питания"
        verbose_name_plural = "14. Ведомость контроля за выполнением норм пищевой продукции"
        ordering = ["-period_start"]

    def clean(self):
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError({"period_end": "Конец периода раньше начала."})

    def avg_completion(self):
        vals = [l.percent for l in self.lines.all() if l.percent is not None]
        return f"{sum(vals) / len(vals):.0f} %" if vals else "—"
    avg_completion.short_description = "Среднее выполнение"

    def __str__(self):
        return f"{self.get_age_group_display()}: {self.period_start:%d.%m}–{self.period_end:%d.%m.%Y}"


class FoodNormLine(models.Model):
    sheet = models.ForeignKey(FoodNormSheet, on_delete=models.CASCADE, related_name="lines", verbose_name="Ведомость")
    product = models.CharField("Продукт", max_length=150)
    norm_g = models.DecimalField("Норма на 1 ребёнка в день, г", max_digits=7, decimal_places=1)
    issued_total_g = models.DecimalField("Выдано всего за период, г", max_digits=12, decimal_places=1)

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"
        ordering = ["id"]

    @property
    def actual_g(self):
        if self.sheet_id and self.sheet.child_days:
            return round(self.issued_total_g / self.sheet.child_days, 1)
        return None

    @property
    def percent(self):
        a = self.actual_g
        if a is not None and self.norm_g:
            return round(a / self.norm_g * 100, 1)
        return None


# ---------------------------------------------------------------- 15
class MedicalCard(BaseRecord):
    """Индивидуальная медицинская карта воспитанника (ф. 026/у)."""
    child = models.OneToOneField(CHILD_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="Ребёнок")
    admission_date = models.DateField("Дата поступления в д/с", null=True, blank=True)
    address = models.CharField("Домашний адрес", max_length=255, blank=True)
    mother = models.CharField("Мать (ФИО, телефон)", max_length=255, blank=True)
    father = models.CharField("Отец (ФИО, телефон)", max_length=255, blank=True)
    polyclinic = models.CharField("Поликлиника, участок", max_length=150, blank=True)
    birth_history = models.TextField("Анамнез (беременность, роды, период новорождённости)", blank=True)
    past_diseases = models.TextField("Перенесённые заболевания", blank=True)
    allergy = models.TextField("Аллергологический анамнез", blank=True)
    admission_exam = models.TextField("Осмотр при поступлении", blank=True)
    notes = models.TextField("Примечание", blank=True)

    class Meta:
        verbose_name = "Медицинская карта воспитанника"
        verbose_name_plural = "15. Индивидуальные медицинские карты воспитанников"
        ordering = ["-updated_at"]

    def entries_count(self):
        return self.entries.count()
    entries_count.short_description = "Записей"

    def __str__(self):
        return f"Медкарта: {self.child}"


class MedicalCardEntry(models.Model):
    card = models.ForeignKey(MedicalCard, on_delete=models.CASCADE, related_name="entries", verbose_name="Карта")
    date = models.DateField("Дата")
    specialist = models.CharField("Специалист / вид осмотра", max_length=150)
    findings = models.TextField("Жалобы, объективно")
    diagnosis = models.CharField("Диагноз / заключение", max_length=255, blank=True)
    recommendations = models.TextField("Назначения, рекомендации", blank=True)

    class Meta:
        verbose_name = "Запись в медкарте"
        verbose_name_plural = "Записи в медкарте"
        ordering = ["date"]


# ---------------------------------------------------------------- 16
class DishQualityAssessment(BaseRecord):
    """Журнал органолептической оценки качества блюд и кулинарных изделий (Форма 3, бракераж готовой продукции)."""
    made_at = models.DateTimeField("Дата, время изготовления блюд и кулинарных изделий")
    dish = models.CharField("Наименование блюд и кулинарных изделий", max_length=255)
    organoleptic = models.TextField(
        "Органолептическая оценка, включая оценку степени готовности блюд и кулинарных изделий")
    permitted_at = models.TimeField(
        "Разрешение к реализации (время)", null=True, blank=True,
        help_text="Блюдо не допущено — оставьте пустым и впишите его в «Примечание».")
    executor = models.CharField("Ответственный исполнитель (Ф.И.О. (при его наличии), должность)",
                                max_length=255, blank=True)
    inspected_by = models.CharField("Ф.И.О. (при его наличии), лица проводившего бракераж", max_length=255)
    notes = models.TextField("Примечание", blank=True,
                             help_text="Наименования готовой продукции, не допущенной к реализации")

    class Meta:
        verbose_name = "Оценка блюда"
        verbose_name_plural = "16. Журнал органолептической оценки качества блюд и кулинарных изделий"
        ordering = ["-made_at"]

    def __str__(self):
        return f"{self.dish} ({timezone.localtime(self.made_at):%d.%m.%Y})"


# ---------------------------------------------------------------- 17
class VitaminCRecord(BaseRecord):
    """Журнал «С-витаминизации» (Форма 2)."""
    prepared_at = models.DateTimeField("Дата и час приготовления блюда")
    dish = models.CharField("Наименование блюда", max_length=255)
    total_mg = models.DecimalField("Общее количество добавленного витамина", max_digits=8, decimal_places=1,
                                   help_text="В миллиграммах")
    portion_mg = models.DecimalField("Содержание витамина «С» в одной порции", max_digits=6, decimal_places=1,
                                     help_text="В миллиграммах")
    responsible = models.CharField("Подпись ответственного лица", max_length=150)

    class Meta:
        verbose_name = "С-витаминизация"
        verbose_name_plural = "17. Журнал «С-витаминизации»"
        ordering = ["-prepared_at"]

    def total_label(self):
        return f"{fmt(self.total_mg)} мг"
    total_label.short_description = "Общее количество добавленного витамина"

    def portion_label(self):
        return f"{fmt(self.portion_mg)} мг"
    portion_label.short_description = "Содержание витамина «С» в одной порции"

    def __str__(self):
        return f"{self.dish} ({timezone.localtime(self.prepared_at):%d.%m.%Y})"


# ---------------------------------------------------------------- печать
class JournalPeriod(models.Model):
    """Строка «Начат … Окончен …» под заголовком печатного журнала: одна запись на журнал."""
    journal = models.CharField("Журнал", max_length=40, unique=True)  # slug из journals.py
    started = models.DateField("Начат", null=True, blank=True)
    finished = models.DateField("Окончен", null=True, blank=True)

    class Meta:
        verbose_name = "Даты ведения журнала"
        verbose_name_plural = "Даты ведения журналов"

    def clean(self):
        if self.started and self.finished and self.finished < self.started:
            raise ValidationError({"finished": "Журнал окончен раньше, чем начат."})

    def __str__(self):
        return self.journal
