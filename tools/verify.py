#!/usr/bin/env python3
"""Проверки целостности визитки.

Единственный тестовый набор проекта: сборки нет, зависимостей нет, гонять
нечего — эта штука и заменяет тесты. Голый стандартный Python.

Запуск: python tools/verify.py
Код возврата: 0 — всё сошлось, 1 — есть ошибки.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

errors: list[str] = []
notes: list[str] = []

# Мёртвый токен проверяется с Task 2: пока нет ни style.css, ни index.html,
# «не используется» верно для каждого токена и проверка была бы vacuously
# верной. Флаг, а не удалённая строка, — чтобы проверка существовала в файле
# с первой версии и просто ждала потребителей.
DEAD_TOKEN_CHECK = True


def read(rel: str) -> str | None:
    """Прочитать файл или записать ошибку. Отсутствие файла — ошибка,
    а не пустой текст: иначе проверки молча проходят по обочине."""
    p = ROOT / rel
    if not p.exists():
        errors.append(f"{rel}: файл отсутствует")
        return None
    return p.read_text(encoding="utf-8")


def read_if_present(rel: str) -> str | None:
    """Прочитать файл, если он есть, и не ругаться если его нет.

    Нужно там, где проверка интересуется содержимым чужого файла, а не его
    существованием: «токен, на который ссылается style.css, объявлен» не
    обязано сообщать об отсутствии style.css — это работа другой проверки.
    Иначе проверка роняет сборку на файле, который ещё не создан, и GREEN
    недостижим.
    """
    p = ROOT / rel
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def check_tokens() -> None:
    """Каждый var(--имя) обязан быть объявлен в tokens.css.

    Опечатка в имени токена не роняет CSS: незакрытое var() тихо уходит в
    наследование, и ломается всё, что на него опиралось, — ровно так из
    IT_movies однажды потерялся --accent-text.
    """
    tokens = read("css/tokens.css")
    if tokens is None:
        return

    defined = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", tokens, re.MULTILINE))
    used: set[str] = set()
    for rel in ("css/style.css", "index.html"):
        txt = read_if_present(rel)
        if txt is None:
            continue
        used |= set(re.findall(r"var\(\s*(--[a-z0-9-]+)", txt))

    for name in sorted(used - defined):
        errors.append(f"ссылка на необъявленный токен: var({name})")

    if DEAD_TOKEN_CHECK:
        # Шкала отступов освобождена намеренно и узко. `--space-8` — это не
        # токен под конкретный элемент, а ступень системы: убрать её потому,
        # что сегодняшняя страница не доросла до 4rem, значит завтра её
        # придётся возвращать, и шкала перестанет быть шкалой. Остальные
        # токены под правило попадают: --accent-hover существует ради
        # конкретного ховера, и если ховер убрали, токен мёртв.
        scale = {n for n in defined - used if n.startswith("--space-")}
        for name in sorted(defined - used - scale):
            errors.append(f"токен объявлен, но не используется: {name}")

    notes.append(
        f"Токены: объявлено {len(defined)}, используется {len(used)}, "
        f"лишних {len(defined - used)} (шкала --space-* не считается)"
    )


# Строки, которые обязаны присутствовать в разметке как текст. Визитка
# обязана читаться без JS: шапка-консоль декоративна, и при проверке очень
# легко свалить начинку страницы в скрипт — тогда выключенный JS оставит
# пустую страницу вместо визитки.
REQUIRED_TEXT = (
    "Exited3n",
    "пентест, форензика",
    "FR13NDS",
    "Active Directory",
    "elsewhere",
    "projects",
    "Whitehat Lab",
    "MAX",
    "GitHub",
    "Hackerlab",
    "Standoff 365",
    "IT Movies",
    "Channel Stats",
    "киберполигон",
)


def check_pages_exist() -> None:
    for rel in ("index.html", "css/style.css"):
        read(rel)


def check_external_links() -> None:
    """Внешняя ссылка обязана открываться безопасно и в новой вкладке.

    Без rel=noopener страница, открытая в новой вкладке, получает
    window.opener и может увести исходное окно на свой домен через
    history.pushState. На визитке с пятью внешними ссылками это и есть
    главный вектор, а не гипотетика.
    """
    html = read_if_present("index.html")
    if html is None:
        return

    anchors = re.findall(r"<a\b[^>]*>", html)
    external = 0
    for tag in anchors:
        href = re.search(r'\bhref\s*=\s*"([^"]+)"', tag)
        if href is None:
            errors.append("<a> без href")
            continue
        url = href.group(1)
        if not url.startswith(("http://", "https://")):
            continue
        external += 1
        if 'target="_blank"' not in tag:
            errors.append(f"внешняя ссылка без target=_blank: {url}")
        rel = re.search(r'\brel\s*=\s*"([^"]*)"', tag)
        if rel is None or "noopener" not in rel.group(1).split():
            errors.append(f"внешняя ссылка без rel=noopener: {url}")

    notes.append(f"Внешних ссылок: {external}")


def check_content_is_static() -> None:
    html = read_if_present("index.html")
    if html is None:
        return
    for needle in REQUIRED_TEXT:
        if needle not in html:
            errors.append(f"index.html: не найден текст {needle!r} — контент обязан быть в разметке, а не собираться скриптом")


def check_internal_links() -> None:
    """Каждый локальный href/src обязан существовать файлом на диске."""
    html = read_if_present("index.html")
    if html is None:
        return

    checked = 0
    for attr in re.findall(r'(?:href|src)\s*=\s*"([^"]+)"', html):
        url = attr.split("?")[0].split("#")[0]
        if not url or url.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:")):
            continue
        target = ROOT / url.lstrip("/")
        if not target.exists():
            errors.append(f"ссылка ведёт в никуда: {attr}")
        checked += 1
    notes.append(f"Локальных ссылок проверено: {checked}")


def check_light_palette_consistency() -> None:
    """Два блока светлой палитры обязаны совпадать побайтно.

    Они существуют по необходимости, а не по недосмотру: `auto` при светлой
    ОС ловится только через prefers-color-scheme, явный выбор — только через
    [data-theme='light'], и одним селектором их не объединить. Плата —
    значение каждого токена написано дважды. Разъехаться они могут молча:
    страница станет наполовину светлой, и по этому ничто не подскажет.

    Поэтому расхождение здесь не стилистика, а ошибка сборки.
    """
    tokens = read_if_present("css/tokens.css")
    if tokens is None:
        return

    def block(pattern: str) -> dict[str, str]:
        m = re.search(pattern, tokens, re.DOTALL)
        if m is None:
            errors.append(f"tokens.css: не найден блок {pattern}")
            return {}
        return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", m.group(1)))

    from_media = block(r"@media\s*\(prefers-color-scheme:\s*light\)\s*\{\s*:root:not\(\[data-theme\]\)\s*\{(.*?)\n  \}")
    explicit = block(r"\[data-theme='light'\]\s*\{(.*?)\n\}")

    if from_media == explicit:
        notes.append(f"Светлая палитра: {len(explicit)} токенов в обоих блоках, совпадают")
        return

    for name in sorted(set(from_media) | set(explicit)):
        a, b = from_media.get(name), explicit.get(name)
        if a != b:
            errors.append(
                f"светлая палитра разошлась в {name}: "
                f"prefers-color-scheme={a!r}, [data-theme='light']={b!r}"
            )


def main() -> int:
    check_tokens()
    check_light_palette_consistency()
    check_pages_exist()
    check_external_links()
    check_content_is_static()
    check_internal_links()

    for n in notes:
        print(f"  {n}")
    if errors:
        print()
        for e in errors:
            print(f"ОШИБКА: {e}")
        print(f"\n{len(errors)} ошибок")
        return 1
    print("\n✅ OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())