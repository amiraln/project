from django.contrib import admin
from django.utils.html import format_html

from .models import FAQ, Appeal, Document, Group, News, NewsPhoto, Page, Person, SiteSettings, Vacancy

TEXT_HELP = "Можно писать обычным текстом: пустая строка — новый абзац."


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Название", {"fields": ["name_kk", "name_ru", "tagline_kk", "tagline_ru", "logo"]}),
        ("Контакты", {"fields": ["address_kk", "address_ru", "phone", "email", "map_embed_url"]}),
        ("Режим работы", {"fields": ["work_hours_kk", "work_hours_ru", "open_time", "close_time", "open_weekdays"]}),
        ("О детском саде", {"fields": ["founder_kk", "founder_ru", "history_kk", "history_ru"], "description": TEXT_HELP}),
        ("Приём граждан", {"fields": ["reception_kk", "reception_ru"]}),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title_ru", "slug", "updated_at"]
    readonly_fields = ["slug"]
    fields = ["slug", "title_kk", "title_ru", "body_kk", "body_ru"]

    def has_add_permission(self, request):
        return request.user.is_superuser  # разделы создаёт команда setup_site

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name_ru", "age_ru", "language", "order"]
    list_editable = ["order"]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["full_name", "position_ru", "kind", "is_published", "order"]
    list_filter = ["kind", "is_published"]
    list_editable = ["is_published", "order"]
    search_fields = ["last_name", "first_name", "middle_name", "position_ru"]
    fieldsets = [
        (None, {"fields": ["kind", ("last_name", "first_name", "middle_name"), "position_kk", "position_ru"]}),
        ("Фото", {"fields": ["photo", "show_photo"]}),
        ("Образование", {"fields": ["education_kk", "education_ru", "specialty_kk", "specialty_ru"]}),
        ("Сертификат о переподготовке по профилю", {"fields": ["retraining_date", "retraining_place_kk", "retraining_place_ru"]}),
        ("Квалификация", {"fields": ["qualification_kk", "qualification_ru", "qualification_year"]}),
        ("Стаж", {"fields": ["experience_years", "position_experience_years"]}),
        ("Контакты (для руководства)", {"fields": ["reception_kk", "reception_ru", "phone", "email"], "classes": ["collapse"]}),
        ("На сайте", {"fields": ["is_published", "order"]}),
    ]

    @admin.display(description="ФИО", ordering="last_name")
    def full_name(self, obj):
        return obj.full_name

    def get_changeform_initial_data(self, request):
        return {"kind": "teacher", **super().get_changeform_initial_data(request)}  # чаще всего вносят педагогов


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title_ru", "category", "language", "published_at", "is_published", "file_link"]
    list_filter = ["category", "is_published", "language"]
    search_fields = ["title_ru", "title_kk"]
    date_hierarchy = "published_at"

    @admin.display(description="Файл")
    def file_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">открыть</a>', obj.file.url) if obj.file else "—"


class NewsPhotoInline(admin.StackedInline):
    model = NewsPhoto
    extra = 1
    fields = ["image", "alt_kk", "alt_ru", "consent", "order"]


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ["title_ru", "kind", "published_at", "is_published"]
    list_filter = ["kind", "is_published"]
    search_fields = ["title_ru", "title_kk"]
    date_hierarchy = "published_at"
    inlines = [NewsPhotoInline]
    fieldsets = [
        (None, {"fields": ["kind", "is_published", "published_at", "event_date"]}),
        ("Текст", {"fields": ["title_kk", "title_ru", "summary_kk", "summary_ru", "body_kk", "body_ru"],
                   "description": TEXT_HELP}),
        ("Обложка", {"fields": ["cover", "cover_alt_kk", "cover_alt_ru", "cover_consent"]}),
    ]


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ["title_ru", "published_at", "is_active"]
    list_editable = ["is_active"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question_ru", "section", "is_published", "order"]
    list_filter = ["section"]
    list_editable = ["is_published", "order"]


@admin.register(Appeal)
class AppealAdmin(admin.ModelAdmin):
    list_display = ["subject", "full_name", "contact", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["full_name", "subject", "contact"]
    readonly_fields = ["full_name", "contact", "subject", "message", "lang", "consent", "created_at", "updated_at"]
    fields = readonly_fields[:6] + ["status", "staff_note", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False
