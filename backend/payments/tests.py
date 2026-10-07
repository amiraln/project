import json
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import ChangeLog, Child, ChildRecord, Guardian
from .views import eorda_date

EORDA = "https://int.indigo.nursultan.e-orda.kz"
PAGES = ["/payments/", "/payments/debts/", "/payments/parents/", "/payments/changelog/", "/payments/child/1/", "/payments/print/2/"]


class AccessTests(TestCase):
    """Раздел оплат открывается только администратору."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("boss", password="pass-for-tests-1")
        cls.editor = User.objects.create_user("editor", password="pass-for-tests-2", is_staff=True)
        ChildRecord.objects.create(month="2026-06", p_id=1, iin="190101500001", fio="Тестов Тест", group_id=2, group_name="Ромашка")

    def test_guest_is_sent_to_staff_login(self):
        for url in PAGES:
            r = self.client.get(url)
            self.assertRedirects(r, f"/staff/login?next={url}", fetch_redirect_response=False)

    def test_staff_without_admin_rights_is_refused(self):
        self.client.force_login(self.editor)
        for url in PAGES:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_inactive_or_non_staff_superuser_is_refused(self):
        inactive = User.objects.create_superuser("gone", password="pass-for-tests-3", is_active=False)
        self.client.force_login(inactive)  # неактивного Django сразу разлогинивает
        self.assertEqual(self.client.get("/payments/").status_code, 302)
        not_staff = User.objects.create_user("nostaff", password="pass-for-tests-3", is_superuser=True)
        self.client.force_login(not_staff)
        self.assertEqual(self.client.get("/payments/").status_code, 403)

    def test_admin_sees_every_page(self):
        self.client.force_login(self.admin)
        for url in PAGES:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_page_apis_refuse_non_admins_without_redirect(self):
        self.client.force_login(self.editor)
        r = self.client.post("/payments/api/payment/", {"pId": 1, "last_payment": 5}, content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_admin_marks_absence_and_it_is_logged(self):
        self.client.force_login(self.admin)
        r = self.client.post("/payments/api/absence/", {"pId": 1, "day": 3, "status": "БР", "month": "2026-06"},
                             content_type="application/json")
        self.assertEqual(r.json()["type"], "absent_reason")
        self.assertEqual(r.json()["totals"]["absences"], [{"code": "БР", "label": "Болезнь ребёнка", "days": [3]}])
        self.assertEqual(ChangeLog.objects.get().user, self.admin)

    def test_me_reports_payments_access(self):
        self.client.force_login(self.admin)
        self.assertTrue(self.client.get("/api/auth/me/").json()["can_access_payments"])
        self.client.force_login(self.editor)
        self.assertFalse(self.client.get("/api/auth/me/").json()["can_access_payments"])

    def test_logout_requires_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/payments/logout/").status_code, 405)
        self.client.post("/payments/logout/")
        self.assertEqual(self.client.get("/payments/").status_code, 302)


class TimesheetApiTests(TestCase):
    """Правка табеля и оплаты из карточки ребёнка."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("boss", password="pass-for-tests-1")
        ChildRecord.objects.create(month="2026-06", p_id=1, iin="190101500001", fio="Тестов Тест", group_id=2, group_name="Ромашка")

    def setUp(self):
        self.client.force_login(self.admin)

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_unknown_status_or_day_does_not_touch_the_timesheet(self):
        for body in ({"status": "XX", "day": 3}, {"status": "БР", "day": 31}, {"status": "БР", "day": "x"}):
            r = self.post("/payments/api/absence/", {"pId": 1, "month": "2026-06", **body})
            self.assertEqual(r.status_code, 400, body)  # в июне 30 дней
        self.assertEqual(ChildRecord.objects.get().days_json, "{}")
        self.assertFalse(ChangeLog.objects.exists())

    def test_vacation_reduces_amount_due_and_payment_is_validated(self):
        for day in (1, 2):
            self.post("/payments/api/absence/", {"pId": 1, "month": "2026-06", "day": day, "status": "ОР"})
        r = self.post("/payments/api/payment/", {"pId": 1, "month": "2026-06", "monthly": "44 000", "last_payment": "40000"})
        self.assertEqual(r.json()["totals"]["total"], 40000)  # 44 000 − 2 дня × 44 000 / 22
        self.assertEqual(r.json()["totals"]["overpay"], 0)
        self.assertEqual(self.post("/payments/api/payment/", {"pId": 1, "month": "2026-06", "last_payment": "-5"}).status_code, 400)
        self.assertEqual(self.post("/payments/api/payment/", {"pId": 9, "month": "2026-06", "monthly": 1}).status_code, 404)

    def test_clear_requires_a_month(self):
        self.assertEqual(self.post("/payments/api/clear/", {}).status_code, 400)
        self.assertTrue(ChildRecord.objects.exists())

    def test_calendar_matches_the_month(self):
        page = self.client.get("/payments/child/1/?month=2026-06")
        self.assertEqual(len(page.context["child"]["days"]), 30)
        self.assertEqual(len(page.context["blank_days"]), 0)  # 1 июня 2026 — понедельник
        page = self.client.get("/payments/child/1/?month=2026-02")
        self.assertIsNone(page.context.get("child"))  # за февраль табеля нет

    def test_debts_and_parents_summarise_all_months(self):
        ChildRecord.objects.create(month="2026-07", p_id=1, iin="190101500001", fio="Тестов Тест", group_id=2, group_name="Ромашка")
        Guardian.objects.create(child_pid=100, child_iin="190101500001", fio="Тестова Мама", phone="+77010000001")
        debts = self.client.get("/payments/debts/")
        self.assertEqual(debts.context["total_owed"], 102000)
        parents = self.client.get("/payments/parents/")
        self.assertContains(parents, "Тестова Мама")
        self.assertContains(parents, 'href="tel:+77010000001"')


