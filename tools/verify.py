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

    --gold, --radius-pill и --shadow удалены редизайном 2026-10-09: кубки
    и медали ушли вместе с разбивкой достижений по годам, пилюли остались
    только у CTA в шапке и им хватает --radius, а тень ушла вместе с
    подъёмом на ховере — отклик дают рамка и цвет. Проверка на отсутствие
    нужна, иначе вернувшийся токен снова станет обязательным для
    потребителей.
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

    # --shadow удалён 2026-10-09 вместе с подъёмом на ховере: круглые
    # карточки ушли, а отклик теперь дают рамка и цвет, и тени на
    # странице не отбрасывает ни один элемент.
    for gone in ("--gold", "--radius-pill", "--shadow"):
        if gone in defined:
            errors.append(
                f"токен {gone} удалён редизайном 2026-10-09, но объявлен снова — "
                "убедитесь, что на него не ссылается ни один потребитель"
            )

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
    "FR13NDS",
    "$ whoami",
    "Red team · Pentest · DFIR",
    "about",
    "elsewhere",
    "best of",
    "projects",
    "В сфере ИТ с 2010 года",
    # Фраза разорвана тегом ссылки: «...призёр <a>Standoff 365</a>».
    # Поэтому проверяются части, а не целая строка — иначе проверка
    # требовала бы от автора убрать ссылку из факта.
    "Постоянный участник и призёр",
    "Standoff 365",
    "Атаки на Active Directory",
    "MAX",
    "GitHub",
    "Hackerlab",
    "IT Movies",
    "Whitehat Lab stats",
    "CTF-площадки",
    # Достижения переехали в панель Standoff (2026-10-09, Task 7): годы и
    # названия площадок больше не строки списка, а содержимое плиток и одна
    # приглушённая строка «также:». Проверяются поэтому не «Standoff 17»,
    # а то, что из достижений действительно осталось на странице.
    #
    # VKACTF, KubanCTF и Cybercoliseum отсюда убраны 2026-10-09: строка
    # «также» теперь проверяется целиком и по порядку в check_best_of_shape
    # (ALSO_PLACES). Пока она проверялась по подстрокам, имена стояли
    # здесь — и четвёртое, HTB, выпало молча, потому что «HackTheBox»
    # убрали из этого списка решением Task 7, а замену не закрепили.
    # Возвращать их сюда нельзя: проверка подстроками ничего не говорит
    # о полноте строки и о её порядке.
    "Top 3",
    "Top 2",
    "призёр · площадка PHDays",
    "также:",
)

# Фоновые места — спека §3.5, четыре выступления, в порядке строки.
# Порядок прибит по той же причине, что и у троек Standoff: строка
# «также» читается слева направо, и перестановка меняет то, что страница
# о себе утверждает. Здесь важно ещё и то, что набор закрыт: раньше
# имена стояли подстроками в REQUIRED_TEXT, и потеря HTB проходила молча.
ALSO_PLACES = (
    "VKACTF Top 2",
    "HTB Cyber Apocalypse Top 4",
    "KubanCTF Top 1",
    "Cybercoliseum Top 2",
)

# Текст, который был на странице и по решению владельца убран. Проверка на
# отсутствие, а не только на присутствие нужного: иначе удалённая строка
# вернётся незаметно — вёрстка не сломается и ошибок не будет.
#
# Три бывших запрета сняты 2026-10-09: новая спека §3 возвращает био-абзац
# из старой спеки §8 целиком, вместе с «Участником команды», «Active
# Directory» и «156 фильмов». Список ниже — только то, что новая спека
# оставляет запрещённым.
FORBIDDEN_TEXT = (
    "Channel Stats",
    "ExIT & EDEN",
    # Курсор в конце заголовка и висячий промпт убраны решением владельца
    # 2026-10-09 в пользу префикса-решётки: `$ whoami` рифмуется с `#about`.
    "Pentest, Red team, DFIR",
    # Форма с запятой не встречается нигде: в подписи hero «пентест и
    # форензика», в био «Пентест и форензика». Запрет остаётся, потому
    # что снятие запрета владельца — это решение, а не молчаливое
    # упрощение списка при правке.
    "пентест, форензика",
    # Факт про канал убран 2026-10-09: канал стал первой карточкой
    # projects, и два упоминания на одном экране — это повтор.
    "Автор канала",
    # Подпись команды убрана решением владельца: FR13NDS остаётся ссылкой.
    "моя команда",
    # Бывшая подпись карточки на киберполигоне. Список FORBIDDEN_IN_CARDS,
    # который её охранял, удалён вместе с карточками: лента ссылок стала
    # чипами, у которых вообще нет слота подписи, и проверять там было
    # нечего. Запрет переносится на документ целиком, чтобы фраза не
    # вернулась молча — ровно для этого список и существует.
    "Профиль на киберполигоне",
)

# «Telegram-канал о технологиях и ИИ» в FORBIDDEN_TEXT сознательно НЕТ,
# хотя раньше фраза была запрещена на карточках elsewhere. Редизайн
# 2026-10-09 пересмотрел её статус: спека §3.4 вернула её как подпись
# первой строки projects («Whitehat Lab»), то есть канал описывался
# этой фразой, а не прятался от неё.
#
# 2026-10-09 (после сборки страницы) подпись первой строки заменена
# владельцем на «Авторский канал об информационной безопасности», а
# фраза осталась только в meta description и og:description. Это разные
# вещи: подпись на странице утверждает, о чём канал, и её сменил
# владелец; мета-теги описывают страницу для поиска, и менять их
# без решения владельца нельзя. Запрещать фразу нельзя и по второй
# причине — она вернулась бы вместе с чужой правкой мета-тегов и
# сломала бы страницу, которой никто не касался.
#
# Пока фраза жива в мета-тегах, проверить её нельзя было бы подпиской
# строки: REQUIRED_TEXT такой строки не содержит, и это правильно —
# подпись проекта менялась уже дважды, и каждый раз проверка требовала
# бы правки кода, а не страницы.


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

    # Разметка внутри атрибута: d="<path ...". Браузер такое значение
    # игнорирует, иконка просто не рисуется — страница при этом выглядит
    # рабочей, поэтому ловится только чтением разметки.
    if 'd="<' in html:
        errors.append(
            "index.html: в атрибуте d= лежит разметка (d=\"<path ...) — иконка "
            "не отрисовалась бы, а страница выглядела бы исправной"
        )

    # Порядок в DOM = порядок чтения и порядок на узком экране (спека §2.2).
    # projects поднимается над elsewhere: это самые кликабельные ссылки
    # страницы, и на телефоне до них должен быть один прокрут, а не три.
    #
    # В списке классов секции допускаются модификаторы: `class="block(?:\s[^"]*)?"`,
    # а не `class="block"`. Блок --panel (у блоков с тяжёлой панелью) —
    # ровно такой модификатор, и точное совпадение перестало бы находить
    # projects вовсе: раздел молча выпал бы из проверки порядка, а страница
    # осталась бы выглядеть рабочей.
    #
    # Форма именно такая, а не `class="block[^"]*"`: последняя согласилась
    # бы и на `class="blocks"`, то есть засчитала бы чужой класс как
    # секцию — и порядок разделов упал бы с сообщением, от которого до
    # причины далеко. Модификатор отделяется пробелом, и ничего больше.
    order = [m.group(1) for m in re.finditer(r'<section class="block(?:\s[^"]*)?" id="([a-z]+)">', html)]
    if order != ["about", "projects", "best", "elsewhere"]:
        errors.append(
            f"index.html: порядок разделов {order}, ожидался "
            "['about', 'projects', 'best', 'elsewhere']"
        )


