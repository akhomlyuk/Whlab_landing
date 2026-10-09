#!/usr/bin/env python3
"""Проверка, что визитка помещается в 320px и не прокручивается вбок.

Файл отдельный, а не ещё одна проверка в verify.py, потому что ловит он
не то, что ловят регулярки: не «правильно ли объявлено правило», а
«поместится ли страница». Источник горизонтальной прокрутки здесь один и
он назван заранее: элемент с white-space: nowrap не переносится, и его
минимальная ширина равна всей строке целиком. Двухколоночная раскладка на
320px такому боксу места не даёт — страница уезжает за правый край, хотя
каждое правило в style.css при этом написано верно, и проверка на
контракт его бы не заметила.

Поэтому здесь считают, а не ищут подстроку. Для каждого правила с
white-space: nowrap проверка находит элемент в index.html, берёт его текст,
меряет текст по метрике шрифта и прибавляет оформление бокса: поля, рамку,
интервал между флекс-элементами и фиксированную ширину значка. Сумма —
это минимальная ширина элемента: уже он стать не может, а на более узкой
странице поедет. Самая широкая из этих ширин плюс поля обёртки и есть та
ширина экрана, ниже которой визитка не помещается; она и сравнивается с
320px.

Метрика шрифта здесь не прикидка «на глаз», а свойство самих шрифтов:
JetBrains Mono моноширинный с шагом 0.6em на любой глиф. Это замерено в
браузере на странице — 8.4px при font-size 14px на цифрах, на заглавных и
на строчных, — и потому ошибка в этой константе означала бы красную
галочку. Для пропорционального шрифта берётся завышенное среднее 0.7em:
ошибка тут может дать лишнее «не помещается», но не может дать лишнее
«помещается».

Что проверка НЕ умеет и говорит об этом ошибкой, а не молчит: разбирать
составные селекторы («.chips > .chip», «.chip:hover»). Молча пропустить
такое правило — значит выпустить страницу с непроверенной неразрывной
строкой, то есть ровно тот дефект, ради которого файл написан.

Запуск: python tools/narrow_test.py
Код возврата: 0 — помещается, 1 — нет.
"""
import math
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Вывод не должен зависеть от того, кто и откуда запустил: на Windows
# консоль по умолчанию cp1251, и галочка в последней строке роняла бы скрипт
# с UnicodeEncodeError на ровном месте (та же причина, что в verify.py).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parent.parent

# Целевая ширина. 320px — самая узкая, на которой визитку ещё открывают,
# и ниже неё поля обёртки съедают почти четверть экрана.
MIN_WIDTH = 320

# Базовый размер шрифта: в файлах он объявлен прямо в body, 16px, и это же
# браузерное умолчание. От него считаются все rem.
ROOT_FONT_PX = 16.0

# Шаг глифа JetBrains Mono: 600/1000 em, одинаковый для всех знаков.
MONO_ADVANCE = 0.6

# Ubuntu пропорциональный, и среднее плавает от «I» до «W». 0.7em взято
# намеренно с запасом: занижение дало бы ложное «помещается», завышение —
# максимум лишнее срабатывание на границе.
PROPORTIONAL_ADVANCE = 0.7

# Теги без содержимого: их не нужно закрывать, иначе разбор разъезжается.
VOID_TAGS = frozenset((
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
))

# Содержимое этих тегов не является текстом страницы.
NON_TEXT_TAGS = frozenset(("script", "style"))

errors: list[str] = []
notes: list[str] = []


# --- Разбор CSS -----------------------------------------------------------