class BookmarkletTests(TestCase):
    """Данные из e-orda сохраняются только под сессией администратора."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("boss", password="pass-for-tests-1")
        cls.editor = User.objects.create_user("editor", password="pass-for-tests-2", is_staff=True)

    def setUp(self):
        self.client.force_login(self.admin)

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def rows(self):
        return {"month": "2026-06", "result": [{"pId": 5, "i": "190101500005", "fio": "Новый", "gId": 3, "gn": "Солнышко"}]}

    def test_bridge_window_is_admin_only_and_keeps_opener(self):
        r = self.client.get("/payments/eorda/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cross-Origin-Opener-Policy"], "unsafe-none")
        self.assertContains(r, EORDA)
        self.assertContains(r, "/payments/api/receive/")

        self.client.force_login(self.editor)
        r = self.client.get("/payments/eorda/")
        self.assertEqual((r.status_code, r["Cross-Origin-Opener-Policy"]), (403, "unsafe-none"))

        self.client.logout()
        r = self.client.get("/payments/eorda/")
        self.assertEqual((r.status_code, r["Cross-Origin-Opener-Policy"]), (302, "unsafe-none"))

    def test_bridge_gives_parents_bookmarklet_children_and_groups_from_timesheet(self):
        Child.objects.create(p_id=651736, fio="Посещает")
        Child.objects.create(p_id=500, fio="Выбыл", is_active=False)
        for month, gid in (("2026-08", 111), ("2026-09", 65642), ("2026-09", 67318)):
            ChildRecord.objects.create(month=month, p_id=gid, fio="Ребёнок", group_id=gid)
        r = self.client.get("/payments/eorda/")
        # группы — из последнего загруженного месяца
        self.assertEqual(r.context["timesheet"], {"children": [651736], "groups": [65642, 67318]})

    def test_saving_requires_admin_session_and_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        body = json.dumps(self.rows())
        r = csrf_client.post("/payments/api/receive/", body, content_type="application/json")
        self.assertEqual(r.status_code, 403)  # без CSRF-токена

        page = csrf_client.get("/payments/eorda/")
        token = str(page.context["csrf_token"])
        r = csrf_client.post("/payments/api/receive/", body, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ChildRecord.objects.filter(p_id=5, month="2026-06").exists())

        self.client.force_login(self.editor)
        self.assertEqual(self.post("/payments/api/guardians/", {"pupils": []}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.post("/payments/api/receive/", self.rows()).status_code, 403)

    def test_guardians_are_linked_by_iin_and_replaced(self):
        # в табеле у ребёнка другой id, чем в списке группы e-orda
        ChildRecord.objects.create(month="2026-09", p_id=77, iin="210101500001", fio="ТЕСТОВ ТЕСТ", group_id=5)
        guardian = {"iin": "900101400001", "fio": "ТЕСТОВА АЙГУЛЬ САПАРОВНА",
                    "phone": "+77010000001, +77020000002", "email": "parent@example.kz"}
        body = {"pupils": [{"p_id": 480001, "iin": "210101500001", "fio": "ТЕСТОВ ТЕСТ", "guardians": [guardian]}]}
        self.assertEqual(self.post("/payments/api/guardians/", body).json()["guardians"], 1)

        page = self.client.get("/payments/child/77/?month=2026-09").content.decode()
        for text in ("ТЕСТОВА АЙГУЛЬ САПАРОВНА", 'href="tel:+77010000001"', 'href="tel:+77020000002"',
                     "parent@example.kz", "900101400001"):
            self.assertIn(text, page)

        self.post("/payments/api/guardians/", body)
        self.assertEqual(Guardian.objects.count(), 1)

    def test_parents_bookmarklet_brings_gender_address_and_contract(self):
        ChildRecord.objects.create(month="2026-09", p_id=651736, iin="210101500001", fio="ТЕСТОВ ТЕСТ", group_id=5)
        Child.objects.create(p_id=651736, iin="210101500001", fio="ТЕСТОВ ТЕСТ")
        pupil = {
            "p_id": 651736, "iin": "210101500001", "fio": "ТЕСТОВ ТЕСТ", "address": "г. Астана, ул. Кенесары, 1",
            "guardians": [{"gender": 1, "fio": "ТЕСТОВ ОТЕЦ", "phone": "+77010000001"},
                          {"gender": "2", "fio": "ТЕСТОВА МАТЬ", "phone": "+77020000002"},
                          {"gender": 9, "fio": "ТЕСТОВА БАБУШКА"}],
            # действующий договор — последний подписанный
            "contracts": [{"number": "Д-15", "date": "/Date(1693526400000)/"},
                          {"number": "Д-2024-7", "date": "2024-09-02T11:00:00"}],
        }
        self.post("/payments/api/guardians/", {"pupils": [pupil]})
        genders = dict(Guardian.objects.values_list("fio", "gender"))
        self.assertEqual(genders, {"ТЕСТОВ ОТЕЦ": Guardian.FATHER, "ТЕСТОВА МАТЬ": Guardian.MOTHER, "ТЕСТОВА БАБУШКА": None})
        child = Child.objects.get()
        self.assertEqual((child.address, child.contract_number, child.contract_date),
                         ("г. Астана, ул. Кенесары, 1", "Д-2024-7", date(2024, 9, 2)))

        page = self.client.get("/payments/child/651736/?month=2026-09").content.decode()
        for text in ("№ Д-2024-7 от 02.09.2024", "г. Астана, ул. Кенесары, 1", ">Отец<", ">Мать<"):
            self.assertIn(text, page)

        # договоры не открылись, адреса в карточке нет — прежние данные остаются
        del pupil["contracts"], pupil["address"]
        self.post("/payments/api/guardians/", {"pupils": [pupil]})
        child.refresh_from_db()
        self.assertEqual((child.address, child.contract_number), ("г. Астана, ул. Кенесары, 1", "Д-2024-7"))
        # договоров у ребёнка нет — договор очищается
        self.post("/payments/api/guardians/", {"pupils": [{**pupil, "contracts": []}]})
        child.refresh_from_db()
        self.assertEqual((child.contract_number, child.contract_date), ("", None))

    def test_eorda_dates(self):
        cases = {
            "/Date(1693526400000)/": date(2023, 9, 1),  # полночь UTC — 05:00 в Астане
            "/Date(1693508400000+0500)/": date(2023, 9, 1),
            "1693526400000": date(2023, 9, 1),
            "2023-09-01T10:20:30.123": date(2023, 9, 1),
            "2023-08-31T20:00:00Z": date(2023, 9, 1),
            "2023-09-01": date(2023, 9, 1),
            "01.09.2023 10:20": date(2023, 9, 1),
            "": None, None: None, "не дата": None, "2023-02-30": None,
        }
        for value, expected in cases.items():
            self.assertEqual(eorda_date(value), expected, value)

    def test_receive_rejects_malformed_month(self):
        rows = self.rows()
        rows["month"] = "2026-9"
        r = self.post("/payments/api/receive/", rows)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ChildRecord.objects.exists())

    def test_page_ships_bookmarklets(self):
        page = self.client.get("/payments/").content.decode()
        self.assertIn("async function eordaBookmarklet", page)  # код закладок встроен в страницу
        self.assertIn('bookmarklet(SITE, "parents")', page)
        self.assertIn("/ru/Contract/GetContractGridForPupil", page)
        self.assertIn("/payments/eorda/", page)


class MedjournalIntegrationTests(TestCase):
    """Медицинская документация — страница раздела табеля, дети берутся из табеля."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("boss", password="pass-for-tests-1")
        cls.editor = User.objects.create_user("editor", password="pass-for-tests-2", is_staff=True)

    def receive(self, month, fio, group):
        body = {"month": month, "result": [{"pId": 5, "i": "190101500005", "fio": fio, "gId": 3, "gn": group}]}
        return self.client.post("/payments/api/receive/", json.dumps(body), content_type="application/json")

    def test_children_come_from_latest_timesheet_month(self):
        self.client.force_login(self.admin)
        self.receive("2026-09", "Новый Ребёнок", "Солнышко")
        child = Child.objects.get(p_id=5)
        self.assertEqual((child.fio, child.group_name, child.last_month), ("Новый Ребёнок", "Солнышко", "2026-09"))

        child.is_active = False
        child.save()
        self.receive("2026-08", "Старое ФИО", "Ясельная")  # старый месяц не затирает свежие данные
        self.receive("2026-10", "Новый Ребёнок", "Старшая")
        child.refresh_from_db()
        self.assertEqual((child.fio, child.group_name, child.last_month), ("Новый Ребёнок", "Старшая", "2026-10"))
        self.assertFalse(child.is_active)  # отметку о выбытии ставит человек
        self.assertEqual(Child.objects.count(), 1)

        # очистка месяца в табеле не трогает воспитанников и их медзаписи
        self.client.post("/payments/api/clear/", json.dumps({"month": "2026-09"}), content_type="application/json")
        self.assertFalse(ChildRecord.objects.filter(month="2026-09").exists())
        self.assertTrue(Child.objects.filter(p_id=5).exists())

    def test_timesheet_links_to_medjournal(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/payments/"), 'href="/payments/med/"')
        page = self.client.get("/payments/med/")
        self.assertContains(page, "Журнал учёта инфекционных заболеваний")
        self.assertContains(page, 'href="/payments/"')  # назад к табелю

    def test_access(self):
        self.assertRedirects(self.client.get("/payments/med/"), "/staff/login?next=/payments/med/",
                             fetch_redirect_response=False)
        self.client.force_login(self.editor)  # сотрудник без прав на журналы
        self.assertNotContains(self.client.get("/payments/med/"), "/payments/med/infectious/")
        self.assertEqual(self.client.get("/payments/med/infectious/").status_code, 403)
        self.assertFalse(self.client.get("/api/auth/me/").json()["can_access_medjournal"])
        self.client.force_login(self.admin)
        self.assertTrue(self.client.get("/api/auth/me/").json()["can_access_medjournal"])