def check_block_hashes() -> None:
    """Заголовок блока начинается с решётки и не кончится курсором.

    Висячий `_` читался как незакрытый промпт — незаконченная мысль.
    Решётка в начале читается как рут и рифмуется с `$ whoami` в шапке.
    """
    html = read_if_present("index.html")
    if html is None:
        return

    if "block__caret" in html or "block__caret" in (read_if_present("css/style.css") or ""):
        errors.append("block__caret вернулся — заголовок блока не должен кончаться курсором")

    titles = re.findall(r'<h2 class="block__title">(.*?)</h2>', html, re.S)
    if len(titles) != 4:
        errors.append(f"index.html: заголовков блоков {len(titles)}, ожидалось 4")
    for t in titles:
        if 'block__hash' not in t:
            errors.append(f"заголовок без решётки: {t.strip()[:40]!r}")

    notes.append(f"Заголовков с решёткой: {sum('block__hash' in t for t in titles)} из {len(titles)}")


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
    # Классы секции ищутся как `class="block(?:\s[^"]*)?"`: у projects в списке
    # есть модификатор --panel, и точное `class="block"` не нашло бы
    # раздел — проверка упала бы «не найден раздел projects» на вполне
    # годной разметке. Форма с `\s` отсекает подставные `class="blocks"`.
    m = re.search(r'<section class="block(?:\s[^"]*)?" id="projects">(.*?)</section>', html, re.S)
    if m is None:
        errors.append("index.html: не найден раздел projects")
        return
    block = m.group(1)
    # Модификатор в списке классов строки (`row row--accent`) тоже должен
    # попадать в выборку. С точным `<a class="row"` первая строка панели —
    # та самая, что несёт главный переход на канал — не находилась вовсе:
    # проверка рапортовала «3 из 3» и молча пропускала знак канала.
    rows = re.findall(r'<a class="row(?:\s[^"]*)?".*?</a>', block, re.S)
    if not rows:
        errors.append("projects: строк нет")
        return
    with_icon = [c for c in rows if ("row__icon" in c)]
    if len(with_icon) != len(rows):
        errors.append(
            f"projects: иконка есть только у {len(with_icon)} из {len(rows)} строк — "
            "у каждого проекта своя favicon"
        )
    for c in with_icon:
        for url in re.findall(r'src="([^"]+)"', c):
            if not (ROOT / url).exists():
                errors.append(f"projects: иконка не найдена на диске: {url}")
    notes.append(f"Строк проектов с иконкой: {len(with_icon)} из {len(rows)}")


def check_best_of_shape() -> None:
    """Standoff собран в одну панель, остальное — одной приглушённой строкой.

    Разбивка достижений по годам прятала Standoff в трёх разных местах:
    он попадал в 2026, в 2025 и в 2024, и не читался как одна история.
    Владелец назвал его главным, всё остальное — фоном, поэтому у
    первых мест нет ни кубков, ни медалей: отдельная графика сделала бы
    VKACTF и KubanCTF равными.
    """
    html = read_if_present("index.html")
    if html is None:
        return

    # Раздел best несёт модификатор block--panel, как и projects, поэтому
    # класс секции ищется той же формой, что и в остальных проверках файла
    # (см. check_project_icons): точное `class="block"` не нашло бы раздел
    # и проверка ругалась бы «не найден раздел best» на годной разметке.
    m = re.search(r'<section class="block(?:\s[^"]*)?" id="best">(.*?)</section>', html, re.DOTALL)
    if m is None:
        errors.append("index.html: не найден раздел best")
        return
    block = m.group(1)

    if "spotlight" not in block:
        errors.append("best of: нет панели .spotlight — Standoff обязан быть собран в одно место")
    if "year__label" in block:
        errors.append("best of: разбивка по годам вернулась — Standoff снова расползётся по трём местам")
    if "result__icon" in block:
        errors.append("best of: кубки и медали вернулись — у фоновых мест графики быть не должно")

    # Содержимое панели проверяется тройками «год → событие → место» по
    # порядку, а не по отдельным подстрокам. Проверка «есть ли где-то на
    # странице 2026», тем более «есть ли где-нибудь Top 3», ничего не
    # говорит о том, что панель утверждает: страница, где 2026 стоит
    # рядом со «Standoff 15», проходит обе молча, и «Top 2» при этом
    # держался на строке «также», где встречается дважды.
    #
    # Порядок — часть проверки, а не её следствие: панель читается от
    # свежего к старому, и две переставленные строки меняют то, что
    # страница говорит о годах. Проверка «есть ли такая тройка среди
    # найденных» такой случай пропускала — обе тройки на месте, переставлены
    # местами, ошибки нет, а панель теперь утверждает Standoff 15 в 2026.
    # Подпись 2024 в самой плитке — «Standoff BRICS»: полное «Standoff
    # Red Team Scenarios» — это 27 знаков моно, и вместе с годом, местом
    # и оформлением плитка просит 267px против 238px полосы на 320px.
    # Флекс не поедет за край — он сожмёт плитку, и перенос упадёт на
    # название площадки: плитка станет 54px против 31px у соседей
    # (замерено в браузере). Полное название не выброшено, а унесено в
    # title того же span — там оно не борется за ширину. И полное
    # название, и короткое закреплены здесь оба: иначе сокращение
    # выглядело бы как опечатка, а не как решение, и через правку
    # атрибута тихо уехало бы в никуда.
    #
    # «Standoff BRICS» — 14 знаков, 118px, плитка просит 233px против
    # 238px полосы. Запас 5px: он есть, но впритык, и «+» в конце уже
    # не влезает (242px). Если подпись снова поедет — сокращать BRICS,
    # а не год и не место.
    expected = (
        ("2026", "Standoff 17", "Top 3", ""),
        ("2025", "Standoff 15", "Top 2", ""),
        ("2024", "Standoff BRICS", "Top 3", "Standoff Red Team Scenarios"),
        ("2023", "Standoff 12", "Top 3", ""),
    )
    # Модификаторы в списках классов допускаются, и на этот раз проверка сама
    # на них наступает: `<li class="place place--new">` и
    # `<span class="place__rank" data-year="2026">` — правки, которые ничего
    # не меняют в том, что панель утверждает, а точный класс их отбрасывал и
    # страница роняла четыре ошибки ни о чём. Та же форма, что у соседних
    # проверок файла (`class="row(?:\s[^"]*)?"` в check_project_icons,
    # `class="block(?:\s[^"]*)?"` для разделов), и по той же причине:
    # `\s` отсекает подставные `class="places"`, а кавычка после класса — нет.
    #
    # title вынимается из того же span, а не ищется по всей строке: иначе
    # полное название 2024 нашлось бы и на соседней строке, и проверка
    # держала бы чужую подпись за свою. Порядок в кортеже —
    # «год → событие → место → полное название», и четвёртая часть пустая
    # у мест, где сокращения нет.
    rows = re.findall(r'<li class="place(?:\s[^"]*)?">(.*?)</li>', block, re.DOTALL)
    got = []
    for row in rows:
        triple = re.findall(
            r'<span class="place__(?:year|event|rank)"[^>]*>([^<]*)</span>', row
        )
        title = re.search(
            r'<span class="place__event"[^>]*\stitle="([^"]*)"', row
        )
        got.append(tuple(triple) + (title.group(1) if title else "",))

    # Сообщение собирается из частей, а не склеивается по индексу: строка
    # может быть короче ожидаемой (тогда частей не хватит) или длиннее её
    # (тогда лишняя часть — это уже другая ошибка, и печатать её в чужом
    # сообщении нельзя). «ничего» печатается только когда строки нет вовсе.
    def place_repr(parts: tuple[str, ...]) -> str:
        if len(parts) < 3:
            return "ничего"
        shown = " · ".join(parts[:3])
        if len(parts) > 3 and parts[3]:
            shown += f" (полное название {parts[3]!r})"
        return shown

    for i, want in enumerate(expected):
        have = got[i] if i < len(got) else ()
        if have != want:
            errors.append(
                f"best of: мест №{i + 1} ждёт {place_repr(want)}, "
                f"а стоит {place_repr(have)} — порядок строк и тройки "
                "«год → событие → место» обязаны совпадать"
            )
    # Номер лишнего места — его собственный индекс, а не хвост: сообщение
    # обязано указывать на строку, которую добавили, иначе виновным читается
    # последнее из ожидаемых мест.
    for i in range(len(expected), len(got)):
        errors.append(
            f"best of: мест №{i + 1} лишнее: {place_repr(got[i])} — "
            "в панели четыре выступления Standoff"
        )

    # Строка «также» проверяется ЦЕЛИКОМ и по порядку, а не по подстрокам.
    # Три проверки REQUIRED_TEXT на VKACTF / KubanCTF / Cybercoliseum держали
    # три имени из четырёх, и страница, где из фоновых мест осталось три,
    # проходила насквозь: спека §3.5 называет четыре выступления, и
    # четвёртое — HTB — выпало молча, потому что «HackTheBox» из
    # REQUIRED_TEXT убрали решением Task 7, а замену не закрепили.
    #
    # Проверка именно строки, а не каждого имени по отдельности, потому
    # что поодиночке не видно ни полноты, ни порядка: строка, где HTB
    # уехал в конец, проходит «есть ли VKACTF» так же спокойно, как
    # строка, где его нет вовсе. Форма — та же, что у троек выше: одно
    # правило на единицу смысла, а не список подстрок.
    also = re.search(r'<p class="also">\s*также:\s*(.*?)</p>', block, re.DOTALL)
    if also is None:
        errors.append(
            "best of: нет приглушённой строки «также» — фоновые места "
            "обязаны остаться видимыми, пусть и одной строкой"
        )
    else:
        got_also = [part.strip() for part in also.group(1).split("·")]
        # Пустые хвосты и лишние разделители не должны проходить как
        # «место №5», поэтому пустые части отбрасываются молча, а их
        # наличие уже ничего не меняет: ниже сверяется ровно четыре.
        got_also = [p for p in got_also if p]
        if got_also != list(ALSO_PLACES):
            errors.append(
                "best of: фоновые места — "
                + (" · ".join(got_also) if got_also else "ничего")
                + f", а ожидается {' · '.join(ALSO_PLACES)} — спека §3.5 "
                "называет четыре выступления, и порядок в строке тоже "
                "часть договора"
            )

    notes.append("Best of: Standoff в одной панели, остальное фоном")


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


