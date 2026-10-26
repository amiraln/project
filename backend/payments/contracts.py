"""Договор с родителем в Word: шаблон contract_template.docx, в нём на месте прочерков — метки {{поле|прочерк}}.

Метку заменяет значение из табеля и контактов e-orda; нет значения — остаётся прочерк, чтобы вписать от руки.
Поля: parent, child, birth_date, group — в шапке и п. 1.1; req_fio, req_fio_more, req_iin, req_phone — в реквизитах.
Текст договора можно править в Word, не трогая метки."""
import io
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from .models import Guardian, guardian_match

TEMPLATE = Path(__file__).with_name("contract_template.docx")
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FIELD = re.compile(r"\{\{(\w+)\|(_*)\}\}")
PARENT_ORDER = {Guardian.MOTHER: 0, Guardian.FATHER: 1}  # договор по умолчанию — на мать, нет её — на отца


def birth_date(iin):
    """Дата рождения из ИИН: первые 6 цифр — ГГММДД, век — по 7-й цифре (5 и 6 — 2000-е)."""
    if not re.fullmatch(r"\d{12}", iin or ""):
        return None
    century = {"1": 1800, "2": 1800, "3": 1900, "4": 1900, "5": 2000, "6": 2000}.get(iin[6])
    try:
        return date(century + int(iin[:2]), int(iin[2:4]), int(iin[4:6])) if century else None
    except ValueError:
        return None


def parents(rec):
    """Родители ребёнка из строки табеля: сначала мать, потом отец, потом остальные."""
    return sorted(Guardian.objects.filter(guardian_match(rec.p_id, rec.iin)),
                  key=lambda g: (PARENT_ORDER.get(g.gender, 2), g.pk))


def contract_fields(rec, parent=None):
    """Значения меток договора; None — оставить прочерк."""
    born = birth_date(rec.iin)
    name = parent.fio.strip() if parent else ""
    return {
        "parent": name or None,
        "child": rec.fio or None,
        "birth_date": born.strftime("%d.%m.%Y") if born else None,
        "group": rec.group_name or None,
        "req_fio": name or None,
        "req_fio_more": "" if name else None,  # строка под ФИО — для длинного ФИО от руки
        "req_iin": (parent.iin if parent else "") or None,
        "req_phone": ", ".join(parent.phones if parent else []) or None,
    }


def contract_docx(fields):
    """Заполненный договор, байты .docx."""
    def fill(m):
        value = fields.get(m[1])
        return m[2] if value is None else escape(value)

    out = io.BytesIO()
    with zipfile.ZipFile(TEMPLATE) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item)
            if item.filename == "word/document.xml":
                data = FIELD.sub(fill, data.decode("utf-8")).encode("utf-8")
            dst.writestr(item, data)
    return out.getvalue()


def file_name(rec):
    return "Договор — " + (re.sub(r'[\\/:*?"<>|]+', " ", rec.fio).strip() or str(rec.p_id)) + ".docx"


def contracts_zip(records):
    """Архив договоров: по одному на каждого ребёнка, родитель — как в parents()."""
    out = io.BytesIO()
    used = Counter()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in records:
            found = parents(rec)
            name = file_name(rec)
            used[name] += 1
            if used[name] > 1:  # тёзки
                name = f"{name[:-5]} ({used[name]}).docx"
            zf.writestr(name, contract_docx(contract_fields(rec, found[0] if found else None)))
    return out.getvalue()
