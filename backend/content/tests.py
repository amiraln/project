from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from .models import Person


def teacher(**fields):
    return Person(**{"kind": "teacher", "last_name": "Иванова", "first_name": "Айгуль", "middle_name": "Ерлан қызы",
                     "position_kk": "Тәрбиеші", "position_ru": "Воспитатель", **fields})


class TeacherCardTests(TestCase):
    """Карточка педагога: ФИО по частям, образование, переподготовка, квалификация, стаж."""

    def test_card_is_served_to_the_site(self):
        teacher(
            education_ru="КазНПУ им. Абая, 2012", specialty_ru="Дошкольное воспитание и обучение",
            retraining_date=date(2023, 5, 12), retraining_place_ru="НЦПК «Өрлеу»",
            qualification_ru="педагог-модератор", qualification_year=2021,
            experience_years=12, position_experience_years=8, photo="people/a.jpg",
        ).save()
        teacher(last_name="Скрытая", is_published=False).save()

        [card] = self.client.get("/api/people/?kind=teacher").json()
        self.assertEqual(card["full_name"], "Иванова Айгуль Ерлан қызы")
        expected = {
            "last_name": "Иванова", "first_name": "Айгуль", "middle_name": "Ерлан қызы",
            "education_ru": "КазНПУ им. Абая, 2012", "specialty_ru": "Дошкольное воспитание и обучение",
            "retraining_date": "2023-05-12", "retraining_place_ru": "НЦПК «Өрлеу»",
            "qualification_ru": "педагог-модератор", "qualification_year": 2021,
            "experience_years": 12, "position_experience_years": 8,
        }
        self.assertEqual({key: card[key] for key in expected}, expected)
        self.assertIsNone(card["photo"])  # фото — только с отметкой о согласии

    def test_card_checks(self):
        teacher(qualification_ru="педагог-эксперт", qualification_year=2020, experience_years=5,
                position_experience_years=5, retraining_date=timezone.localdate()).full_clean()

        next_year = timezone.localdate().year + 1
        bad = {
            "qualification_year": [{"qualification_ru": "педагог", "qualification_year": next_year},
                                   {"qualification_year": 2020},  # год без названия
                                   {"qualification_ru": "педагог", "qualification_year": 1900}],
            "retraining_date": [{"retraining_date": timezone.localdate() + timedelta(days=1)}],
            "position_experience_years": [{"experience_years": 3, "position_experience_years": 4}],
            "first_name": [{"first_name": ""}],
        }
        for field, cases in bad.items():
            for fields in cases:
                with self.assertRaises(ValidationError, msg=fields) as caught:
                    teacher(**fields).full_clean()
                self.assertIn(field, caught.exception.message_dict, fields)


class SplitFullNameMigrationTests(TransactionTestCase):
    """Прежнее поле «ФИО» раскладывается на фамилию, имя и отчество."""

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_full_name_is_split(self):
        apps = self.migrate([("content", "0001_initial")])
        Person_ = apps.get_model("content", "Person")
        for name in ("Иванова Айгуль Сапаровна", "Серікова Дана Ерлан қызы", "Ахметов Арман", "Мадина"):
            Person_.objects.create(kind="teacher", full_name=name, position_kk="Тәрбиеші", position_ru="Воспитатель")

        apps = self.migrate([("content", "0002_person_card")])
        names = list(apps.get_model("content", "Person").objects.order_by("id")
                     .values_list("last_name", "first_name", "middle_name"))
        self.assertEqual(names, [("Иванова", "Айгуль", "Сапаровна"), ("Серікова", "Дана", "Ерлан қызы"),
                                 ("Ахметов", "Арман", ""), ("Мадина", "", "")])