def css_rules(css: str) -> list[tuple[tuple[str, ...], str, str]]:
    """Правила файла как (медиа-цепочка, селектор, тело).

    Комментарии снимаются заранее: «white-space: nowrap» в пояснении
    выглядит для регулярки как объявление, и проверка измерила бы строку
    из комментария (та же причина, что в check_print_styles).

    Медиа-цепочка нужна, чтобы отличать правило, которое рисуется всегда,
    от отката: правило внутри @media print не может дать прокрутку на
    экране, и ругаться на него было бы неверно.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out: list[tuple[tuple[str, ...], str, str]] = []
    media: tuple[str, ...] = ()
    prelude = ""
    i, n = 0, len(css)
    while i < n:
        ch = css[i]
        if ch == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            body = css[i + 1:j - 1]
            selector = " ".join(prelude.split())
            if selector.startswith("@media"):
                for sub_media, sub_sel, sub_body in css_rules(body):
                    out.append((media + (selector,), sub_sel, sub_body))
            elif selector.startswith("@"):
                pass  # @font-face и @keyframes правилами раскладки не являются
            else:
                out.append((media, selector, body))
            prelude = ""
            i = j
        elif ch == ";":
            prelude = ""
            i += 1
        else:
            prelude += ch
            i += 1
    return out


def declared(body: str, prop: str) -> str | None:
    """Значение последнего объявления prop в теле правила.

    Взгляд назад `(?<![\\w-])` обязателен: без него `padding` находит
    `padding-left`, а `width` — `min-width`, и бокс вышел бы вдвое шире
    своей настоящей ширины.
    """
    found = re.findall(rf"(?<![\w-]){re.escape(prop)}\s*:\s*([^;{{}}]+)", body)
    return found[-1].strip() if found else None


def length_px(value: str | None, font_px: float, tokens: dict[str, str], depth: int = 0) -> float | None:
    """Длина в пикселях из значения CSS. None — если это не длина.

    Понимаются px, rem, em и ссылка на токен. Всё остальное (проценты,
    auto, calc(), min(), normal) возвращает None: подставлять вместо них
    ноль значило бы занизить бокс и получить ложное «помещается».
    """
    if value is None or depth > 8:
        return None
    v = " ".join(value.split())
    if v in ("0", "0px", "0rem", "0em"):
        return 0.0
    ref = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*))?\)", v)
    if ref:
        resolved = tokens.get(ref.group(1))
        return length_px(resolved if resolved is not None else ref.group(2), font_px, tokens, depth + 1)
    for unit, scale in (("px", 1.0), ("rem", ROOT_FONT_PX), ("em", font_px)):
        m = re.fullmatch(rf"(-?[\d.]+){unit}", v)
        if m:
            return float(m.group(1)) * scale
    return None


# --- Разбор HTML ----------------------------------------------------------

class Node:
    """Элемент разобранного дерева: тег, классы, родитель, дети, текст."""

    __slots__ = ("tag", "classes", "parent", "children", "chunks")

    def __init__(self, tag: str | None, classes: tuple[str, ...], parent: "Node | None") -> None:
        self.tag = tag
        self.classes = classes
        self.parent = parent
        self.children: list[Node] = []
        self.chunks: list[str] = []

    def text(self) -> str:
        """Весь текст под элементом одной строкой, вместе с его собственным."""
        out: list[str] = list(self.chunks)
        stack = list(self.children)
        while stack:
            node = stack.pop(0)
            if node.tag in NON_TEXT_TAGS:
                continue
            out.extend(node.chunks)
            stack = list(node.children) + stack
        return " ".join(" ".join(out).split())

    def items(self) -> int:
        """Сколько флекс-элементов (или инлайн-боксов) внутри элемента.

        Текстовый узел внутри flex-контейнера тоже элемент, поэтому он
        считается наравне с тегами: без этого у .chip не было бы интервала
        между значком и подписью.
        """
        return len(self.children) + (1 if self.text() else 0)

    def ancestors(self) -> list["Node"]:
        out: list[Node] = []
        node = self.parent
        while node is not None and node.tag is not None:
            out.append(node)
            node = node.parent
        return out


class Tree(HTMLParser):
    """Дерево страницы. Нужен, чтобы найти элемент селектора вместе с его
    предками: размер шрифта и оформление наследуются, и без родителей
    строку не измерить."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node(None, (), None)
        self.stack = [self.root]
        self.nodes: list[Node] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        node = Node(tag, tuple(v for k, v in attrs if k == "class"), self.stack[-1])
        self.stack[-1].children.append(node)
        self.nodes.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        node = Node(tag, tuple(v for k, v in attrs if k == "class"), self.stack[-1])
        self.stack[-1].children.append(node)
        self.nodes.append(node)

    def handle_endtag(self, tag: str) -> None:
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].chunks.append(data)


# Один класс, один тег или тег с классами. Всё остальное — составной
# селектор, который проверка разбирать не умеет и обязана сказать об этом.
SIMPLE_SELECTOR = re.compile(r"^(?:([a-zA-Z][\w-]*)|(\*))?((?:\.[\w-]+)*)$")