# Порядок блоков, в котором страница обязана читаться: одна колонка в
# порядке чтения. Один и тот же список обслуживает и бумагу, и телефон —
# обе раскладки обязаны совпадать с порядком секций в разметке (hero,
# about, projects, best, elsewhere), и на обеих best стоит третьим, а не
# жмётся под низ, как это делает широкая раскладка с двумя рядами правой
# колонки. Одна константа вместо двух ещё и потому, что расхождение
# между ними — это ровно тот дефект, который проверка ниже и ловит.
READING_ORDER = ("about", "projects", "best", "elsewhere")

# Имя оставлено прежним: на бумагу ссылается половина сообщений, и
# переименование одной константы ничего бы не прояснило.
PRINT_AREAS = READING_ORDER


def check_print_styles() -> None:
    """Печать визитки — реальный сценарий, а не заморочка.

    Тёмный фон на печати съедает тонер, а текст, нарисованный --muted, при
    выключенных фонах может оказаться белым на белом. Поэтому @media print
    обязан подставлять светлые значения явно.

    Раскладка на листе проверяется разбором строк областей, а не поиском
    подстроки: «grid-template-areas» встречается и в комментарии, и в
    раскладке, повторяющей широкую, — и обе подмены проходят проверку
    присутствия, хотя на листе панель занимает половину ширины или блоки
    идут не в том порядке. Об этом же говорит договорённость
    check_two_column_layout: судить надо о форме раскладки, а не о том,
    что строка объявлена.
    """
    css = read_if_present("css/style.css")
    if css is None:
        return
    m = re.search(r"@media\s*print\s*\{(.*)\}\s*$", css, re.DOTALL)
    if m is None:
        errors.append("css/style.css: нет @media print")
        return
    # Комментарии вырезаются до всех разборов: иначе пояснение «области
    # названы явно» засчиталось бы за само объявление — ровно тот случай,
    # ради которого комментарии снимает _grid_area_rows.
    block = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    for needed in ("--bg", "--text", "--muted"):
        if needed not in block:
            errors.append(f"@media print не переопределяет {needed} — печать может выйти нечитаемой")

    # Одна колонка в порядке чтения. Панель projects на двух колонках занимает
    # на листе половину ширины, а подписи в две строки превратятся в обрезку.
    # Визитку печатают — из неё делают визитки, поэтому раскладка обязана
    # сложиться, а порядок блоков на бумаге обязан совпадать с порядком чтения.
    rows = _grid_area_rows(block)
    if not rows:
        errors.append(
            "@media print: области не схлопнуты в одну колонку — блок не "
            "объявляет grid-template-areas, и main остаётся двухколоночным"
        )
    elif fat_row := next((r for r in rows if len(r) != 1), None):
        errors.append(
            "@media print: области не схлопнуты в одну колонку — строка "
            f"{' '.join(fat_row)!r} занимает {len(fat_row)} ячейки, на листе "
            "панель проектов уедет в половину ширины"
        )
    elif tuple(row[0] for row in rows) != PRINT_AREAS:
        got = " ".join(row[0] for row in rows)
        errors.append(
            f"@media print: порядок областей на листе — {got}, а читать надо "
            f"{' '.join(PRINT_AREAS)}: на бумаге блоки идут сверху вниз, "
            "и best стоит третьим, а не под низом"
        )
    elif not re.search(r"grid-template-columns\s*:\s*1fr\s*;", block):
        errors.append(
            "@media print: области схлопнуты, но колонка не схлопнута — "
            "нужен grid-template-columns: 1fr, иначе треки остаются 1fr 1.25fr"
        )

    # Скруглённые углы панели держатся на overflow: hidden; на бумаге он
    # обрезает содержимое строк по скруглённому углу. Запятая после имени
    # в регулярке — на случай, если владелец снова соберёт снятие угла и
    # скругления в один селекторный список, поставив .panel не первым.
    if not re.search(r"\.panel\s*[,{][^}]*overflow", block):
        errors.append(
            "@media print: у .panel не снят overflow — скруглённые углы "
            "обрежут содержимое на бумаге"
        )

    # Отступ сверху у best — дыра в 103px на A4, и ни один прогон её не
    # видел: поле `margin` не читает ни одна из трёх проверок, а блок
    # 640px, который этот отступ снимает, на A4 (794px) и Letter (816px)
    # не действует — медиа-условия не складываются. Поэтому проверяется
    # не «сколько получится на A4» (это уже измерение, а не инвариант),
    # а сам факт снятия: в печатном блоке обязано быть правило, которое
    # обнуляет block-start у best.
    #
    # Ищется любая из форм снятия — margin-block-start, margin-block
    # или margin, — потому что автору всё равно, какой именно из них
    # написан, а проверке не всё равно лишь одно: сверху ноль. Порядок
    # поиска от длинной формы к короткой важен: `margin: 0` не должно
    # удовлетворять проверку раньше, чем `margin-block-start: 0`, если
    # в правиле объявлены обе.
    if not re.search(
        r"#best\b[^{}]*\{[^{}]*margin(?:-block)?(?:-start)?\s*:\s*(?:0|0px|0rem)\b",
        block,
    ):
        errors.append(
            "@media print: у #best не снят margin-block-start — печатный блок "
            "не попадает под @media 640px, и над панелью Standoff останется "
            "дыра в --space-section (79px на A4) поверх margin-block-end "
            "у projects"
        )

    # Адрес у каждой ссылки печатается (a[href]::after ниже), а .chip
    # объявлен white-space: nowrap. На A4 это проходит случайно, на A5
    # самый широкий чип (max.ru/join/…) проецируется в ~665px против
    # 527px полосы и на 85-миллиметровой визитке — в 289px, то есть
    # вылезает за поля. Печать — реальный сценарий (визитку печатают),
    # и на превью это не видно: страница выглядит рабочей, вылезает
    # только бумага.
    #
    # Требуется снятие nowrap, а не только overflow-wrap: в адресе нет
    # пробелов, поэтому одного wrap без white-space: normal недостаточно.
    # Ищется правило с .chip, а не подстрока `white-space` во всём
    # блоке — иначе выключатель отступов сойдёт за чип.
    if not re.search(
        r"\.chip\b[^{}]*\{[^{}]*white-space\s*:\s*(?:normal|initial|unset|pre-wrap|wrap)\b",
        block,
    ):
        errors.append(
            "@media print: у .chip не снят white-space: nowrap — адрес в "
            "конце ссылки не влезает ни на A5, ни на визитку 85 мм, и "
            "переполосы не будет видно до первого отпечатка"
        )

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


