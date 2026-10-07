"""Обработка загруженных фото: удаляем EXIF (в нём бывают GPS-координаты) и уменьшаем до 2000 px."""
import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_SIDE = 2000


def process_image(field):
    # _committed=False означает «файл только что загружен и ещё не сохранён»
    if not field or getattr(field, "_committed", True):
        return
    field.open()
    img = Image.open(field)
    fmt = (img.format or "JPEG").upper()
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if fmt not in ("JPEG", "PNG", "WEBP"):
        fmt = "JPEG"
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format=fmt, quality=85, optimize=True)  # без exif=...
    name = os.path.splitext(os.path.basename(field.name))[0]
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]
    field.save(f"{name}.{ext}", ContentFile(buf.getvalue()), save=False)
