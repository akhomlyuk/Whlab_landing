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

# Вывод не должен зависеть от того, кто и откуда запустил. На Windows
# консоль по умолчанию cp1251, и галочка в последней строке роняла скрипт
# с UnicodeEncodeError на ровном месте — зелёный отчёт превращался в
# красную ошибку вывода.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

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
    "Pentest, Red team, DFIR",
    "FR13NDS",
    "elsewhere",
    "projects",
    "best of",
    "Whitehat Lab",
    "MAX",
    "GitHub",
    "Hackerlab",
    "Standoff 365",
    "IT Movies",
    "Whitehat Lab stats",
    "Standoff 17",
    "Standoff 15",
    "Standoff 12",
    "VKACTF",
    "KubanCTF",
    "Cybercoliseum",
    "HackTheBox",
)

# Текст, который был на странице и по решению владельца убран. Проверка на
# отсутствие, а не только на присутствие нужного: иначе удалённая строка
# вернётся незаметно — вёрстка не сломается и ошибок не будет.
FORBIDDEN_TEXT = (
    "Участник команды",
    "Active Directory",
    "Channel Stats",
    "Автор каталога из 156",
    "пентест, форензика",
)

# Эти две убраны именно с карточек в разделе elsewhere. В meta description
# фраза «Telegram-канал о технологиях и ИИ» остаётся: там она описывает
# страницу для поиска и убирать её значило бы потерять сведения. Поэтому
# проверка смотрит в карточки, а не в документ целиком.
FORBIDDEN_IN_CARDS = (
    "Telegram-канал о технологиях",
    "Профиль на киберполигоне",
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
    for needle in FORBIDDEN_TEXT:
        if needle in html:
            errors.append(f"index.html: текст {needle!r} удалён по решению владельца, но вернулся")

    elsewhere = re.search(r'<section class="block" id="elsewhere">(.*?)</section>', html, re.S)
    if elsewhere is None:
        errors.append("index.html: не найден раздел elsewhere")
    else:
        for needle in FORBIDDEN_IN_CARDS:
            if needle in elsewhere.group(1):
                errors.append(f"index.html: подпись {needle!r} удалена с карточки, но вернулась")

    # Разметка внутри атрибута: d="<path ...". Браузер такое значение
    # игнорирует, иконка просто не рисуется — страница при этом выглядит
    # рабочей, поэтому ловится только чтением разметки.
    if 'd="<' in html:
        errors.append(
            "index.html: в атрибуте d= лежит разметка (d=\"<path ...) — иконка "
            "не отрисовалась бы, а страница выглядела бы исправной"
        )


def check_css_sanity() -> None:
    """Скобки сбалансированы и свойства не осиротели.

    Сломанный CSS не падает: правило без селектора просто игнорируется, и
    страница остаётся рабочей — теряются только отступы, рамки или выравнивание.
    Один раз при вырезании правила `.card__icon--img` потерялся селектор
    `.card {`, и его свойства прилипли к соседнему правилу: карточки остались
    в ряд, и ни ошибка, ни браузер об этом не сказали. Проверка на баланс и
    на строки-свойства сразу после `}` ловит именно такое.
    """
    for rel in ("css/style.css", "css/tokens.css", "css/fonts.css"):
        raw = read_if_present(rel)
        if raw is None:
            continue
        css = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
        if css.count("{") != css.count("}"):
            errors.append(
                f"{rel}: скобки не сбалансированы — {css.count('{')} открывающих, "
                f"{css.count('}')} закрывающих"
            )
        lines = css.split("\n")
        for i, line in enumerate(lines):
            t = line.strip()
            if not t or t.startswith(("{", "}", "@")):
                continue
            if i > 0 and lines[i - 1].strip().startswith("}"):
                errors.append(
                    f"{rel}:{i + 1}: свойство {t!r} идёт сразу после закрывающей "
                    "скобки — потерян селектор, и оно утекло в соседнее правило"
                )
    notes.append("CSS: баланс скобок и отсутствие сирот проверены")


def check_two_theme_states() -> None:
    """Выбор темы — из двух состояний, авто не выбирается вручную.

    Автоматический режим остаётся (до первого клика страница следует за
    ОС), но он не является пунктом выбора: переключатель ходит только между
    тёмной и светлой. Третье состояние означало бы, что пользователь может
    вернуться к «как в системе», а проверять это вручную — лишнее действие.
    """
    html = read_if_present("index.html")
    if html is None:
        return
    if re.search(r"'auto'", html) and "prefers-color-scheme" not in html:
        errors.append("index.html: слово 'auto' осталось, но авто-режим должен быть только неявным")
    if re.search(r"=== 'light'\s*\?\s*'auto'", html):
        errors.append("index.html: цикл переключателя всё ещё возвращает в auto — состояний должно быть два")
    notes.append("Состояний темы в переключателе: два (проверено по циклу)")


def check_project_icons() -> None:
    """У карточек проектов должны быть свои иконки.

    Пустая плитка ради единообразия с разделом ссылок выглядит дырой:
    ссылка это площадка с логотипом, проект это сайт с favicon.
    """
    html = read_if_present("index.html")
    if html is None:
        return
    m = re.search(r'<section class="block" id="projects">(.*?)</section>', html, re.S)
    if m is None:
        errors.append("index.html: не найден раздел projects")
        return
    block = m.group(1)
    cards = re.findall(r'<a class="card".*?</a>', block, re.S)
    if not cards:
        errors.append("projects: карточек нет")
        return
    with_icon = [c for c in cards if ("card__icon" in c)]
    if len(with_icon) != len(cards):
        errors.append(
            f"projects: иконка есть только у {len(with_icon)} из {len(cards)} карточек — "
            "у каждого проекта своя favicon"
        )
    for c in with_icon:
        for url in re.findall(r'src="([^"]+)"', c):
            if not (ROOT / url).exists():
                errors.append(f"projects: иконка не найдена на диске: {url}")
    notes.append(f"Карточек проектов с иконкой: {len(with_icon)} из {len(cards)}")


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


def check_theme() -> None:
    """Тема обязана применяться до первой отрисовки и переживать перезагрузку.

    Инлайн-скрипт в <head> — приём против вспышки светлой темы на тёмном
    домене: поставленный в конце файла или в модуле, он отработает уже
    после того, как браузер нарисует светлый фон.
    """
    html = read_if_present("index.html")
    if html is None:
        return

    head_end = html.find("</head>")
    if head_end == -1:
        errors.append("index.html: нет </head>")
        return
    head = html[:head_end]

    if "whlab-theme" not in html:
        errors.append("index.html: ключ localStorage 'whlab-theme' не найден")
    if "it-movies-theme" in html:
        errors.append(
            "index.html: использован ключ it-movies-theme — настройки разных "
            "доменов не должны перетирать друг друга"
        )

    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", head, re.DOTALL)
    if not any("whlab-theme" in s for s in scripts):
        errors.append(
            "index.html: скрипта темы нет в <head> — он обязан быть там и "
            "без defer, иначе видна вспышка светлой темы"
        )

    if "defer" in head and "whlab-theme" in head:
        errors.append("index.html: скрипт темы помечен defer — применение темы уйдёт на потом")

    if 'name="theme-color"' not in html:
        errors.append("index.html: нет meta[name=theme-color] — скроллбар и нативные контролы останутся в теме ОС")

    notes.append(f"Скриптов в <head>: {len(scripts)}")


def check_auto_theme_fallback() -> None:
    """Состояние auto обязано означать «как в системе», а не «тёмная».

    Тёмная палитра живёт в :root, а :root без атрибута data-theme — это и
    есть auto. Без prefers-color-scheme ветки светлая ОС получит тёмную
    страницу, и никто об этом не узнает.
    """
    tokens = read_if_present("css/tokens.css")
    if tokens is None:
        return
    if not re.search(r"@media\s*\(prefers-color-scheme:\s*light\)\s*\{[^}]*:root:not\(\[data-theme\]\)", tokens):
        errors.append(
            "tokens.css: нет @media (prefers-color-scheme: light) с :root:not([data-theme]) — "
            "состояние auto не будет следовать за ОС"
        )


SITE = "https://whlab.ru/"

REQUIRED_META = (
    'og:title', 'og:description', 'og:image', 'og:url', 'og:type',
    'og:site_name', 'og:locale', 'twitter:card', 'twitter:image',
)


def check_meta() -> None:
    html = read_if_present("index.html")
    if html is None:
        return

    head = html[: html.find("</head>") if "</head>" in html else len(html)]
    for prop in REQUIRED_META:
        if f'property="{prop}"' not in head and f'name="{prop}"' not in head:
            errors.append(f"index.html <head>: нет {prop}")

    canon = re.search(r'<link rel="canonical" href="([^"]+)"', head)
    if canon is None:
        errors.append("index.html <head>: нет canonical")
    elif canon.group(1) != SITE:
        errors.append(f"canonical указывает на {canon.group(1)}, а не на {SITE}")

    og_url = re.search(r'property="og:url" content="([^"]+)"', head)
    if og_url and og_url.group(1) != SITE:
        errors.append(f"og:url указывает на {og_url.group(1)}, а не на {SITE}")

    img = re.search(r'property="og:image" content="([^"]+)"', head)
    if img:
        url = img.group(1)
        if not url.startswith(SITE):
            errors.append(f"og:image ведёт не на свой домен: {url}")
        rel = url[len(SITE):]
        if not (ROOT / rel).exists():
            errors.append(f"og:image не существует на диске: {rel}")

    notes.append(f"Мета-тегов проверено: {len(REQUIRED_META)} + canonical")


def check_print_styles() -> None:
    """Печать визитки — реальный сценарий, а не заморочка.

    Тёмный фон на печати съедает тонер, а текст, нарисованный --muted, при
    выключенных фонах может оказаться белым на белом. Поэтому @media print
    обязан подставлять светлые значения явно.
    """
    css = read_if_present("css/style.css")
    if css is None:
        return
    m = re.search(r"@media\s*print\s*\{(.*)\}\s*$", css, re.DOTALL)
    if m is None:
        errors.append("css/style.css: нет @media print")
        return
    block = m.group(1)
    for needed in ("--bg", "--text", "--muted"):
        if needed not in block:
            errors.append(f"@media print не переопределяет {needed} — печать может выйти нечитаемой")
    notes.append("Печатные правила: найдены")


def check_fonts() -> None:
    """Шрифт, объявленный в токенах, обязан реально грузиться.

    Имя в --font/--mono само по себе ничего не значит: если @font-face нет,
    браузер молча уходит на следующее в списке и рисует системным шрифтом.
    Страница при этом выглядит рабочей, вёрстка не едет, ошибок в консоли
    нет — расходится только начертание. Обнаруживается это замером ширины
    текста, а не просмотром кода.

    Проверяются обе стороны: каждый семейный шрифт из токенов имеет
    @font-face, и каждый url() из fonts.css указывает на файл, который
    существует.
    """
    tokens = read_if_present("css/tokens.css")
    fonts = read_if_present("css/fonts.css")
    html = read_if_present("index.html")
    if tokens is None:
        return

    if fonts is None:
        errors.append("css/fonts.css отсутствует — --font и --mono уйдут на системный шрифт")
        return

    declared = set()
    for raw in re.findall(r"--(?:font|mono):\s*([^;]+);", tokens):
        for part in raw.split(","):
            name = part.strip().strip("'\"")
            # Системные и общие имена шрифтом быть не могут.
            if not name or name in {
                "sans-serif", "serif", "monospace", "system-ui", "ui-monospace",
                "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto",
                "SF Mono", "Cascadia Code", "Consolas", "cursive", "fantasy",
            }:
                continue
            declared.add(name)

    faces = set(re.findall(r"font-family:\s*\"([^\"]+)\"", fonts))
    for name in sorted(declared - faces):
        errors.append(f"токен ссылается на шрифт {name!r}, но @font-face для него нет")

    for url in re.findall(r"url\(\"?([^\")]+)\"?\)", fonts):
        if url.startswith(("http://", "https://", "data:")):
            errors.append(f"fonts.css тянет шрифт извне: {url} — самохостинг или ничего")
            continue
        rel = (ROOT / "css" / url).resolve().relative_to(ROOT)
        if not (ROOT / rel).exists():
            errors.append(f"fonts.css ссылается на отсутствующий файл: {url}")

    if html is not None and "css/fonts.css" not in html:
        errors.append("index.html не подключает css/fonts.css")

    notes.append(f"Шрифтов объявлено в токенах: {len(declared)}, @font-face: {len(faces)}")


def _codepoints(spec: str) -> set[int]:
    """Разобрать список unicode-range в множество кодовых точек."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip().removeprefix("U+")
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-")
            out |= set(range(int(lo, 16), int(hi, 16) + 1))
        else:
            out.add(int(part, 16))
    return out


def check_font_charset_coverage() -> None:
    """Диапазоны сабсетов не перекрываются и покрывают текст страницы.

    Ошибка, которую это ловит, стоила одной выкладки и выглядела
    безобидно. У всех трёх файлов JetBrains Mono стоял одинаковый
    `unicode-range: U+0000-00FF`. Диапазоны перекрываются, а при
    совпадении выигрывает последнее объявление — латинский файл, в
    котором нет кириллических глифов. Весь русский текст в
    моноширинных элементах уходил в системный шрифт по умолчанию и
    рисовался пропорциональным: страница не падала, вёрстка не ехала, в
    консоли было чисто. Заметить можно только замером ширины.

    Отсюда две проверки. Первая — структурная: у одного семейства и
    веса не может быть двух одинаковых диапазонов, это всегда ошибка
    независимо от того, какие символы на странице. Вторая — по
    содержимому: объединение диапазонов каждого семейства обязано
    покрывать каждый не-ASCII символ из index.html.
    """
    fonts = read_if_present("css/fonts.css")
    html = read_if_present("index.html")
    if fonts is None or html is None:
        return

    faces = []
    for body in re.findall(r"@font-face\s*\{(.*?)\}", fonts, re.S):
        fam = re.search(r'font-family:\s*"([^"]+)"', body)
        weight = re.search(r"font-weight:\s*([^;]+);", body)
        urange = re.search(r"unicode-range:\s*([^;]+);", body)
        src = re.search(r'url\("([^"]+)"\)', body)
        if not (fam and urange and src):
            errors.append("@font-face без font-family, src или unicode-range")
            continue
        faces.append((
            fam.group(1),
            weight.group(1).strip() if weight else "",
            src.group(1).rsplit("/", 1)[-1],
            " ".join(urange.group(1).split()),
        ))

    # Первая проверка: одинаковый диапазон в одном семействе.
    seen: dict[tuple[str, str, str], str] = {}
    for fam, weight, fname, urange in faces:
        key = (fam, weight, urange)
        if key in seen:
            errors.append(
                f"css/fonts.css: {fam} {weight} — у {seen[key]} и {fname} "
                f"одинаковый unicode-range ({urange}). Сабсеты перекрываются, "
                "победит последний объявленный, а его глифов может не хватить"
            )
        else:
            seen[key] = fname

    # Вторая проверка: покрытие символов страницы.
    body_text = re.sub(r"<style.*?</style>|<script.*?</script>", " ", html, flags=re.S)
    body_text = re.sub(r"<[^>]+>", " ", body_text)
    needed = {ord(c) for c in body_text if ord(c) > 127}
    if not needed:
        notes.append("Не-ASCII символов на странице нет, покрытие проверять нечем")
        return

    for fam in sorted({f[0] for f in faces}):
        covered: set[int] = set()
        for f_fam, _w, _fn, urange in faces:
            if f_fam == fam:
                covered |= _codepoints(urange)
        missing = sorted(needed - covered)
        if missing:
            shown = ", ".join(f"U+{m:04X}" for m in missing[:12])
            if len(missing) > 12:
                shown += f" и ещё {len(missing) - 12}"
            errors.append(
                f"{fam}: объявленные unicode-range не покрывают "
                f"{len(missing)} символов со страницы: {shown} — "
                "они уйдут в системный шрифт"
            )
        else:
            notes.append(f"{fam}: покрывает все {len(needed)} не-ASCII символов страницы")


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
    check_two_theme_states()
    check_project_icons()
    check_internal_links()
    check_theme()
    check_auto_theme_fallback()
    check_meta()
    check_print_styles()
    check_fonts()
    check_font_charset_coverage()
    check_css_sanity()

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