def _srgb_channel(c: float) -> float:
    """Канал в линейном пространстве по формуле WCAG 2.x."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    """Относительная яркость по WCAG 2.x."""
    h = hex_color.strip().lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)


def _contrast(a: str, b: str) -> float:
    """Коэффициент контраста двух цветов (WCAG 2.x)."""
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# Пары (цвет текста, фон, минимум). Текст — 4.5:1 (WCAG 1.4.3), графика — 3:1
# (WCAG 1.4.11). Список проверяется в обеих темах: тёмная берётся из :root,
# светлая — из :root с наложенным [data-theme='light'].
#
# Список покрывает каждое сочетание, которым страница реально рисует:
# --accent и --signal на всех трёх подложках, --tg и --brand-ink и на
# плитке, и на карточке (знак в пилюле лежит прямо на фоне карточки),
# --text и --muted на всех трёх. Пропущенная пара — это не «сработает
# позже», а тихая дыра: первая же правка палитры проходит незамеченной.
#
# Подложка вложенных блоков — --surface, а не --bg: подписи строк
# панели projects рисуются --muted, а знаки на них --accent, и пары с
# --surface обязаны стоять в списке отдельно от пар с --bg. Обе уже там
# есть, повторно добавлять не нужно: дубликат проверяет то же сочетание
# второй раз и только засоряет список.
CONTRAST_PAIRS = (
    # Текст на фоне
    ("--text", "--bg", 4.5),
    ("--text", "--surface", 4.5),
    # Плитки мест в панели Standoff лежат на --surface-2 и рисуются
    # --text: подложка вложена в панель на один уровень глубже, чем у
    # строк projects, и пара с --surface её не покрывает.
    ("--text", "--surface-2", 4.5),
    ("--text-strong", "--bg", 4.5),
    # Подпись кнопки в шапке. Пара была пропущена, пока Telegram был
    # акцентным: на нём текст был --bg, и подпись --text-strong на --surface
    # рисовала ровно одна кнопка — GitHub. 2026-10-09 обе кнопки стали
    # одинаковыми, и пропуск перестал быть безобидным: сменить
    # --text-strong на что-то менее контрастное, и подписи обеих кнопок
    # поехали бы молча. Замерено: 16.86 в тёмной, 18.81 в светлой.
    ("--text-strong", "--surface", 4.5),
    ("--muted", "--bg", 4.5),
    ("--muted", "--surface", 4.5),
    ("--muted", "--surface-2", 4.5),
    # Акцент: промпт, подчёркивания заголовков, знаки по умолчанию
    ("--accent", "--bg", 4.5),
    ("--accent", "--surface", 4.5),
    ("--accent", "--surface-2", 4.5),
    # Зелёный микро-сигнал, в том числе на плитке знака при ховере
    ("--signal", "--bg", 4.5),
    ("--signal", "--surface", 4.5),
    ("--signal", "--surface-2", 4.5),
    # Фирменные знаки: и на плитке, и прямо на фоне карточки и пилюли
    ("--tg", "--surface", 3.0),
    ("--tg", "--surface-2", 3.0),
    ("--brand-ink", "--surface", 3.0),
    ("--brand-ink", "--surface-2", 3.0),
    # Золото ушло вместе с раздельными кубками: Standoff собран в одну панель
    # без графики, первые места помечены текстом Top 1..Top 4, а отдельный
    # цвет для них больше не нужен.
    #
    # Пары (--tg, --accent) здесь НЕТ и по другой, чем была, причине.
    # Пока кнопка Telegram была акцентной, знак на ней наследовал её цвет,
    # а не --tg (1.26:1 в светлой теме и 1.41:1 в тёмной — глиф главного
    # перехода на канал просто исчезал), и пара была недостижимой: сама по
    # себе она падала бы, обвиняя страницу в невозможном сочетании.
    # 2026-10-09 владелец убрал акцентную кнопку целиком («не надо ее синим
    # выделять»), .pill--accent и .pill__icon--tg удалены, и сочетания
    # --tg на --accent на странице больше не существует вовсе — не как
    # недостижимое, а как ненарисованное. Пара (--accent, --bg) ниже
    # остаётся настоящей: --accent красит решётку заголовков, подчёркивания
    # и знаки по умолчанию, всё это лежит на фоне.
    #
    # Пары (--tg, --accent-soft) здесь нет по другой причине, и она
    # техническая: --accent-soft это rgba(), а сравнение ниже пропускает
    # любое значение, не начинающееся с «#». Пара с ним была бы
    # vacuously верной в обеих темах — проверка молча соглашалась бы с
    # чем угодно. Настоящая подложка знака — это композиция --accent-soft
    # поверх фона строки, и именно поэтому пара в список не годится: фон
    # строки меняется (ховер даёт --surface-2), так что подложек две, а
    # проверить их обе проверка не умеет. На ховере плитка знака к тому же
    # остаётся на --accent-soft: `.row--accent .row__icon` с (0,2,0)
    # перебивает `.row__icon` с (0,1,0). Числа на 8-битном композите
    # (round каналов перед подсчётом):
    #   тёмная   --accent-soft 0.14 на --surface   #0F1620 = #152D3E -> 4.71:1
    #   тёмная   --accent-soft 0.14 на --surface-2 #151E2A = #1A3447 -> 4.28:1
    #   светлая  --accent-soft 0.10 на --surface   #FFFFFF = #E6F0F6 -> 4.06:1
    #   светлая  --accent-soft 0.10 на --surface-2 #EDF2F7 = #D6E4EE -> 3.62:1
    # Все четыре выше порога графики 3:1. Держат знак канала существующие
    # пары (--tg, --surface) и (--tg, --surface-2) — обе настоящие.
)


def check_contrast_pairs() -> None:
    """Все смысловые цветовые пары держат порог WCAG в обеих темах.

    Контраст считается по формуле, а не на глаз: упал ли он — видно только
    числом. Новые акценты (голубый --accent, зелёный --signal) проверяются
    здесь именно поэтому.
    """
    tokens = read("css/tokens.css")
    if tokens is None:
        return

    root_m = re.search(r":root\s*\{(.*?)\n\}", tokens, re.DOTALL)
    light_m = re.search(r"\[data-theme='light'\]\s*\{(.*?)\n\}", tokens, re.DOTALL)
    if root_m is None or light_m is None:
        errors.append("tokens.css: не найден :root или [data-theme='light']")
        return

    def block_of(body: str) -> dict[str, str]:
        # Комментарии вырезаются обязательно. Объяснение про --accent:
        # внутри комментария выглядит для регулярки как объявление, а
        # значение тянется до следующей «;» — то есть до следующего
        # токена, и тот молча пропадает из палитры. На служебном токене
        # это молчание выглядит как «токен не найден», и виноват оказывается
        # тот, кто его проверяет, а не тот, кто писал CSS.
        clean = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", clean))

    dark = block_of(root_m.group(1))
    light = {**dark, **block_of(light_m.group(1))}

    for theme_name, pal in (("тёмная", dark), ("светлая", light)):
        for fg, bg, need in CONTRAST_PAIRS:
            fv, bv = pal.get(fg), pal.get(bg)
            if fv is None or bv is None:
                errors.append(
                    f"контраст {theme_name}: токен {fg if fv is None else bg} не найден"
                )
                continue
            if not fv.startswith("#") or not bv.startswith("#"):
                continue
            ratio = _contrast(fv, bv)
            if ratio < need:
                errors.append(
                    f"контраст {theme_name}: {fg} ({fv.strip()}) на {bg} "
                    f"({bv.strip()}) = {ratio:.2f}, нужно ≥ {need}"
                )
    notes.append("Контраст-пары: проверены в обеих темах")


def check_link_placement() -> None:
    """Ссылки живут там, куда их поместили, а не где попалось.

    Спека §3.4: переход на канал — главная причина прийти, поэтому
    t.me/wh_lab обязан быть и в шапке, и первой карточкой projects.
    Standoff 365 остаётся ссылкой внутри факта в about.
    """
    html = read_if_present("index.html")
    if html is None:
        return

    # Модификаторы в списке классов секции допускаются — та же причина,
    # что в check_project_icons: у projects есть `block--panel`.
    def section(name: str) -> str | None:
        m = re.search(rf'<section class="block(?:\s[^"]*)?" id="{name}">(.*?)</section>', html, re.DOTALL)
        if m is None:
            errors.append(f"index.html: не найден раздел {name}")
            return None
        return m.group(1)

    about = section("about")
    projects = section("projects")
    elsewhere = section("elsewhere")
    if about is None or projects is None or elsewhere is None:
        return

    if "standoff365.com/profile/Exited3n/" not in about:
        errors.append("about: нет ссылки на профиль Standoff 365 — факт должен быть кликабельным")
    if about.count("t.me/wh_lab"):
        errors.append("about: ссылка на канал вернулась — канал живёт в шапке и в projects")

    if "t.me/wh_lab" not in projects:
        errors.append("projects: нет карточки Whitehat Lab — главный переход на канал исчез")

    # Дубль ссылки обязателен, но пара «где именно» у каждой своя, и
    # требовать обе в elsewhere было бы противоречием: канал живёт в
    # шапке и в projects, а не в ленте ссылок, — ровно это и написано в
    # докстринге выше. Поэтому elsewhere проверяется только у той
    # ссылки, которая по контракту там стоит, а обе обязаны
    # встретиться на странице дважды.
    if "github.com/akhomlyuk" not in elsewhere:
        errors.append("elsewhere: нет ссылки github.com/akhomlyuk")

    # Шапка проверяется отдельно от счёта вхождений. Счёт «два раза на
    # странице» ничего не говорит о том, где именно: перенос пилюли
    # Telegram из header в footer оставил бы счёт на месте и прошёл бы
    # прогон, хотя главный переход на канал ушёл с первого экрана.
    hero = re.search(r'<header class="hero">(.*?)</header>', html, re.DOTALL)
    if hero is None:
        errors.append("index.html: не найден <header class=\"hero\">")
    else:
        for url in ("t.me/wh_lab", "github.com/akhomlyuk"):
            if url not in hero.group(1):
                errors.append(f"hero: нет ссылки {url} — переход с первого экрана пропал")

    for url, where in (
        ("t.me/wh_lab", "в шапке и в projects"),
        ("github.com/akhomlyuk", "в шапке и в ленте ссылок"),
    ):
        if html.count(url) < 2:
            errors.append(f"index.html: {url} должна быть и {where}")

    notes.append("Ссылки: шапка, about, projects и elsewhere проверены")


def check_chips() -> None:
    """Лента ссылок — чипы по ширине содержимого, и у каждого своя иконка.

    Сетка фиксированной ширины ломалась бы при добавлении пятой ссылки:
    владелец прямо сказал, что будет её добавлять. Чипы на flex-wrap
    занимают ровно свою ширину, а новая ссылка сама встаёт в конец строки.
    """
    html = read_if_present("index.html")
    css = read_if_present("css/style.css")
    if html is None:
        return

    # Та же форма, что в остальных местах файла: `elsewhere` сегодня без
    # модификаторов и точное `class="block"` срабатывает, но владелец
    # вправе повесить на него класс так же, как повесил `block--panel` на
    # projects, — и проверка молча перестала бы находить раздел.
    m = re.search(r'<section class="block(?:\s[^"]*)?" id="elsewhere">(.*?)</section>', html, re.DOTALL)
    if m is None:
        errors.append("index.html: не найден раздел elsewhere")
        return
    block = m.group(1)

    chips = re.findall(r'<a class="chip".*?</a>', block, re.S)
    if len(chips) < 4:
        errors.append(f"elsewhere: чипов {len(chips)}, ожидалось минимум 4")
    for c in chips:
        if "chip__icon" not in c:
            errors.append("elsewhere: чип без иконки")

    if css is not None:
        chips_rule = re.search(r"\.chips\s*\{(.*?)\}", css, re.DOTALL)
        if chips_rule is None:
            errors.append("style.css: нет правила .chips")
        elif "flex-wrap" not in chips_rule.group(1):
            errors.append("style.css: .chips без flex-wrap — длинная ссылка не перенесётся, а новая сломает строку")

    notes.append(f"Чипов в ленте ссылок: {len(chips)}")


def check_footer() -> None:
    """Подвал по спеке §3: копирайт + переключатель темы.

    Переключатель переезжает из header в footer — если переезд забудут
    совершить, кнопка темы потеряется, а страница останется «рабочей».
    """
    html = read_if_present("index.html")
    if html is None:
        return
    m = re.search(r"<footer\b.*?</footer>", html, re.DOTALL)
    if m is None:
        errors.append("index.html: нет <footer> — по спеке в подвале копирайт и переключатель темы")
        return
    footer = m.group(0)
    if "data-theme-toggle" not in footer:
        errors.append("footer: нет переключателя темы — он переехал сюда из header")
    # Копирайт принимается и символом, и сущностью: &copy; в исходнике
    # выглядит для проверки иначе, чем рисунок на странице, и ругаться
    # на корректный HTML было бы проверкой формы записи, а не намерения.
    if "©" not in footer and "&copy;" not in footer:
        errors.append("footer: нет копирайта")
    notes.append("Footer: найден, переключатель на месте")


def _grid_area_rows(css: str) -> list[list[str]]:
    """Строки всех grid-template-areas из куска CSS, как списки имён.

    Вид кавычки не важен: страница пишет области в одинарных, но
    проверка не должна ломаться от их смены на двойные — регулярка
    принимает и те, и другие. Объявление обрывается точкой с запятой, а
    не переводом строки, поэтому многострочная запись разбирается целиком.

    Комментарии вырезаются: `grid-template-areas` в пояснении выглядит
    для регулярки как объявление и тянет за собой следующую строку
    области (та же причина, что в block_of в check_contrast_pairs).
    """
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rows: list[list[str]] = []
    for decl in re.findall(r"grid-template-areas\s*:(.*?);", clean, re.DOTALL):
        rows.extend(row.split() for row in re.findall(r"['\"]([^'\"]*)['\"]", decl))
    return rows


def _wide_layout_css(css: str) -> str:
    """Кусок CSS без содержимого @media — то, что рисуется без оговорок.

    Широкая раскладка интересует проверку ровно одна: та, что действует
    без медиа-условий. Всё, что лежит внутри @media, — откаты, и области
    там одноимённые с широкими: @media (max-width: 640px) перестраивает
    их в одну колонку, @media print схлопывает страницу на бумагу. Если
    считать строки по всему файлу, то с появлением первого же отката
    панель projects начинает занимать «три ряда из семи», и проверка
    роняет корректную раскладку — виня широкие области в том, что они
    объявлены ещё и там.

    Вырезается содержимое ЛЮБОГО @media, а не только 640px: список
    откатов будет расти, а проверка — нет. Вложенные медиа-блоки (@media
    внутри @media) не встречаются и не ожидаются; на их месте цикл
    вырежет внешний блок целиком, вместе со вложенным, — а это ровно то
    поведение, которое нужно: лишние области не попадут в счёт.

    Побочный плюс: комментарии и правила @media остаются в файле, и
    объявление grid-template-areas внутри вложенного селектора не может
    подделать широкую раскладку.
    """
    out = css
    while True:
        m = re.search(r"@media\b[^{]*\{", out)
        if m is None:
            return out
        # Идём по балансу скобок от открытой до её парной.
        depth = 1
        i = m.end()
        while i < len(out) and depth:
            if out[i] == "{":
                depth += 1
            elif out[i] == "}":
                depth -= 1
            i += 1
        out = out[:m.start()] + out[i:]


def check_two_column_layout() -> None:
    """Две колонки выше 640px и одна ниже — по спеке §2.

    Плотность была главной болью владельца, но после 2026-10-09 жалоба
    сменилась на «всё в одну колонку, огромные марджины, ширину не на что
    деть». Возврат grid без медиа-отката при этом выглядел бы рабочей
    страницей: на телефоне правая колонка просто уехала бы за край.

    Эта проверка — приёмка Task 4, поэтому судит она о раскладке, а не о
    наличии строк в файле: «области перестроены» означает, что внутри
    @media каждая строка области состоит из одного имени, а колонка
    схлопнута до одной. Области, повторяющие широкую раскладку, и
    «перестроенные» области при оставшихся 1fr 1.25fr дают телефону
    либо две колонки, либо трек шириной во весь экран — и обе ошибки
    раньше проходили молча.

    ДОГОВОРЁННОСТЬ С TASK 4 (это его приёмка, а не украшение):
    внутри @media (max-width: 640px) обязаны быть
      grid-template-areas: 'about' 'projects' 'best' 'elsewhere'
                          — одним именем в строке, четыре строки
                            И В ЭТОМ ПОРЯДКЕ;
      grid-template-columns: 1fr;   — 1fr или none, но не 1fr 1.25fr.
    Порядок — часть договора, а не его следствие, и именно поэтому
    раньше он здесь не стоял: пока проверка спрашивала только «одна ли
    ячейка в строке», она молча пропускала ЛЮБУЮ перестановку четырёх
    имён, включая ту, что стоит здесь. Противоположное рассуждение
    («невалидные области делают колонки невалидными») этой мутации не
    касается: 'about' 'elsewhere' 'projects' 'best' — раскладка вполне
    валидная, просто projects уезжает под три ссылки, и ради этого
    отката он и поднят над elsewhere в разметке.

    Откат в @media (max-width: 640px) проверяется отдельно от широкой
    раскладки: широкие области читаются из файла за вычетом содержимого
    ЛЮБОГО @media (см. _wide_layout_css), поэтому добавление отката —
    печать в Task 8, — не сдвинет счёт строк в широкой половине.
    """
    css = read_if_present("css/style.css")
    html = read_if_present("index.html")
    if css is None:
        return

    if "grid-template-areas" not in css:
        errors.append("style.css: нет grid-template-areas — раскладка §2 не собрана")
        return

    media = re.search(r"@media\s*\(max-width:\s*640px\)\s*\{(.*?)\n\}", css, re.DOTALL)

    # Широкая раскладка — только то, что рисуется без медиа-условий.
    # Откаты (@media 640px в Task 4, @media print в Task 8) объявляют те
    # же имена областей, и в общем счёте они выглядели бы как «панель
    # занимает три ряда из семи»: проверка роняла бы правильную страницу
    # и винила широкие области в том, что они объявлены ещё где-то.
    rows = _grid_area_rows(_wide_layout_css(css))
    wide_ok = True

    names = {name for row in rows for name in row}
    for area in ("about", "projects", "elsewhere", "best"):
        if area not in names:
            wide_ok = False
            errors.append(f"style.css: область {area!r} не объявлена в grid-template-areas")

    # Панель обязана стоять в обоих рядах правой колонки, иначе about и
    # elsewhere займут два ряда, а панель окажется в собственном. Считаются
    # строки области, а не ищется объявление grid-area: при раскладке
    # 'elsewhere about' панель уезжает в третий ряд, страница остаётся
    # рабочей, а grid-area: projects на месте — и проверка молчит.
    spanned = sum("projects" in row for row in rows)
    if spanned != 2:
        wide_ok = False
        errors.append(
            "style.css: projects не тянется на обе строки правой колонки — "
            f"ожидалось два ряда с projects, в области их {spanned} из {len(rows)}"
        )

    # grid-area нужен отдельно от областей: сами области только называют
    # ячейки, а без явного закрепления #projects авторазмещение положило бы
    # панель в первую свободную — левую — ячейку.
    if not re.search(r"grid-area:\s*projects", css):
        wide_ok = False
        errors.append("style.css: нет grid-area: projects — панель не закреплена в правой колонке")

    # Медиа-откат: без него телефон получает две колонки. Договорённость с
    # Task 4: внутри @media — grid-template-areas одним именом в строке и
    # grid-template-columns: 1fr (или none).
    narrow_ok = False
    if media is None:
        errors.append("style.css: нет @media (max-width: 640px) — на телефоне колонки не схлопнутся")
    else:
        block = media.group(1)
        narrow_rows = _grid_area_rows(block)
        if not narrow_rows:
            errors.append("@media 640px: области не перестроены в одну колонку")
        elif fat_row := next((r for r in narrow_rows if len(r) != 1), None):
            errors.append(
                "@media 640px: области не перестроены в одну колонку — строка "
                f"{' '.join(fat_row)!r} занимает {len(fat_row)} ячейки"
            )
        elif tuple(row[0] for row in narrow_rows) != READING_ORDER:
            got = " ".join(row[0] for row in narrow_rows)
            errors.append(
                f"@media 640px: порядок областей на телефоне — {got}, а "
                f"читать надо {' '.join(READING_ORDER)}: одна колонка в "
                "порядке чтения, и projects не должен уезжать под "
                "четыре ссылки — до них должен быть один прокрут"
            )
        elif not re.search(r"grid-template-columns\s*:\s*(?:none|1fr)\s*;", block):
            errors.append(
                "@media 640px: области перестроены, но колонка не схлопнута — "
                "нужен grid-template-columns: 1fr"
            )
        else:
            narrow_ok = True

    if html is not None and html.count('id="projects"') != 1:
        errors.append('index.html: раздел projects должен быть ровно один')

    # Заметка — только когда сошлись обе половины, широкая и узкая. Без
    # этого прогон печатал «медиа-откат на месте» рядом с «ОШИБКА:
    # @media 640px: области не перестроены», а «области объявлены» — рядом
    # с «область 'best' не объявлена»: отмашка, которой не было.
    if wide_ok and narrow_ok:
        notes.append("Раскладка: области объявлены, медиа-откат на месте")


def check_hero() -> None:
    """Hero по спеке §5: строка $ whoami, курсор, две CTA-ссылки.

    Дублирование hero CTA + elsewhere разрешено спекой §7 — поэтому
    каждая из двух ссылок обязана встретиться на странице дважды.
    """
    html = read_if_present("index.html")
    if html is None:
        return
    if "$ whoami" not in html:
        errors.append("index.html: нет строки '$ whoami' над именем в hero")
    # Мигающий курсор убран решением владельца 2026-10-09: анимация
    # мигала вопреки просьбе и раздражала. Проверка остаётся, чтобы он
    # не вернулся вместе с правкой оформления hero.
    if "hero__cursor" in html or "cursor-blink" in html:
        errors.append("index.html: курсор в строке '$ whoami' вернулся — он убран по решению владельца")
    # Дубль: факт «с 2010 года» живёт в about, в hero повторять его незачем.
    if "10+ лет в информационной безопасности" in html:
        errors.append(
            "index.html: строка «10+ лет в информационной безопасности» вернулась "
            "в hero — она дублирует факт из about"
        )
    # Ссылка на профиль Standoff уехала в about, из ленты ссылок убрана.
    for url, where in (
        ("https://github.com/akhomlyuk", "hero-CTA и elsewhere"),
    ):
        if html.count(url) < 2:
            errors.append(f"index.html: {url} должна быть в {where}")
    notes.append("Hero: whoami, отсутствие курсора и CTA проверены")


def check_reduced_motion() -> None:
    """Движение при вестибулярных нарушениях — помеха, а не украшение.

    Проверка спрашивает саму страницу, а не сверяется с заранее
    заданным текстом правила. Раньше она требовала литерал `transform: none`,
    и подъём на ховере давал ей повод. Редизайн 2026-10-09 убрал подъём
    вместе с круглыми карточками, и требование начало охранять пустоту: CSS
    держал `transform: none` для селекторов, которые не объявляют никакого
    transform, а прогон печатал «подъём отключается» про подъём, которого
    нет. Теперь transform требуется гасить только если он где-то на странице
    реально объявлен, а заметка говорит о том, что на странице есть.
    """
    css = read_if_present("css/style.css")
    if css is None:
        return
    m = re.search(
        r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\n\}", css, re.DOTALL
    )
    if m is None:
        errors.append("style.css: нет @media (prefers-reduced-motion: reduce)")
        return
    block = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)

    # Всё вне блока отката: transform, который надо погасить, может быть
    # объявлен где угодно — и до медиа-блока, и после.
    outside = re.sub(r"/\*.*?\*/", "", css[: m.start()] + css[m.end() :], flags=re.DOTALL)

    # animation: none больше не требуется: мигающий курсор убран
    # решением владельца, анимации на странице не осталось. Проверять
    # нечего — требовало бы только выдуманного правила в CSS.
    if re.search(r"animation\s*:[^;}]*\binfinite", block):
        errors.append("reduced-motion: бесконечная анимация не отключается")

    # (?<![\w-]) отсекает -webkit-transform и transform-like классы.
    has_transform = re.search(r"(?<![\w-])transform\s*:", outside) is not None
    has_transition = re.search(r"(?<![\w-])transition\s*:\s*(?!none)", outside) is not None

    if has_transform and "transform: none" not in block:
        errors.append(
            "reduced-motion: на странице объявлен transform, но он не отключается — "
            "в блоке отката нет transform: none"
        )
    if has_transition and "transition: none" not in block:
        errors.append(
            "reduced-motion: на странице объявлены переходы, но они не отключаются — "
            "в блоке отката нет transition: none"
        )

    if has_transform:
        notes.append("Reduced-motion: transform и переходы отключаются, анимаций нет")
    else:
        notes.append("Reduced-motion: transform на странице нет, отключаются переходы")


def check_no_literals_outside_tokens() -> None:
    """Мимо токенов — ни цвета, ни rem. Правило заявлено шапкой style.css.

    Шапка файла обещает: «ни одного цвета и ни одного rem мими токенов,
    иначе страница перестанет переключаться темой целиком». До сих пор
    обещание никто не проверял: literal `#123456`, вписанный в любое
    правило, проходил все три набора, и тема переставала переключаться
    для одного элемента — то есть ровно тот полом, ради которого
    токены и заведены.

    Область проверки — файл, который правит форму, а не tokens.css:
    там литералы и есть исходник. Границы исключений выбраны по
    содержимому файла, а не на глаз, и каждая объяснена в коде:

      * @media print — единственное место, где литералы законны: печать
        подставляет бумажную палитру поверх экранной, и --muted, --border
        и прочие на белом обязаны стать конкретными значениями. Это
        подстановка токенов, а не обход их.
      * .wrapper — `min(var(--wrapper-max), 100% - 2rem)`. Единственный
        rem мимо шкалы отступов: 2rem здесь не отступ, а запас полей
        от края окна, и он не переключается темой.
      * font-size и две fluid-шкалы clamp() в нём — единственные
        литералы размеров в файле, и шапка называет их своими же
        словами. Остальные font-size — rem, но это размеры текста,
        а не отступы: они не часть шкалы --space-*.

    Комментарии снимаются ДО подсчёта: иначе hex в пояснении про
    печатные фирменные цвета (--tg даёт 2.68:1 на белом) сошёл бы за
    литерал на странице.
    """
    css = read_if_present("css/style.css")
    if css is None:
        return
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    # Печать вырезается целиком, а не по строкам: @media print —
    # вложенный блок, и его содержимое вырезается по балансу скобок,
    # как в _wide_layout_css, иначе литералы палитры печати попали бы
    # в счёт.
    screen = _wide_layout_css(clean)

    # Ширина страницы: rem в .wrapper — запас полей, а не отступ.
    screen = re.sub(r"\.wrapper\s*\{[^}]*\}", "", screen)

    for match in re.finditer(
        r"(#[0-9A-Fa-f]{3,8}\b|\b(?:rgba?|hsla?)\([^)]*\)|"
        r"(?<![\w-])(?:margin|padding|gap|row-gap|column-gap|inset|top|"
        r"left|right|bottom)\s*:[^;{}]*[\d.]rem)",
        screen,
    ):
        found = match.group(0)
        line = screen[: match.start()].count("\n") + 1
        if found.startswith("#") or "(" in found:
            errors.append(
                f"style.css:{line}: литеральный цвет {found!r} мимо токенов — "
                "страница перестанет переключаться темой целиком "
                "(на @media print палитра бумаги — исключение)"
            )
        else:
            errors.append(
                f"style.css:{line}: {found.strip()!r} — отступ в rem мимо "
                "шкалы --space-*; в файле остались только font-size и "
                "100% - 2rem у .wrapper"
            )

    notes.append("Литералы мимо токенов: нет (вне @media print)")


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
        # Комментарии вырезаются: «--accent:» в пояснении выглядит для
        # регулярки как объявление и съедает следующий токен (см.
        # block_of в check_contrast_pairs).
        clean = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
        return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", clean))

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


def check_og_image_fresh() -> None:
    """Превью для соцсетей обязано собираться из текущей палитры.

    Картинка og:image была сделана руками один раз и с тех пор жила
    бинарём: правки страницы её не трогали, и к моменту редизайна на ней
    остались зелёный `$` из удалённой эстетики и строка «10+ лет в
    информационной безопасности», которой на странице уже нет. Скрипт
    tools/og_image.py закрывает эту дыру, но только если им пользуются —
    поэтому здесь превью пересобирается и сверяется байт в байт.

    Рендер требует Edge и Pillow, которых на машине проверки может не
    быть (например, в CI на Linux). Тогда проверка молча пропускается и
    говорит об этом: требовать браузер ради ассетов — значит сделать
    verify.py непроходимым на половине машин.
    """
    target = ROOT / "static" / "ogimage.webp"
    script = ROOT / "tools" / "og_image.py"
    if not script.exists():
        errors.append("tools/og_image.py отсутствует — превью нечем пересобрать")
        return
    if not target.exists():
        return  # существование файла проверяет check_meta

    try:
        from PIL import features  # noqa: F401
    except ImportError:
        notes.append("Превью: Pillow не установлен, проверка свежести пропущена")
        return
    if not features.check("webp"):
        notes.append("Превью: Pillow без webp, проверка свежести пропущена")
        return

    import shutil
    import subprocess
    import sys
    import tempfile

    if not any(p.exists() for p in (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )):
        notes.append("Превью: Edge не найден, проверка свежести пропущена")
        return

    keep = target.read_bytes()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            # Скрипт пишет по месту; отодвигаем текущий файл и сравниваем
            # с тем, что соберётся заново из нынешних токенов.
            target.write_bytes(b"")
            rc = subprocess.run(
                [sys.executable, str(script)], capture_output=True, timeout=120, cwd=ROOT
            )
            fresh = target.read_bytes()
    finally:
        target.write_bytes(keep)

    if rc.returncode != 0 or not fresh:
        notes.append(
            "Превью: пересборка не удалась, свежесть не проверена "
            f"({rc.stderr.decode(errors='replace')[:120].strip()})"
        )
        return

    if fresh != keep:
        errors.append(
            "static/ogimage.webp не соответствует текущей палитре — "
            "запусти `python tools/og_image.py` и закоммичь результат"
        )
    else:
        notes.append("Превью: совпадает с текущей палитрой")


def main() -> int:
    check_tokens()
    check_light_palette_consistency()
    check_pages_exist()
    check_external_links()
    check_content_is_static()
    check_block_hashes()
    check_two_theme_states()
    check_project_icons()
    check_best_of_shape()
    check_internal_links()
    check_theme()
    check_auto_theme_fallback()
    check_meta()
    check_print_styles()
    check_fonts()
    check_font_charset_coverage()
    check_contrast_pairs()
    check_link_placement()
    check_chips()
    check_footer()
    check_two_column_layout()
    check_hero()
    check_reduced_motion()
    check_no_literals_outside_tokens()
    check_og_image_fresh()
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