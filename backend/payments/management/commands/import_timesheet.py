"""python manage.py import_timesheet /home/ubuntu/timesheet_project/db.sqlite3

Переносит данные старой системы табеля. Только в пустой раздел, старую базу не меняет.
"""
import sqlite3
from datetime import timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils.dateparse import parse_datetime

from payments.models import ChangeLog, ChildRecord, Guardian, PaymentImport, PaymentInfo, sync_children

# Порядок важен: сначала дети, на них ссылаются оплаты и квитанции
MODELS = [ChildRecord, PaymentInfo, ChangeLog, PaymentImport, Guardian]
DATETIME_FIELDS = {"updated_at", "created_at"}


def to_datetime(value):
    if value in (None, ""):
        return None
    dt = parse_datetime(str(value))
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)  # Django хранит время в SQLite в UTC
    return dt


class Command(BaseCommand):
    help = "Перенести данные из старой базы табеля (timesheet_project/db.sqlite3)"

    def add_arguments(self, parser):
        parser.add_argument("path", help="путь к db.sqlite3 старой системы")

    def handle(self, *args, path, **options):
        busy = [m._meta.verbose_name_plural for m in MODELS if m.objects.exists()]
        if busy:
            raise CommandError(f"В разделе оплат уже есть данные ({', '.join(busy)}). Импорт возможен только в пустой раздел.")
        try:
            src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error as e:
            raise CommandError(f"Не удалось открыть {path}: {e}")
        src.row_factory = sqlite3.Row
        tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "timesheet_app_childrecord" not in tables:
            raise CommandError(f"{path} — не база табеля (нет таблицы timesheet_app_childrecord)")

        # Автор изменения в журнале: ищем пользователя сайта с тем же логином
        old_users = dict(src.execute("SELECT id, username FROM auth_user")) if "auth_user" in tables else {}
        site_users = {u.username: u.pk for u in get_user_model().objects.filter(username__in=old_users.values())}

        with transaction.atomic():
            for model in MODELS:
                table = f"timesheet_app_{model._meta.model_name}"
                if table not in tables:
                    self.stdout.write(f"  {model._meta.verbose_name_plural}: нет в старой базе, пропущено")
                    continue
                rows = [dict(r) for r in src.execute(f'SELECT * FROM "{table}"')]
                objs, stamps = [], []
                for row in rows:
                    if model is ChangeLog:
                        row["user_id"] = site_users.get(old_users.get(row.get("user_id")))
                    values = {}
                    for field in model._meta.concrete_fields:
                        if field.attname not in row:
                            continue
                        value = row[field.attname]
                        values[field.attname] = to_datetime(value) if field.name in DATETIME_FIELDS else value
                    objs.append(model(**values))
                    stamps.append({k: v for k, v in values.items() if k in DATETIME_FIELDS})
                model.objects.bulk_create(objs, batch_size=500)
                # auto_now / auto_now_add перезаписали время при вставке — возвращаем исходное
                for obj, stamp in zip(objs, stamps):
                    for k, v in stamp.items():
                        setattr(obj, k, v)
                stamp_fields = [f for f in DATETIME_FIELDS if any(f in s for s in stamps)]
                if stamp_fields:
                    model.objects.bulk_update(objs, stamp_fields, batch_size=500)
                self.stdout.write(f"  {model._meta.verbose_name_plural}: {len(objs)}")

            # id перенесены как есть — в PostgreSQL надо сдвинуть счётчики
            with connection.cursor() as cursor:
                for sql in connection.ops.sequence_reset_sql(no_style(), MODELS):
                    cursor.execute(sql)

            sync_children()  # воспитанники для медицинских журналов

        src.close()
        self.stdout.write(self.style.SUCCESS("Готово. Данные табеля перенесены."))
