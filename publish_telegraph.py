"""Публикация документов на Telegra.ph.

Telegram показывает такие страницы через Instant View: сверху заголовок
документа вместо адреса, открывается мгновенно, без браузера. Именно так
сделано у оригинала.

Запуск: python landing/publish_telegraph.py
Ссылки печатаются в конце — их нужно прописать в .env бота.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.telegra.ph"
AUTHOR = "67 Star"
TOKEN_FILE = Path(__file__).parent / ".telegraph_token"


def call(method: str, **params) -> dict:
    data = urllib.parse.urlencode(
        {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
         for k, v in params.items() if v is not None}
    ).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=30) as r:
        result = json.loads(r.read())
    if not result.get("ok"):
        raise RuntimeError(f"{method}: {result.get('error')}")
    return result["result"]


def get_token() -> str:
    """Токен нужен, чтобы позже редактировать страницы, а не плодить новые."""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    account = call("createAccount", short_name="67Star", author_name=AUTHOR)
    TOKEN_FILE.write_text(account["access_token"])
    return account["access_token"]


def html_to_nodes(html: str) -> list:
    """Разбор наших документов в формат Telegra.ph.

    Полноценный парсер не нужен: документы写 по одному шаблону —
    заголовки h2, списки ul/li и абзацы.
    """
    body = re.search(r"<body>(.*?)</body>", html, re.S)
    html = body.group(1) if body else html
    # Заголовок и дата выводятся Telegra.ph отдельно
    html = re.sub(r"<h1>.*?</h1>", "", html, flags=re.S)
    html = re.sub(r'<div class="date">.*?</div>', "", html, flags=re.S)

    nodes: list = []
    for match in re.finditer(
        r"<h2>(.*?)</h2>|<li>(.*?)</li>|<p[^>]*>(.*?)</p>", html, re.S
    ):
        h2, li, p = match.groups()
        if h2 is not None:
            nodes.append({"tag": "h3", "children": [clean(h2)]})
        elif li is not None:
            nodes.append({"tag": "p", "children": inline(li)})
        elif p is not None:
            text = clean(p)
            if text:
                nodes.append({"tag": "p", "children": [{"tag": "i", "children": [text]}]})
    return nodes


def inline(fragment: str) -> list:
    """Сохраняем жирный текст, остальную разметку убираем."""
    parts: list = []
    pos = 0
    for m in re.finditer(r"<b>(.*?)</b>", fragment, re.S):
        before = clean(fragment[pos : m.start()])
        if before:
            parts.append(before)
        parts.append({"tag": "b", "children": [clean(m.group(1))]})
        pos = m.end()
    tail = clean(fragment[pos:])
    if tail:
        parts.append(tail)
    return parts or [""]


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&laquo;", "«")
        .replace("&raquo;", "»")
        .replace("&mdash;", "—")
        .replace("&amp;", "&")
    )
    return re.sub(r"\s+", " ", text).strip()


def publish(filename: str, title: str) -> str:
    html = (Path(__file__).parent / filename).read_text(encoding="utf-8")
    page = call(
        "createPage",
        access_token=get_token(),
        title=title,
        author_name=AUTHOR,
        content=html_to_nodes(html),
        return_content="false",
    )
    return page["url"]


if __name__ == "__main__":
    terms = publish("terms.html", "Пользовательское соглашение")
    privacy = publish("privacy.html", "Политика конфиденциальности")

    print("\nготово, пропишите в .env:\n")
    print(f"RULES_URL={terms}")
    print(f"PRIVACY_URL={privacy}")
