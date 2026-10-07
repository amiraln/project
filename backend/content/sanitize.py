"""Очистка HTML, который сотрудники вводят в админке.

Даже если в текст попадёт <script> или onclick=..., на сайт он не пройдёт.
"""
import nh3

ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "a",
    "ul", "ol", "li", "h2", "h3", "h4", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td", "caption", "hr",
}
ALLOWED_ATTRS = {"a": {"href", "title"}, "th": {"scope", "colspan", "rowspan"}, "td": {"colspan", "rowspan"}}


def clean_html(value: str) -> str:
    if not value:
        return ""
    # Если текст без HTML-тегов — превращаем абзацы в <p>, чтобы сотрудникам не нужно было знать HTML.
    if "<" not in value:
        paragraphs = [p.strip().replace("\n", "<br>") for p in value.replace("\r\n", "\n").split("\n\n")]
        value = "".join(f"<p>{p}</p>" for p in paragraphs if p)
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto", "tel"},
        link_rel="noopener noreferrer",
    )