def selector_matches(selector: str, node: Node) -> bool:
    """Подходит ли элемент под одну часть селектора."""
    m = SIMPLE_SELECTOR.match(selector)
    if m is None:
        raise ValueError(f"селектор не разбирается: {selector!r}")
    if m.group(2) == "*":
        return True
    tag, classes = m.group(1), m.group(3)
    if tag is not None and node.tag != tag.lower():
        return False
    return set(classes.split(".")[1:]) <= set(node.classes)


def parseable(selector: str) -> tuple[list[str], list[str]]:
    """Части селектора, которые проверка умеет, и те, которых она не умеет.

    Составные селекторы («.chips > .chip», «a[href]::after») не мешают
    искать свойства элемента — они просто не про этот элемент, и молча
    пропустить их безопасно. Но в правиле с white-space: nowrap молчать
    нельзя: это правило обязано быть измерено, поэтому find_nodes
    возвращает и непонятные части, а вызывающий код ругается.
    """
    parts = [" ".join(p.split()) for p in selector.split(",") if p.strip()]
    good, bad = [], []
    for part in parts:
        try:
            selector_matches(part, Node(None, (), None))
        except ValueError:
            bad.append(part)
        else:
            good.append(part)
    return good, bad


def find_nodes(tree: Tree, selector: str) -> list[Node]:
    """Элементы под составным селектором (списком через запятую)."""
    good, bad = parseable(selector)
    if bad:
        raise ValueError(f"селектор не разбирается: {', '.join(bad)}")
    return [n for n in tree.nodes if any(selector_matches(p, n) for p in good)]


# --- Свойства элемента по правилам ---------------------------------------

def own_property(rules, node: Node, prop: str, tokens: dict[str, str], font_px: float):
    """Значение свойства на самом элементе (последнее правило в файле)."""
    for media, selector, body in rules:
        if media:
            continue
        parts, _ = parseable(selector)
        if any(selector_matches(p, node) for p in parts):
            value = declared(body, prop)
            if value is not None:
                return length_px(value, font_px, tokens)
    return None


def inherited_property(rules, node: Node, prop: str, tokens: dict[str, str], font_px: float):
    """Значение свойства на элементе, иначе на ближайшем предке.

    Порядок важен: последнее правило в файле выигрывает у предыдущего, но
    объявление на самом элементе сильнее любого у предка, поэтому
    предки смотрятся только если своего объявления нет.
    """
    value = own_property(rules, node, prop, tokens, font_px)
    if value is not None:
        return value
    for ancestor in node.ancestors():
        value = own_property(rules, ancestor, prop, tokens, font_px)
        if value is not None:
            return value
    return None


def font_size_of(rules, node: Node, tokens: dict[str, str]) -> float:
    """Размер шрифта элемента в пикселях. Умолчание — 16px, агентское."""
    return inherited_property(rules, node, "font-size", tokens, ROOT_FONT_PX) or ROOT_FONT_PX


def advance_of(rules, node: Node, tokens: dict[str, str]) -> tuple[float, str]:
    """Шаг глифа и имя семейства — по фактически применившейся гарнитуре.

    Нулевой шаг означает «гарнитуру определить нечем»: подставлять шаг
    наугад здесь опаснее, чем сказать правду, потому что неизвестная
    гарнитура — это ровно тот случай, где прокрутка появляется тихо.
    """
    for rule in (node,) + tuple(node.ancestors()):
        for media, selector, body in rules:
            if media:
                continue
            parts, _ = parseable(selector)
            if not any(selector_matches(p, rule) for p in parts):
                continue
            value = declared(body, "font-family")
            if value is None:
                continue
            m = re.search(r"var\(\s*(--[\w-]+)", value)
            resolved = tokens.get(m.group(1), "") if m else value
            if "JetBrains Mono" in resolved or "monospace" in resolved:
                return MONO_ADVANCE, "JetBrains Mono"
            if "Ubuntu" in resolved:
                return PROPORTIONAL_ADVANCE, "Ubuntu"
            return 0.0, resolved.strip("'\" ")
    return 0.0, "гарнитура по умолчанию из браузера"


