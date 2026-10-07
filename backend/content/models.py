from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible

from .images import process_image
from .sanitize import clean_html

LANG_CHOICES = [("kk", "Казахский"), ("ru", "Русский"), ("both", "Казахский и русский")]
CONSENT_LABEL = "Подтверждаю: на фото нет детей ИЛИ есть письменное согласие родителей (законных представителей)"
CONSENT_ERROR = "Нельзя публиковать фото без подтверждения согласия родителей (законных представителей)."
MAP_HOSTS = ("yandex.ru", "yandex.kz", "2gis.kz", "2gis.ru", "google.com", "www.google.com")


@deconstructible
class MaxSizeValidator:
    def __init__(self, mb):
        self.mb = mb

    def __call__(self, f):
        if f and f.size > self.mb * 1024 * 1024:
            raise ValidationError(f"Файл больше {self.mb} МБ.")

    def __eq__(self, other):
        return isinstance(other, MaxSizeValidator) and other.mb == self.mb


image_validators = [FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), MaxSizeValidator(10)]


class Ordered(models.Model):
    order = models.PositiveIntegerField("Порядок", default=0, help_text="Меньше — выше в списке")

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class SiteSettings(models.Model):
    """Одна запись: название, контакты, режим работы. Редактируется в админке."""

    name_kk = models.CharField("Название (қаз.)", max_length=255)
    name_ru = models.CharField("Название (рус.)", max_length=255)
    tagline_kk = models.CharField("Короткое описание (қаз.)", max_length=255, blank=True)
    tagline_ru = models.CharField("Короткое описание (рус.)", max_length=255, blank=True)
    logo = models.ImageField("Логотип", upload_to="site/", blank=True, validators=image_validators)
    address_kk = models.CharField("Адрес (қаз.)", max_length=255, blank=True)
    address_ru = models.CharField("Адрес (рус.)", max_length=255, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    email = models.EmailField("E-mail", blank=True)
    work_hours_kk = models.CharField("Режим работы, текстом (қаз.)", max_length=255, blank=True,
                                     help_text="Например: Дүйсенбі–Жұма, 07:30–19:00")
    work_hours_ru = models.CharField("Режим работы, текстом (рус.)", max_length=255, blank=True,
                                     help_text="Например: Пн–Пт, 07:30–19:00")
    open_time = models.TimeField("Открытие", null=True, blank=True)
    close_time = models.TimeField("Закрытие", null=True, blank=True)
    open_weekdays = models.CharField("Рабочие дни", max_length=7, default="12345",
                                     help_text="Цифры дней: 1 — понедельник … 7 — воскресенье")
    founder_kk = models.TextField("Учредитель (қаз.)", blank=True)
    founder_ru = models.TextField("Учредитель (рус.)", blank=True)
    history_kk = models.TextField("История (қаз.)", blank=True)
    history_ru = models.TextField("История (рус.)", blank=True)
    reception_kk = models.TextField("График приёма граждан (қаз.)", blank=True)
    reception_ru = models.TextField("График приёма граждан (рус.)", blank=True)
    map_embed_url = models.URLField("Ссылка на карту для встраивания", blank=True,
                                    help_text="Ссылка «для встраивания» из Яндекс.Карт, 2ГИС или Google Maps")
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"

    def clean(self):
        if self.map_embed_url:
            host = urlparse(self.map_embed_url).hostname or ""
            if not any(host == h or host.endswith("." + h) for h in MAP_HOSTS):
                raise ValidationError({"map_embed_url": "Разрешены только карты Яндекса, 2ГИС или Google."})
        if self.open_weekdays and not set(self.open_weekdays) <= set("1234567"):
            raise ValidationError({"open_weekdays": "Только цифры от 1 до 7."})

    def save(self, *args, **kwargs):
        self.pk = 1
        for f in ("founder_kk", "founder_ru", "history_kk", "history_ru", "reception_kk", "reception_ru"):
            setattr(self, f, clean_html(getattr(self, f)))
        process_image(self.logo)
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"name_kk": "Ботақаным", "name_ru": "Ботаканым"})
        return obj


