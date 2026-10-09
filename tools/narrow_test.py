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

Поэтому здесь считают, а не ищут подстроку. Считается три вещи, и все
три — в одном и том же ключе: ширина неразрывной строки, ширина бокса
вокруг неё и полоса, в которую этот бокс должен влезть.

1. Неразрывная строка. Для каждого правила с white-space: nowrap
   проверка находит элемент в index.html, берёт его текст, меряет текст
   по метрике гарнитуры и прибавляет оформление бокса: поля, рамку,
   интервал между флекс-элементами и фиксированную ширину значка.
2. Полоса. Считается не полоса страницы, а полоса ВНУТРИ контейнера:
   от 288px отнимаются поля и рамка каждого предка по пути к элементу.
   Плитка внутри .spotlight получает не 288, а 238 — и именно с ней
   сверяется, потому что 288 ей ничего не говорит.
3. Неразрывная строка внутри флекс-контейнера без переноса. Ширина
   такой строки не освобождается соседям: контейнер не переносит свои
   элементы и обязан уместить их все на одной строке. Поэтому
   считается минимальная ширина контейнера — сумма минимальных ширин
   элементов плюс интервалы и поля — и сверяется с его же полосой.

Метрика шрифта здесь не прикидка «на глаз», а свойство самих шрифтов:
JetBrains Mono моноширинный с шагом 0.6em на любой глиф. Это замерено в
браузере на странице — 8.4px при font-size 14px на цифрах, на заглавных и
на строчных, — и потому ошибка в этой константе означала бы красную
галочку. Для пропорционального шрифта берётся завышенное среднее 0.7em:
ошибка тут может дать лишнее «не помещается», но не может дать лишнее
«помещается».

ЧТО ФАЙЛ НЕ ЛОВИТ — важно, чтобы это не выдавали за защиту:

  * Сжатие флекс-элементов. Плитка .place — флекс-элемент с
    flex-shrink: 1, и если её натуральная ширина больше полосы,
    браузер не поедет за край, а сожмёт подписи ВНУТРИ. Так «Top 3»
    превратилось в «Top / 3» на 320px. Минимальная ширина флекс-элемента
    считается по неразрывным кускам и по самому длинному слову, а
    натуральная — нет: чтобы её узнать, нужен разрыв строк. Откат
    правки `.place__year`/`.place__rank` этот прогон НЕ заметит.
  * Сетку. display: grid считается как один столбец — на 320px так и
    есть, но две колонки на широком экране этим не охвачены.
  * Содержимое псевдоэлементов. `::before`/`::after` у флекс-контейнера
    становятся его элементами и занимают место, но в дереве разбора их
    нет, и мерить их нечем. Правило с таким псевдоэлементом проверка не
    пропускает молча, а отказывается считать страницу годной — про
    `.chip::after { padding: 0 120px }` прогон скажет прямо.
  * Правила, условие которых нельзя решить (min-width, всякое неведомое):
    действует худший случай. @media print не действует — страница на
    бумаге, а не на экране.