def padding_x_of(bodies: list[str], font_px: float, tokens: dict[str, str]) -> float:
    """Поля по бокам. Сокращённая запись разбирается, иначе плитка с
    `padding: 4px 12px` посчиталась бы вдвое уже своей настоящей.

    Берётся последнее правило, которое вообще объявляет поля: в каскаде
    побеждает написанное ниже, а не сумма. Поля и рамка при этом
    считаются независимо — они живут в разных правилах чаще, чем кажется.
    """
    for body in reversed(bodies):
        left = length_px(declared(body, "padding-left"), font_px, tokens)
        right = length_px(declared(body, "padding-right"), font_px, tokens)
        if left is not None or right is not None:
            return (left or 0.0) + (right or 0.0)
        shorthand = declared(body, "padding")
        if shorthand is None:
            continue
        parts = [" ".join(s.split()) for s in re.split(r"\s+", shorthand.strip()) if s]
        values = [length_px(p, font_px, tokens) for p in parts]
        if not values or values[0] is None:
            continue
        if len(values) == 1:
            return values[0] * 2
        if len(values) == 2:
            return (values[1] or 0.0) * 2
        return (values[1] or 0.0) + (values[3] if len(values) > 3 and values[3] is not None else values[1] or 0.0)
    return 0.0


def border_x_of(bodies: list[str], font_px: float, tokens: dict[str, str]) -> float:
    """Рамка по бокам в пикселях. Снова последнее правило, не сумма."""
    for body in reversed(bodies):
        widths: list[float] = []
        for side in ("left", "right"):
            width = length_px(declared(body, f"border-{side}-width"), font_px, tokens)
            if width is None:
                shorthand = declared(body, f"border-{side}") or declared(body, "border")
                if shorthand:
                    m = re.search(r"(-?[\d.]+)px", shorthand)
                    width = float(m.group(1)) if m else 0.0
            widths.append(width or 0.0)
        if any(widths):
            return sum(widths)
    return 0.0


def box_overhead(rules, node: Node, tokens: dict[str, str], font_px: float) -> float:
    """Всё в боксе, кроме текста: поля, рамка, интервалы, значок.

    Оформление значка берётся у дочернего элемента: у .chip это
    `width: 16px` у .chip__icon, и без него плитка посчиталась бы на 16px
    уже настоящей — ровно настолько, сколько нужно, чтобы длинная подпись
    влезла туда, куда не влезает.

    Известная недооценка: у .hero__tag щит — это не прямой ребёнок, а
    svg внутри .hero__shield, и его width: 0.95em в счёт не идёт. Подпись
    считается на 17px уже настоящей, но там её 202px против полосы в
    288px, так что запас перекрывает ошибку с запасом. Обратного хуже:
    занижение здесь может дать лишнее «помещается» — и если бы щит
    дорос до сотни пикселей, проверка промолчала бы.
    """
    own = own_property_bodies(rules, node)
    overhead = padding_x_of(own, font_px, tokens) + border_x_of(own, font_px, tokens)

    gaps = 0.0
    for rule_body in own:
        for prop in ("gap", "column-gap"):
            value = length_px(declared(rule_body, prop), font_px, tokens)
            if value is not None:
                gaps = max(gaps, value)
    overhead += gaps * max(0, node.items() - 1)

    for child in node.children:
        for child_body in own_property_bodies(rules, child):
            width = length_px(declared(child_body, "width"), font_px, tokens)
            if width:
                overhead += width
    return overhead


def own_property_bodies(rules, node: Node) -> list[str]:
    """Тела правил, бьющих прямо по элементу (без предков и без медиа)."""
    out = []
    for media, selector, body in rules:
        if media:
            continue
        parts, _ = parseable(selector)
        if any(selector_matches(p, node) for p in parts):
            out.append(body)
    return out


# --- Проверки -------------------------------------------------------------