class Page(models.Model):
    """Текстовая часть раздела: «О детском саде», «Питание», «Родителям» и т.д."""

    slug = models.SlugField("Код раздела", unique=True)
    title_kk = models.CharField("Заголовок (қаз.)", max_length=255)
    title_ru = models.CharField("Заголовок (рус.)", max_length=255)
    body_kk = models.TextField("Текст (қаз.)", blank=True)
    body_ru = models.TextField("Текст (рус.)", blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Текст раздела"
        verbose_name_plural = "Тексты разделов"
        ordering = ["slug"]

    def __str__(self):
        return self.title_ru

    def save(self, *args, **kwargs):
        self.body_kk = clean_html(self.body_kk)
        self.body_ru = clean_html(self.body_ru)
        super().save(*args, **kwargs)


class Group(Ordered):
    name_kk = models.CharField("Название (қаз.)", max_length=120)
    name_ru = models.CharField("Название (рус.)", max_length=120)
    age_kk = models.CharField("Возраст (қаз.)", max_length=60, help_text="Например: 3–4 жас")
    age_ru = models.CharField("Возраст (рус.)", max_length=60, help_text="Например: 3–4 года")
    language = models.CharField("Язык обучения", max_length=4, choices=LANG_CHOICES, default="kk")

    class Meta(Ordered.Meta):
        verbose_name = "Группа"
        verbose_name_plural = "Группы"

    def __str__(self):
        return self.name_ru


class Person(Ordered):
    KIND_CHOICES = [("leader", "Руководство"), ("teacher", "Педагог / специалист")]

    kind = models.CharField("Раздел", max_length=10, choices=KIND_CHOICES)
    full_name = models.CharField("ФИО", max_length=255)
    position_kk = models.CharField("Должность (қаз.)", max_length=255)
    position_ru = models.CharField("Должность (рус.)", max_length=255)
    education_kk = models.CharField("Образование (қаз.)", max_length=500, blank=True)
    education_ru = models.CharField("Образование (рус.)", max_length=500, blank=True)
    qualification_kk = models.CharField("Квалификация / категория (қаз.)", max_length=255, blank=True)
    qualification_ru = models.CharField("Квалификация / категория (рус.)", max_length=255, blank=True)
    experience_years = models.PositiveSmallIntegerField("Педагогический стаж, лет", null=True, blank=True)
    reception_kk = models.CharField("Часы приёма (қаз.)", max_length=255, blank=True)
    reception_ru = models.CharField("Часы приёма (рус.)", max_length=255, blank=True)
    phone = models.CharField("Рабочий телефон", max_length=50, blank=True)
    email = models.EmailField("Рабочий e-mail", blank=True)
    photo = models.ImageField("Фото", upload_to="people/", blank=True, validators=image_validators)
    show_photo = models.BooleanField("Показывать фото", default=False,
                                     help_text="Только если сотрудник дал согласие на публикацию фото")
    is_published = models.BooleanField("Показывать на сайте", default=True)

    class Meta(Ordered.Meta):
        verbose_name = "Сотрудник на сайте"
        verbose_name_plural = "Сотрудники на сайте"

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        process_image(self.photo)
        super().save(*args, **kwargs)


class Document(models.Model):
    CATEGORY_CHOICES = [
        ("charter", "Устав"),
        ("gos", "ГОСО"),
        ("rules", "Типовые правила"),
        ("program", "Образовательные программы"),
        ("schedule", "Режим дня и расписание"),
        ("admission", "Приём в детский сад"),
        ("contract", "Договоры и заявления"),
        ("payment", "Оплата"),
        ("menu", "Меню"),
        ("nutrition", "Организация питания"),
        ("report", "Отчёты"),
        ("budget", "Бюджет"),
        ("procurement", "Закупки"),
        ("other", "Прочее"),
    ]

    title_kk = models.CharField("Название (қаз.)", max_length=255)
    title_ru = models.CharField("Название (рус.)", max_length=255)
    category = models.CharField("Категория", max_length=20, choices=CATEGORY_CHOICES)
    language = models.CharField("Язык документа", max_length=4, choices=LANG_CHOICES, default="both")
    file = models.FileField(
        "Файл", upload_to="documents/%Y/%m/",
        validators=[FileExtensionValidator(["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png"]), MaxSizeValidator(20)],
    )
    published_at = models.DateField("Дата публикации", default=timezone.localdate)
    is_published = models.BooleanField("Опубликован", default=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ["category", "-published_at", "-id"]

    def __str__(self):
        return self.title_ru


class News(models.Model):
    KIND_CHOICES = [("news", "Новость"), ("announcement", "Объявление"), ("event", "Мероприятие")]

    kind = models.CharField("Тип", max_length=15, choices=KIND_CHOICES, default="news")
    title_kk = models.CharField("Заголовок (қаз.)", max_length=255)
    title_ru = models.CharField("Заголовок (рус.)", max_length=255)
    summary_kk = models.CharField("Кратко (қаз.)", max_length=300, blank=True)
    summary_ru = models.CharField("Кратко (рус.)", max_length=300, blank=True)
    body_kk = models.TextField("Текст (қаз.)", blank=True)
    body_ru = models.TextField("Текст (рус.)", blank=True)
    cover = models.ImageField("Обложка", upload_to="news/%Y/%m/", blank=True, validators=image_validators)
    cover_alt_kk = models.CharField("Описание обложки для незрячих (қаз.)", max_length=255, blank=True)
    cover_alt_ru = models.CharField("Описание обложки для незрячих (рус.)", max_length=255, blank=True)
    cover_consent = models.BooleanField(CONSENT_LABEL, default=False)
    event_date = models.DateTimeField("Дата мероприятия", null=True, blank=True)
    published_at = models.DateTimeField("Дата публикации", default=timezone.now)
    is_published = models.BooleanField("Опубликовано", default=True)

    class Meta:
        verbose_name = "Новость / объявление"
        verbose_name_plural = "Новости и объявления"
        ordering = ["-published_at", "-id"]

    def __str__(self):
        return self.title_ru

    def clean(self):
        errors = {}
        if self.cover and not self.cover_consent:
            errors["cover_consent"] = CONSENT_ERROR
        if self.cover and not (self.cover_alt_kk and self.cover_alt_ru):
            errors["cover_alt_ru"] = "Опишите фото на обоих языках — это нужно для людей с нарушением зрения."
        if self.kind == "event" and not self.event_date:
            errors["event_date"] = "Укажите дату мероприятия."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.body_kk = clean_html(self.body_kk)
        self.body_ru = clean_html(self.body_ru)
        process_image(self.cover)
        super().save(*args, **kwargs)


class NewsPhoto(Ordered):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField("Фото", upload_to="news/%Y/%m/", validators=image_validators)
    alt_kk = models.CharField("Описание для незрячих (қаз.)", max_length=255)
    alt_ru = models.CharField("Описание для незрячих (рус.)", max_length=255)
    consent = models.BooleanField(CONSENT_LABEL, default=False)

    class Meta(Ordered.Meta):
        verbose_name = "Фото"
        verbose_name_plural = "Фотографии"

    def clean(self):
        if not self.consent:
            raise ValidationError({"consent": CONSENT_ERROR})

    def save(self, *args, **kwargs):
        process_image(self.image)
        super().save(*args, **kwargs)


class Vacancy(Ordered):
    title_kk = models.CharField("Должность (қаз.)", max_length=255)
    title_ru = models.CharField("Должность (рус.)", max_length=255)
    requirements_kk = models.TextField("Требования (қаз.)")
    requirements_ru = models.TextField("Требования (рус.)")
    conditions_kk = models.TextField("Условия (қаз.)", blank=True)
    conditions_ru = models.TextField("Условия (рус.)", blank=True)
    contact = models.CharField("Контакт для связи", max_length=255)
    is_active = models.BooleanField("Актуальна", default=True)
    published_at = models.DateField("Дата публикации", default=timezone.localdate)

    class Meta(Ordered.Meta):
        verbose_name = "Вакансия"
        verbose_name_plural = "Вакансии"

    def __str__(self):
        return self.title_ru

    def save(self, *args, **kwargs):
        for f in ("requirements_kk", "requirements_ru", "conditions_kk", "conditions_ru"):
            setattr(self, f, clean_html(getattr(self, f)))
        super().save(*args, **kwargs)


class FAQ(Ordered):
    SECTION_CHOICES = [("parents", "Родителям"), ("appeals", "Обращения")]

    section = models.CharField("Раздел", max_length=10, choices=SECTION_CHOICES)
    question_kk = models.CharField("Вопрос (қаз.)", max_length=500)
    question_ru = models.CharField("Вопрос (рус.)", max_length=500)
    answer_kk = models.TextField("Ответ (қаз.)")
    answer_ru = models.TextField("Ответ (рус.)")
    is_published = models.BooleanField("Показывать", default=True)

    class Meta(Ordered.Meta):
        verbose_name = "Вопрос-ответ"
        verbose_name_plural = "Частые вопросы"

    def __str__(self):
        return self.question_ru

    def save(self, *args, **kwargs):
        self.answer_kk = clean_html(self.answer_kk)
        self.answer_ru = clean_html(self.answer_ru)
        super().save(*args, **kwargs)


class Appeal(models.Model):
    """Обращение с сайта. Содержит персональные данные — видят только сотрудники с правом просмотра."""

    STATUS_CHOICES = [("new", "Новое"), ("in_progress", "В работе"), ("done", "Обработано")]

    full_name = models.CharField("ФИО", max_length=255)
    contact = models.CharField("Телефон или e-mail", max_length=255)
    subject = models.CharField("Тема", max_length=255)
    message = models.TextField("Текст", max_length=5000)
    lang = models.CharField("Язык", max_length=2, default="ru")
    consent = models.BooleanField("Согласие на обработку персональных данных")
    status = models.CharField("Статус", max_length=15, choices=STATUS_CHOICES, default="new")
    staff_note = models.TextField("Заметка сотрудника", blank=True)
    created_at = models.DateTimeField("Получено", auto_now_add=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        verbose_name = "Обращение"
        verbose_name_plural = "Обращения"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.full_name}"
