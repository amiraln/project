"""Создаёт настройки, разделы сайта и группу «Редакторы сайта».

Запуск: python manage.py setup_site   (безопасно запускать повторно)
"""
from django.contrib.auth.models import Group as AuthGroup
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand

from content.models import Page, SiteSettings

PAGES = {
    "about": ("Балабақша туралы", "О детском саде"),
    "leadership": ("Басшылық", "Руководство"),
    "teachers": ("Педагогтер", "Педагоги"),
    "documents": ("Құжаттар", "Документы"),
    "education": ("Тәрбие және оқыту", "Воспитание и обучение"),
    "parents": ("Ата-аналарға", "Родителям"),
    "nutrition": ("Тамақтану", "Питание"),
    "finance": ("Қаржы", "Финансы"),
    "vacancies": ("Бос орындар", "Вакансии"),
    "appeals": ("Өтініштер", "Обращения"),
}

EDITOR_MODELS = ["page", "group", "person", "document", "news", "newsphoto", "vacancy", "faq"]


class Command(BaseCommand):
    help = "Первичная настройка сайта"

    def handle(self, *args, **options):
        SiteSettings.load()
        for slug, (kk, ru) in PAGES.items():
            Page.objects.get_or_create(slug=slug, defaults={"title_kk": kk, "title_ru": ru})

        editors, _ = AuthGroup.objects.get_or_create(name="Редакторы сайта")
        perms = list(Permission.objects.filter(content_type__app_label="content", content_type__model__in=EDITOR_MODELS))
        perms += list(Permission.objects.filter(
            content_type__app_label="content",
            codename__in=["view_appeal", "change_appeal", "view_sitesettings", "change_sitesettings"],
        ))
        editors.permissions.set(perms)
        self.stdout.write(self.style.SUCCESS(
            "Готово. Сотрудникам поставьте «Статус персонала» и добавьте в группу «Редакторы сайта»."
        ))