def content_width(css: str, tokens: dict[str, str]) -> tuple[float, float, float]:
    """Ширина обёртки на MIN_WIDTH и сколько из неё достаётся контенту.

    Возвращает (ширина обёртки, поля по бокам суммарно, ширина контента).
    Формула читается из самого файла, а не зашита числом: если владелец
    сменит `100% - 2rem` на `100% - 1rem`, бюджет контента обязан
    сдвинуться вместе с правкой, иначе проверка продолжитт считать не
    тот край, который нарисован.
    """
    wrapper_rule = next((body for _, selector, body in css_rules(css)
                         if ".wrapper" in parseable(selector)[0]), None)
    if wrapper_rule is None:
        errors.append("style.css: нет правила .wrapper — ширину страницы считать нечем")
        return float(MIN_WIDTH), 32.0, float(MIN_WIDTH)
    width = declared(wrapper_rule, "width") or ""
    m = re.search(r"100%\s*-\s*([\d.]+)rem", width)
    if m is None:
        errors.append(
            "style.css: не разобрана формула ширины .wrapper "
            f"({width!r}) — проверка не знает, сколько места остаётся под контент"
        )
        return float(MIN_WIDTH), 32.0, float(MIN_WIDTH)
    side_total = float(m.group(1)) * ROOT_FONT_PX
    cap = length_px(tokens.get("--wrapper-max", ""), ROOT_FONT_PX, tokens)
    cap = cap if cap is not None else float("inf")
    box = min(cap, MIN_WIDTH - side_total)
    return box, side_total, box


def check_narrow_fallback(css: str) -> None:
    """На 320px раскладка обязана быть одноколоночной, и откат обязан
    на 320px вообще действовать.

    Порог написан руками, и в этом его слабое место: @media
    (max-width: 240px) не сработает на экране в 320px, а страница всё
    равно нарисуется двумя колонками и уедет вбок. Проверка на
    присутствие такого отката молчала бы ровно на той ширине, ради
    которой он написан, поэтому граница сравнивается с 320px, а не
    ищется как строка.
    """
    blocks = [
        (float(b), m)
        for b, m in re.findall(
            r"@media\s*\(max-width:\s*([\d.]+)px\)\s*\{(.*?)\n\}", css, re.DOTALL
        )
    ]
    if not blocks:
        errors.append(
            "style.css: нет @media (max-width: Npx) — на 320px страница "
            "останется в двух колонках и поедет вбок"
        )
        return
    # Откат, который на 320px действует, — это тот, у кого граница не уже
    # целевой ширины: max-width: 640px на экране в 320px срабатывает.
    # Наоборот, откат на max-width: 240px на 320-экранном телефоне не
    # действует, и страница рисуется двумя колонками: наличие правила в
    # файле для этого ничего не значит.
    applicable = [b for b in blocks if b[0] >= MIN_WIDTH]
    if not applicable:
        widest = max(b[0] for b in blocks)
        errors.append(
            f"style.css: ни один откат не действует на {MIN_WIDTH}px — "
            f"самый широкий порог max-width: {widest:g}px, а страница "
            "останется в двух колонках и поедет вбок"
        )
        return
    breakpoint, inner = max(applicable, key=lambda b: b[0])
    inner = re.sub(r"/\*.*?\*/", "", inner, flags=re.DOTALL)

    rows = [
        r.split()
        for r in re.findall(r"grid-template-areas\s*:(.*?);", inner, re.DOTALL)
        for r in re.findall(r"['\"]([^'\"]*)['\"]", r)
    ]
    if rows and any(len(r) != 1 for r in rows):
        fat = next(r for r in rows if len(r) != 1)
        errors.append(
            "style.css: в откате @media область занимает не одну ячейку — "
            f"строка {' '.join(fat)!r} оставит вторую колонку"
        )
    if not re.search(r"grid-template-columns\s*:\s*(?:none|1fr)\s*;", inner):
        errors.append(
            "style.css: в откате @media колонка не схлопнута — "
            "нужен grid-template-columns: 1fr, иначе треки остаются 1fr 1.25fr"
        )
    notes.append(f"Откат в одну колонку на {MIN_WIDTH}px: max-width {breakpoint:g}px")


def check_fixed_widths(css: str, available: float) -> None:
    """Ни одна фиксированная ширина в px не должна быть шире полосы контента.

    Это второй, чисто декларативный источник вылета за край: бокс шириной
    320px внутри полосы в 288px не переносится и не сжимается, страница
    получает горизонтальную прокрутку, а правило при этом написано
    безупречно. Правила @media print не проверяются: на бумаге полоса
    другая, и ругаться на неё было бы неверно.
    """
    widest = 0.0
    for media, selector, body in css_rules(css):
        if any("print" in m for m in media):
            continue
        for prop in ("width", "min-width"):
            for value in re.findall(rf"(?<![\w-]){prop}\s*:\s*([\d.]+)px", body):
                width = float(value)
                widest = max(widest, width)
                if width > available:
                    errors.append(
                        f"style.css: {selector} объявляет {prop}: {width:g}px, "
                        f"а на {MIN_WIDTH}px доступно {available:g}px — "
                        "бокс шире полосы и страница поедет вбок"
                    )
    if widest:
        notes.append(f"Самая широкая фиксированная ширина: {widest:g}px из {available:g}px")


