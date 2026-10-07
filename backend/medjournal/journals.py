"""
Реестр журналов: одна запись = один журнал.
Отсюда строятся список, формы, фильтры и печатные формы, так что новый журнал
добавляется одной строкой в JOURNALS без новых view и шаблонов.
"""
from dataclasses import dataclass, field

from . import models as m


@dataclass
class Inline:
    model: type
    fields: list
    extra: int = 3
    title: str = ""
    computed: list = field(default_factory=list)  # вычисляемые колонки для печати


@dataclass
class Journal:
    number: str
    slug: str
    model: type
    columns: list                      # поля модели или методы/свойства для таблицы и печати
    date_field: str | None = None      # по нему фильтр «с … по …»
    child_field: str | None = "child"  # по нему фильтр «ребёнок»
    inlines: list = field(default_factory=list)
    section: str = "med"               # med — медкабинет, food — пищеблок
    landscape: bool = True
    # Утверждённая форма («Форма 1»): печать точно по ней — графы нумеруются с 1 без «№ п/п»,
    # подписи — в самих графах, внизу — примечание к форме; footnote_column помечается «*»
    form: str = ""
    footnote: str = ""
    footnote_column: str = ""

    @property
    def title(self):
        name = str(self.model._meta.verbose_name_plural)
        return name.split(". ", 1)[1] if ". " in name else name

    @property
    def perm_prefix(self):
        return f"{self.model._meta.app_label}.%s_{self.model._meta.model_name}"


JOURNALS = [
    Journal("1", "infectious", m.InfectiousDiseaseRecord,
            ["child", "date_onset", "date_detected", "diagnosis", "lab_confirmation", "date_isolated",
             "hospitalized_to", "notice_sent_at", "notice_received_by", "date_returned", "responsible"],
            date_field="date_detected"),
    Journal("2", "somatic", m.SomaticDiseaseRecord,
            ["child", "date_start", "diagnosis", "date_end", "days", "certificate", "notes"],
            date_field="date_start"),
    Journal("3", "contacts", m.InfectionContactRecord,
            ["child", "disease", "place", "contact_date", "quarantine_start", "quarantine_end",
             "vaccination_status", "measures", "outcome", "responsible"],
            date_field="contact_date"),
    Journal("4", "vaccinations", m.VaccinationRecord,
            ["child", "vaccine_label", "dose", "date", "drug_name", "series", "dose_ml", "route",
             "reaction_local", "reaction_general", "place", "medical_worker"],
            date_field="date"),
    Journal("4а", "exemptions", m.VaccinationExemption,
            ["child", "kind", "vaccine", "date_from", "date_to", "reason", "document"],
            date_field="date_from"),
    Journal("5", "mantoux", m.MantouxTest,
            ["child", "test_type", "purpose", "date_placed", "drug_series", "date_read", "papule_mm",
             "hyperemia_mm", "result", "previous_papule_mm", "bcg_scar_mm", "nurse"],
            date_field="date_placed"),
    Journal("6", "tb-risk", m.MantouxRiskGroupEntry,
            ["child", "risk_factor", "risk_details", "date_included", "planned_test_date",
             "test_result", "date_excluded", "notes"],
            date_field="date_included"),
    Journal("7", "phthisio", m.TuberculinPositiveReferral,
            ["child", "test_info", "reason", "referral_date", "phthisiatrician_visit", "xray_result",
             "conclusion", "dispensary_group", "admitted", "admitted_date"],
            date_field="referral_date"),
    Journal("8", "chemoprophylaxis", m.ChemoprophylaxisCourse,
            ["child", "indication", "drug", "dose", "prescribed_by", "date_start", "date_end_planned",
             "date_end_actual", "doses_given", "side_effects"],
            date_field="date_start",
            inlines=[Inline(m.ChemoprophylaxisDose, ["date", "taken", "reason_missed", "nurse"],
                            extra=7, title="Ежедневный контроль приёма")]),
    Journal("9", "helminths", m.HelminthExam,
            ["child", "exam_date", "method", "result_label", "treatment", "control_date", "control_result"],
            date_field="exam_date"),
    Journal("10", "health-passport", m.HealthPassport,
            ["child", "blood_group", "health_group", "pe_group", "allergies", "chronic",
             "dispensary", "last_measure"],
            inlines=[Inline(m.Anthropometry, ["date", "height_cm", "weight_kg", "physical_development",
                                              "vision", "posture"], title="Антропометрия и осмотры", computed=["bmi"])]),
    Journal("11", "risk-groups", m.RiskGroupEntry,
            ["child", "category", "diagnosis", "date_included", "date_excluded", "measures"],
            date_field="date_included"),
    Journal("12", "food-brakerage", m.PerishableFoodBrakerage,
            ["received_at", "product", "quantity", "organoleptic", "shelf_life_until", "used_days",
             "responsible", "notes"],
            date_field="received_at", child_field=None, section="food",
            form="Форма 1", footnote="* Указываются факты списания, возврата продуктов",
            footnote_column="notes"),
    Journal("13", "kitchen-staff", m.KitchenStaffInspection,
            ["date", "employee", "position", "skin_ok", "throat_ok", "gut_ok", "family_ok",
             "admitted", "measures", "inspected_by"],
            date_field="date", child_field=None, section="food"),
    Journal("14", "food-norms", m.FoodNormSheet,
            ["period_start", "period_end", "age_group", "child_days", "avg_completion", "responsible"],
            date_field="period_start", child_field=None, section="food",
            inlines=[Inline(m.FoodNormLine, ["product", "norm_g", "issued_total_g"], extra=10,
                            title="Продукты", computed=["actual_g", "percent"])]),
    Journal("15", "medical-cards", m.MedicalCard,
            ["child", "admission_date", "polyclinic", "address", "mother", "father", "entries_count"],
            inlines=[Inline(m.MedicalCardEntry, ["date", "specialist", "findings", "diagnosis",
                                                 "recommendations"], extra=2, title="Записи осмотров")]),
    Journal("16", "dish-quality", m.DishQualityAssessment,
            ["made_at", "dish", "organoleptic", "permitted_at", "executor", "inspected_by", "notes"],
            date_field="made_at", child_field=None, section="food",
            form="Форма 3",
            footnote="в графе 7 указываются наименования готовой продукции, не допущенных к реализации"),
    Journal("17", "vitamin-c", m.VitaminCRecord,
            ["prepared_at", "dish", "total_label", "portion_label", "responsible"],
            date_field="prepared_at", child_field=None, section="food", landscape=False, form="Форма 2"),
]

BY_SLUG = {j.slug: j for j in JOURNALS}

SECTIONS = [("med", "Медицинский кабинет"), ("food", "Пищеблок и питание")]