Что проверка НЕ умеет и говорит об этом ошибкой, а не молчит: разбирать
составные селекторы («.chips > .chip», «#best .spotlight») там, где они
объявляют то, что влияет на размер. Молча пропустить такое правило —
значит выпустить страницу с непроверенной неразрывной строкой, то есть
ровно тот дефект, ради которого файл написан. Обход идёт по меряемым
боксам **и по их предкам**: размер бокса читается с них всех, и пропуск
любого из них — тот же тихий недобор.

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

# Теги, которые по умолчанию блочные. Умолчание нужно, потому что у
# .block, li и section нет объявления display, а считать их инлайновыми
# значит не увидеть в раскладке ни одного блока.
BLOCK_TAGS = frozenset((
    "address", "article", "aside", "blockquote", "body", "dd", "div", "dl",
    "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
    "pre", "section", "table", "ul",
))

# Заменяющие элементы: у них собственная ширина и есть минимальная, они не
# сжимаются до нуля, как бокс с текстом.
REPLACED_TAGS = frozenset((
    "canvas", "embed", "iframe", "img", "input", "object", "picture", "svg",
    "video",
))

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


def media_applies(condition: str, width: float) -> bool:
    """Действует ли @media на экране шириной width.

    Условие не вычисляется — вычисляется только применимость, и то там,
    где её можно решить однозначно. Всё неразрешимое считается
    действующим: лучше лишняя ошибка, чем уверенное «помещается» на
    странице, которую надо было померить.
    """
    if re.search(r"\bprint\b", condition):
        return False
    m = re.search(r"max-width\s*:\s*([\d.]+)px", condition)
    if m:
        return float(m.group(1)) >= width
    m = re.search(r"min-width\s*:\s*([\d.]+)px", condition)
    if m:
        return width >= float(m.group(1))
    return True


def applicable_conditions(rules) -> set[str]:
    """Условия @media из правил, действующие на экране MIN_WIDTH."""
    conditions = {c for media, _, _ in rules for c in media}
    return {c for c in conditions if media_applies(c, MIN_WIDTH)}


def live_rules(css: str) -> list[tuple[tuple[str, ...], str, str]]:
    """Правила, которые вообще могут действовать на экране MIN_WIDTH.

    Отсечение делается один раз, здесь, а не в каждом обходе: иначе
    пришлось бы повторять «пропустить @media» в шести местах, и одно
    из них рано или поздно забылось бы — а забытое здесь означает
    неразобранный каскад, то есть тихо неверные числа.
    """
    rules = css_rules(css)
    ok = applicable_conditions(rules)
    return [r for r in rules if all(c in ok for c in r[0])]


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

    def direct_text(self) -> str:
        """Только собственный текст элемента, без текста потомков.

        Отдельно от text() он нужен при разборе флекс-контейнера: текст,
        лежащий между двумя <span>, становится отдельным элементом строки,
        и посчитанный вместе с потомками он посчитался бы дважды.
        """
        return " ".join(" ".join(self.chunks).split())

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
    """Части селектора, которые проверка умеет, и те, которых она не умеет."""
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


def subject_could_match(part: str, node: Node) -> bool:
    """Относится ли непонятный селектор к этому элементу — хотя бы правой
    частью своей цепочки.

    Разбирать весь селектор не нужно: важно лишь одно — может ли это
    правило вообще бить по данному элементу. `.chips > .chip` — может,
    и молчать про него нельзя. А `a[href]::after` — не может: псевдоэлемента
    в дереве нет. Отсеиваются и правила, чья правая часть указывает на
    другой элемент (`.hero__shield svg` для чипа), иначе проверка ругалась
    бы на каждый второй селектор в файле.

    Если правую часть разобрать не удалось, ответ — «может»: неизвестное
    считается опасным.
    """
    right = re.split(r"[\s>+~]+", part.strip())[-1]
    if not right:
        return False
    # Псевдоэлемент — не элемент дерева, но полноценный бокс на самом
    # элементе: ::before у флекс-контейнера становится его элементом и
    # занимает место, а `padding` у него — реальные 240px поперёк. Отбросить
    # его как «псевдоэлемента в дереве нет» нельзя: дерево тут ни при
    # чём, считается раскладка. Поэтому псевдоэлемент снимается, а сам
    # элемент проверяется как обычно.
    if "::" in right:
        right = re.sub(r"::[A-Za-z][\w-]*", "", right)
        if not right:
            return True
    right = re.sub(r":[A-Za-z][\w-]*", "", right)
    right = re.sub(r"\[[^\]]*\]", "", right)
    m = SIMPLE_SELECTOR.match(right)
    if m is None:
        return True
    if m.group(2) == "*":
        return True
    if m.group(1) is not None and m.group(1).lower() != (node.tag or ""):
        return False
    return set(m.group(3).split(".")[1:]) <= set(node.classes)


def raising_parts(rules, node: Node, prop: str) -> list[str]:
    """Проверяемые части селекторов для свойства prop.

    Непонимание селектора — не повод пропускать правило молча: оно либо
    подходит элементу и объявляет нужное свойство (тогда бокс посчитан
    неверно и страница поедет тихо), либо не подходит и тогда просто не
    мешает. Разница видна здесь, а не потеряна молча.
    """
    for _, selector, body in rules:
        if declared(body, prop) is None:
            continue
        for part in parseable(selector)[1]:
            if subject_could_match(part, node):
                raise ValueError(f"{part!r} объявляет {prop}, но проверка не умеет его разобрать")


def find_nodes(tree: Tree, selector: str) -> list[Node]:
    """Элементы под составным селектором (списком через запятую)."""
    good, bad = parseable(selector)
    if bad:
        raise ValueError(f"селектор не разбирается: {', '.join(bad)}")
    return [n for n in tree.nodes if any(selector_matches(p, n) for p in good)]


# --- Свойства элемента по правилам ---------------------------------------

def own_property(rules, node: Node, prop: str, tokens: dict[str, str], font_px: float):
    """Значение свойства на самом элементе.

    Побеждает ПОСЛЕДНЕЕ правило в файле, а не первое. Обход по порядку
    файла с возвратом на первой подходящей строке читает каскад наоборот
    и выдаёт уверенно неверные числа: раннее правило с правильным кеглем
    перебивало бы позднее настоящее с 4rem, чипы вышли бы по 741px, и
    проверка радостно сообщала бы «201.2px».
    """
    value = None
    for body in own_property_bodies(rules, node):
        declared_value = declared(body, prop)
        if declared_value is not None:
            value = length_px(declared_value, font_px, tokens)
    return value


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

    Обход ведёт себя так же, как own_property: сначала сам элемент и
    последнее правило для него, и только потом предки.
    """
    for target in (node,) + tuple(node.ancestors()):
        value = None
        for body in own_property_bodies(rules, target):
            declared_value = declared(body, "font-family")
            if declared_value is not None:
                value = declared_value
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

    `padding-inline` разбирается наравне с `padding-left/right`: это
    логическое направление записи, а в горизонтальной раскладке оно
    обычное поле. Не зная его, обёртка с `padding-inline` выглядела бы
    без полей — и полоса для её детей считалась бы шире настоящей.
    """
    for body in reversed(bodies):
        left = length_px(declared(body, "padding-left"), font_px, tokens)
        right = length_px(declared(body, "padding-right"), font_px, tokens)
        if left is None and right is None:
            inline = length_px(declared(body, "padding-inline"), font_px, tokens)
            start = length_px(declared(body, "padding-inline-start"), font_px, tokens)
            end = length_px(declared(body, "padding-inline-end"), font_px, tokens)
            left = inline if inline is not None else start
            right = inline if inline is not None else end
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
    svg внутри .hero__shield, и его width: 0.95em в счёт не идёт: селектор
    «.hero__shield svg» составной, и check_readable_selectors его не
    считает ошибкой только потому, что svg не несёт текста и подписи не
    решает. Подпись выходит на 17px уже настоящей, но там её 202px против
    полосы в 288px, так что запас перекрывает ошибку. Обратного хуже:
    занижение способно дать лишнее «помещается», и если бы щит дорос до
    сотни пикселей, проверка промолчала бы.
    """
    own = own_property_bodies(rules, node)
    overhead = padding_x_of(own, font_px, tokens) + border_x_of(own, font_px, tokens)

    # Интервал считается между соседними элементами строки. Текстовый узел
    # между тегами тоже элемент — без этого у .chip не было бы зазора между
    # значком и подписью, и плитка сочлась бы на 8px уже своей настоящей.
    parts = len(node.children) + (1 if node.direct_text() else 0)
    overhead += gap_x_of(rules, node, font_px, tokens) * max(0, parts - 1)

    for child in node.children:
        for child_body in own_property_bodies(rules, child):
            width = length_px(declared(child_body, "width"), font_px, tokens)
            if width:
                overhead += width
    return overhead


def own_property_bodies(rules, node: Node) -> list[str]:
    """Тела правил, бьющих прямо по элементу, в порядке файла.

    Медиа-откаты уже отсечены в live_rules, поэтому здесь проверки на
    media нет: повторять её в каждом обходе — значит забыть её в одном
    из них, а забытая даёт неразобранный каскад.
    """
    out = []
    for _, selector, body in rules:
        parts, _ = parseable(selector)
        if any(selector_matches(p, node) for p in parts):
            out.append(body)
    return out


def white_space_of(rules, node: Node) -> str:
    """white-space элемента: своё объявление, иначе предковое.

    Нужно, чтобы отличить неразрывный текст от переносного: у первого
    минимальная ширина равна всей строке, у второго — самому длинному
    слову.
    """
    value = None
    for body in own_property_bodies(rules, node):
        declared_value = declared(body, "white-space")
        if declared_value is not None:
            value = declared_value
    if value is None:
        for ancestor in node.ancestors():
            for body in own_property_bodies(rules, ancestor):
                declared_value = declared(body, "white-space")
                if declared_value is not None:
                    value = declared_value
            if value is not None:
                break
    return value or "normal"


def strip_root_of(tree: Tree) -> Node | None:
    """Корень полосы — обёртка, от которой отсчитываются все поля."""
    return next((n for n in tree.nodes if n.tag == "div" and "wrapper" in n.classes), None)


def container_width(rules, node: Node, root: Node, outer: float,
                    tokens: dict[str, str], font_px: float) -> float:
    """Полоса, доступная боксу элемента, — с учётом предков.

    Сравнивать бокс с полосой страницы нельзя: у плитки внутри .spotlight
    полоса не 288, а 238, потому что между ней и страницей стоят поля и
    рамка панели. Отнимается оформление каждого предка по пути.

    `outer` — ширина рамки полосы (обёртки), а не её внутренняя полоса,
    и это единственный способ не вычесть поля обёртки дважды: раньше
    content_width отнимал их сама, а обход предков отнимал ещё раз, и
    обёртка с `padding-inline` сужала полосу вдвое против всякой
    разумности. Поэтому здесь обход начинается с корня полосы, а сам
    корень в списке предков пропускается.
    """
    width = outer
    chain = [root] + [a for a in node.ancestors() if a is not root]
    for ancestor in chain:
        bodies = own_property_bodies(rules, ancestor)
        width -= padding_x_of(bodies, font_px, tokens)
        width -= border_x_of(bodies, font_px, tokens)
    return width


# --- Проверки -------------------------------------------------------------

def display_of(rules, node: Node) -> str:
    """display элемента: своё объявление, иначе умолчание по тегу."""
    value = None
    for body in own_property_bodies(rules, node):
        declared_value = declared(body, "display")
        if declared_value is not None:
            value = declared_value
    if value is not None:
        return value
    return "block" if node.tag in BLOCK_TAGS else "inline"


def flex_kind(rules, node: Node) -> str:
    """Как элементы расставлены по ширине: «row», «stack» или «».

    «row» — флекс-контейнер, который не переносит элементы и кладёт их в
    одну строку. Минимальная ширина такого контейнера равна СУММЕ
    минимальных ширин элементов: места соседям не остаётся, и если сумма
    не влезает, браузер либо сожмёт элементы, либо поедет за край — молча.

    «stack» — перенос, колонка или сетка: элементы не конкурируют за одну
    строку, поэтому берётся наибольшая из минимальных, а не сумма. Сетка
    считается одним столбцом — на 320px она одна, и это единственное,
    что здесь нужно.
    """
    display = display_of(rules, node)
    if "grid" in display:
        return "stack"
    if "flex" not in display:
        return ""
    direction = None
    for body in own_property_bodies(rules, node):
        value = declared(body, "flex-direction")
        if value is not None:
            direction = value
    if direction is not None and "column" in direction:
        return "stack"
    for body in own_property_bodies(rules, node):
        if re.search(r"flex-wrap\s*:\s*wrap", body):
            return "stack"
    return "row"


def gap_x_of(rules, node: Node, font_px: float, tokens: dict[str, str]) -> float:
    """Интервал по горизонтали — наибольший из объявленных."""
    gap = 0.0
    for body in own_property_bodies(rules, node):
        for prop in ("gap", "column-gap"):
            value = length_px(declared(body, prop), font_px, tokens)
            if value is not None:
                gap = max(gap, value)
    return gap


def fixed_width(rules, node: Node, tokens: dict[str, str], font_px: float) -> float | None:
    """Ширина, которую бокс не отдаст никогда.

    Объявленная width становится такой, только если элемент не сжимается
    (`flex: none` либо `flex-shrink: 0`) или если он заменяющий — у
    заменяющего собственная ширина и есть минимальная. Иначе элемент
    ужимается до своей минимальной, и width ничего не значит: без этой
    оговорки иконка 36px посчиталась бы нулём и не учлась бы в строке.
    """
    width = own_property(rules, node, "width", tokens, font_px)
    if width is None:
        return None
    if node.tag in REPLACED_TAGS:
        return width
    for body in own_property_bodies(rules, node):
        if re.search(r"flex\s*:\s*none\s*;", body) or re.search(r"flex-shrink\s*:\s*0", body):
            return width
    return None


def min_content(rules, node: Node, tokens: dict[str, str], depth: int = 0) -> float:
    """Наименьшая ширина, в которую бокс ещё может ужаться.

    Текст без переноса тянется всей строкой, переносный — самым длинным
    словом: перенос разрезает строку по пробелу, и уже это слово и есть
    наименьшая возможная ширина. Дети считаются рекурсивно по тем же
    правилам, а собственный текст элемента — отдельно от текста детей:
    иначе он посчитался бы дважды.
    """
    if depth > 12:
        return 0.0
    font_px = font_size_of(rules, node, tokens)
    bodies = own_property_bodies(rules, node)
    chrome = padding_x_of(bodies, font_px, tokens) + border_x_of(bodies, font_px, tokens)

    fixed = fixed_width(rules, node, tokens, font_px)
    if fixed is not None:
        return chrome + fixed

    kind = flex_kind(rules, node)
    if kind:
        parts = [min_content(rules, c, tokens, depth + 1) for c in node.children]
        if node.direct_text():
            parts.append(text_measure(rules, node, node.direct_text(), tokens))
    else:
        # Обычный блок: боксы-дети дают максимум, инлайновые дети отдельно
        # не считаются — они текут в строке вместе с текстом.
        parts = [
            min_content(rules, c, tokens, depth + 1)
            for c in node.children
            if display_of(rules, c) not in ("inline", "inline-flex", "inline-grid", "inline-block")
        ]
        if node.text():
            parts.append(text_measure(rules, node, node.text(), tokens))

    if not parts:
        return chrome
    if kind == "row":
        return chrome + sum(parts) + gap_x_of(rules, node, font_px, tokens) * (len(parts) - 1)
    return chrome + max(parts)


def text_measure(rules, node: Node, text: str, tokens: dict[str, str]) -> float:
    """Ширина текста в его наименьшей возможной ширине."""
    if not text:
        return 0.0
    font_px = font_size_of(rules, node, tokens)
    advance, _ = advance_of(rules, node, tokens)
    if not advance:
        return 0.0
    if "nowrap" in white_space_of(rules, node):
        unit = text
    else:
        # Самое длинное слово. Перенос по дефису не учитывается: браузер
        # рвёт строку и по нему, а разбирать правила переноса тут нечем.
        # Оценка в сторону завышения — в сторону ошибки, а не пропуска.
        unit = max(text.split(" "), key=len)
    return advance * font_px * len(unit)


SIZING_PROPS = (
    "padding", "border", "width", "gap", "font-size", "font-family",
    "white-space", "display", "flex-direction", "flex-wrap",
)


def measured_nodes(rules, tree: Tree, tokens: dict[str, str]) -> list[Node]:
    """Узлы, чей размер проверка читает, — вместе с их предками.

    Это неразрывные строки, контейнеры без переноса, те их дети, у
    которых есть текст или объявленная ширина, **и все предки всех
    этих узлов**. Предки нужны не из вежливости: `container_width`
    снимает с каждого поля и рамку, а `min_content` и `font_size_of`
    читают по цепочке вверх, — то есть размер меряемого бокса
    складывается из размеров их всех. Проверка, которая смотрела бы
    только на сам бокс, пропускала ровно тот случай, где поля панели
    спрятаны за неразбираемым `#best .spotlight`: 48px исчезали из
    модели, полоса для плитки вырастала с 238 до 286, и дефект
    становился невидим.

    Чего в списке нет: знаков и картинок, которые не несут текста и не
    объявляют ширины, — о них молчать можно.
    """
    out: list[Node] = []
    seen: set[int] = set()

    def add(node: Node) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        out.append(node)

    for node in tree.nodes:
        kind = flex_kind(rules, node)
        fixed = fixed_width(rules, node, tokens, font_size_of(rules, node, tokens))
        carries = bool(node.text()) or fixed is not None
        measured = ("nowrap" in white_space_of(rules, node) and carries) or kind == "row"
        if not measured:
            continue
        add(node)
        for ancestor in node.ancestors():
            add(ancestor)
        if kind == "row":
            for child in node.children:
                if child.text() or fixed_width(
                    rules, child, tokens, font_size_of(rules, child, tokens)
                ) is not None:
                    add(child)
    return out


def check_readable_selectors(rules, tree: Tree, tokens: dict[str, str]) -> None:
    """Ни одно правило, влияющее на размер меряемого бокса, не осталось
    непрочитанным.

    Составной селектор («.chips > .chip», «#best .spotlight») проверка
    не разбирает, и раньше такое правило просто исчезало: бокс считался
    без объявленных ему полей и выходил уже настоящей ширины, то есть
    ровно настолько, чтобы длинная подпись влезла туда, куда не влезает.

    Обход идёт по measured_nodes, а это меряемые боксы **вместе с
    предками**: размер меряемого бокса читается с них всех, и пропуск
    любого из них — тот же тихий недобор. Раньше аудит покрывал только
    сам бокс, и объявление полей у его предка исчезало: `#best
    .spotlight` съедал 48px, полоса для плитки росла с 238 до 286, а
    прогон оставался зелёным.

    Отказ честнее догадки. Если правило разобрать нельзя и оно может
    бить по меряемому боксу — это ошибка, а не предупреждение: страница,
    чью геометрию не удалось восстановить, не может быть названа годной.
    """
    for node in measured_nodes(rules, tree, tokens):
        for prop in SIZING_PROPS:
            try:
                raising_parts(rules, node, prop)
            except ValueError as e:
                errors.append(
                    f"style.css: {_sel_of(node)} — {e}; размер бокса посчитан "
                    "без этого правила и вышел бы уже своей настоящей"
                )
                return


def check_flex_rows(rules, tree: Tree, tokens: dict[str, str], root: Node, outer: float) -> None:
    """Неразрывная строка в негнущемся флекс-контейнере не оставляет соседям места.

    Без этой проверки неразрывная строка проходила бы, если бы ей хватало
    полосы, — а места ей не хватало: ширина строки не освобождается
    соседям, и контейнер либо сожмёт их, либо вылезет за край. Именно так
    вела себя плитка «2024 Red Team Scenarios Top 3» на 320px.
    """
    checked = 0
    worst = 0.0
    worst_label = "—"
    for node in tree.nodes:
        if flex_kind(rules, node) != "row":
            continue
        font_px = font_size_of(rules, node, tokens)
        available = container_width(rules, node, root, outer, tokens, font_px)
        need = min_content(rules, node, tokens)
        checked += 1
        if need > worst:
            worst, worst_label = need, _sel_of(node)
        if need > available:
            errors.append(
                f"{_sel_of(node)}: элементы не переносятся, вместе им нужно "
                f"{need:.0f}px, а контейнер отдаёт {available:g}px — лишнее "
                "сожмёт подписи, избыток уйдёт за правый край"
            )
    if checked:
        notes.append(
            f"Флекс-контейнеров без переноса: {checked}, самый тесный — "
            f"{worst_label}: {worst:.0f}px"
        )


def _sel_of(node: Node) -> str:
    classes = ".".join(node.classes)
    return f"{node.tag}{'.' + classes if classes else ''}"


def content_width(css: str, tokens: dict[str, str]) -> tuple[float, float, float]:
    """Ширина обёртки на MIN_WIDTH и сколько из неё достаётся детям.

    Возвращает (ширина рамки полосы, поля по бокам суммарно, полоса
    детям). Поля по бокам уже вычлись как «100% - 2rem», а padding-inline
    самой обёртки вычитается здесь — иначе он не учитывался бы вовсе, и
    полоса для детей вышла бы шире той, что нарисована. Проверки по
    контейнерам берут ПЕРВУЮ величину и вычитают оформление корня сами:
    отдать им уже вычтенную полосу значило бы вычесть обёртку дважды.
    Формула читается из самого файла, а не зашита числом: если владелец
    сменит `100% - 2rem` на `100% - 1rem`, бюджет обязан сдвинуться
    вместе с правкой, иначе проверка продолжит считать не тот край,
    который нарисован.
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
    chrome = padding_x_of([wrapper_rule], ROOT_FONT_PX, tokens)
    chrome += border_x_of([wrapper_rule], ROOT_FONT_PX, tokens)
    return box, side_total, box - chrome


def check_narrow_fallback(rules) -> None:
    """На 320px раскладка обязана быть одноколоночной, и откат обязан
    на 320px вообще действовать.

    Порог написан руками, и в этом его слабое место: @media
    (max-width: 240px) не сработает на экране в 320px, а страница всё
    равно нарисуется двумя колонками и уедет вбок. Проверка на
    присутствие такого отката молчала бы ровно на той ширине, ради
    которой он написан, поэтому граница сравнивается с 320px — и
    делается это в media_applies, откуда в правила попадает только то,
    что на 320px действительно действует. Отката, чей порог не дотягивает
    до целевого экрана, здесь просто не будет: порог отсеется, и
    отсутствие отката станет пустым списком, а не ложным «есть».
    """
    narrow = [m for m, _, _ in rules if "max-width" in " ".join(m)]
    if not narrow:
        errors.append(
            f"style.css: ни один откат не действует на {MIN_WIDTH}px — "
            "страница останется в двух колонках и поедет вбок"
        )
        return

    inner = "\n".join(body for m, _, body in rules if "max-width" in " ".join(m))
    rows = [
        r.split()
        for decl in re.findall(r"grid-template-areas\s*:(.*?);", inner, re.DOTALL)
        for r in re.findall(r"['\"]([^'\"]*)['\"]", decl)
    ]
    if not rows:
        errors.append(
            "@media: области не перестроены в одну колонку — блок не "
            "объявляет grid-template-areas, и main остаётся двухколоночным"
        )
    elif any(len(r) != 1 for r in rows):
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
    notes.append(f"Откат в одну колонку действует на {MIN_WIDTH}px")


def check_fixed_widths(rules, available: float) -> None:
    """Ни одна фиксированная ширина в px не должна быть шире полосы контента.

    Это второй, чисто декларативный источник вылета за край: бокс шириной
    320px внутри полосы в 288px не переносится и не сжимается, страница
    получает горизонтальную прокрутку, а правило при этом написано
    безупречно. Правила @media print отсечены в live_rules: на бумаге
    полоса другая, и ругаться на неё было бы неверно.
    """
    widest = 0.0
    for media, selector, body in rules:
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


def check_nowrap_runs(rules, tree: Tree, tokens: dict[str, str], root: Node, outer: float) -> float:
    """Главная проверка: неразрывная строка обязана влезать в полосу.

    Сверяется не с полосой страницы, а с полосой КОНТЕЙНЕРА: у плитки
    внутри .spotlight между ней и страницей стоят поля и рамка панели,
    и 288px ей ничего не говорят.

    Возвращает ширину самого широкого бокса — из неё получается та
    минимальная ширина экрана, на которой визитка ещё стоит.
    """
    worst = 0.0
    worst_label = "—"
    measured = 0
    for _, selector, body in rules:
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
            try:
                raising_parts(rules, node, "padding")
                raising_parts(rules, node, "border")
                raising_parts(rules, node, "width")
            except ValueError as e:
                errors.append(
                    f"style.css: {selector} — {e}; бокс строки {text!r} посчитан "
                    "бы без этого правила и вышел бы уже своей настоящей"
                )
                continue
            run = advance * font_px * len(text)
            box = run + box_overhead(rules, node, tokens, font_px)
            available = container_width(rules, node, root, outer, tokens, font_px)
            measured += 1
            if box > worst:
                worst = box
                worst_label = f"{selector} {text!r}"
            if box > available:
                errors.append(
                    f"{selector}: неразрывная строка {text!r} — {box:.0f}px "
                    f"({len(text)} знаков × {advance:g}em × {font_px:g}px + "
                    f"оформление {box - run:.0f}px), а её контейнер на "
                    f"{MIN_WIDTH}px отдаёт {available:g}px. Строка не "
                    "переносится и вытолкнет страницу за правый край; нужен "
                    "перенос или сокращение подписи"
                )
    if measured:
        notes.append(
            f"Неразрывных строк измерено: {measured}, самая широкая — "
            f"{worst_label}: {worst:.0f}px"
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

    outer, side_total, available = content_width(css, tokens)
    print(f"Обёртка на {MIN_WIDTH}px: {outer:g}px, из них поля {side_total:g}px, детям {available:g}px")

    # Один раз отсекаются откаты, не действующие на экране MIN_WIDTH, и
    # дальше все проверки работают с одним и тем же списком правил.
    rules = live_rules(css)
    tree = Tree()
    tree.feed(html)

    # Проверки по контейнерам считают от ширины РАМКИ полосы, а не от её
    # внутренней полосы: оформление корня вычитает container_width, иначе
    # оно вычлось бы дважды — один раз в content_width, второй в обходе.
    root = strip_root_of(tree)
    if root is None:
        errors.append("index.html: нет .wrapper — считать полосу контейнера не от чего")
        root = Node("div", ("wrapper",), None)

    check_narrow_fallback(rules)
    check_fixed_widths(rules, available)
    check_readable_selectors(rules, tree, tokens)
    check_flex_rows(rules, tree, tokens, root, outer)
    worst = check_nowrap_runs(rules, tree, tokens, root, outer)

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