def check_nowrap_runs(css: str, html: str, tokens: dict[str, str], available: float) -> float:
    """Главная проверка: неразрывная строка обязана влезать в полосу.

    Возвращает ширину самого широкого бокса — из неё получается та
    минимальная ширина экрана, на которой визитка ещё стоит.
    """
    rules = css_rules(css)
    tree = Tree()
    tree.feed(html)

    worst = 0.0
    worst_label = "—"
    measured = 0
    for media, selector, body in rules:
        if "white-space" not in body:
            continue
        value = declared(body, "white-space")
        if value is None or "nowrap" not in value:
            continue
        try:
            nodes = find_nodes(tree, selector)
        except ValueError as e:
            # Неразрывная строка под таким селектором не измерена, а
            # пропустить её молча — значит выпустить страницу с
            # непроверенным боксом. Это ошибка, а не предупреждение.
            errors.append(
                f"style.css: {selector} объявляет white-space: nowrap, "
                f"но проверка не умеет его разобрать ({e}) — строка под ним "
                "осталась бы неизмеренной"
            )
            continue
        if not nodes:
            errors.append(
                f"style.css: {selector} объявляет white-space: nowrap, но на "
                "странице нет ни одного элемента с таким классом — правило "
                "охраняет пустоту, а строка, которую оно задумано было "
                "защитить, измеряется в другом месте"
            )
            continue
        for node in nodes:
            text = node.text()
            if not text:
                continue
            font_px = font_size_of(rules, node, tokens)
            advance, family = advance_of(rules, node, tokens)
            if not advance:
                errors.append(
                    f"style.css: не удалось определить гарнитуру для {selector} "
                    f"({family}) — строку {text!r} нечем мерить, а она не переносится"
                )
                continue
            run = advance * font_px * len(text)
            box = run + box_overhead(rules, node, tokens, font_px)
            measured += 1
            if box > worst:
                worst = box
                worst_label = f"{selector} {text!r}"
            if box > available:
                errors.append(
                    f"{selector}: неразрывная строка {text!r} — {box:.0f}px "
                    f"({len(text)} знаков × {advance:g}em × {font_px:g}px + "
                    f"оформление {box - run:.0f}px), а на {MIN_WIDTH}px доступно "
                    f"{available:g}px. Строка не переносится и вытолкнет страницу "
                    "за правый край; нужен перенос или сокращение подписи"
                )
    if measured:
        notes.append(
            f"Неразрывных строк измерено: {measured}, самая широкая — "
            f"{worst_label}: {worst:.0f}px из {available:g}px"
        )
    return worst


def main() -> int:
    css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
    tokens_css = (ROOT / "css" / "tokens.css").read_text(encoding="utf-8")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    tokens = {
        name: value
        for name, value in re.findall(
            r"(--[\w-]+)\s*:\s*([^;]+);", re.sub(r"/\*.*?\*/", "", tokens_css, flags=re.DOTALL)
        )
    }

    box, side_total, available = content_width(css, tokens)
    print(f"Обёртка на {MIN_WIDTH}px: {box:g}px, из них поля {side_total:g}px, контенту {available:g}px")

    check_narrow_fallback(css)
    check_fixed_widths(css, available)
    worst = check_nowrap_runs(css, html, tokens, available)

    # Итог одной строкой: так и обещано в докстринге — проверка считает
    # минимальную ширину экрана и сравнивает её с целевой.
    if worst:
        need = math.ceil(worst + side_total)
        print(f"Самая узкая ширина экрана по неразрывным строкам: {need}px (цель {MIN_WIDTH}px)")
        if need > MIN_WIDTH:
            errors.append(
                f"визитка не помещается в {MIN_WIDTH}px: самый широкий "
                f"неразрывный бокс требует {need}px"
            )

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