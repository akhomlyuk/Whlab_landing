#!/usr/bin/env python3
"""Воспроизводление трёх дефектов ревью. Каждый тест падает на текущем коде.

Запуск: python tools/review_fixes_test.py
Код возврата: 0 — все тесты прошли, 1 — есть провалы.
"""
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parent.parent

failures: list[str] = []
passes: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name: str, ok: bool, detail: str) -> None:
    if ok:
        passes.append(name)
    else:
        failures.append(f"{name}: {detail}")


# --- Дефект 1: фокус-кольцо срезается overflow:hidden на .panel -----------

def _rules(css: str) -> list[tuple[tuple[str, ...], int, str, str]]:
    """Правила файла как (медиа-цепочка, номер по порядку, селектор, тело).

    Порядок в файле — часть каскада, поэтому он и сохраняется: два
    правила одинаковой специфичности решает именно то, которое ниже.
    Счётчик сквозной, включая вложенные правила: номер, выданный внутри
    @media, должен быть БОЛЬШЕ номера всего, что стояло до блока. Иначе
    правило с отступом 2px внутри @media (max-width: 640px) получило бы
    меньший номер, чем настоящее -2px выше по файлу, и при равной
    специфичности проиграло бы — а на экране уже 640px оно как раз и
    побеждает. Комментарии снимаются, иначе объяснение про -2px
    посчиталось бы за само объявление.

    ВНУТРЬ @media заходится, а не перескакивается. Раньше любое правило
    под @media просто выпадало из разбора, и каскад считался по одной
    лишь широкой половине файла. Условие медиа вычислить нельзя,
    поэтому решает _worst_case_offset.
    """
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out: list[tuple[tuple[str, ...], int, str, str]] = []
    counter = [0]

    def walk(source: str, media: tuple[str, ...]) -> None:
        prelude = ""
        i, n = 0, len(source)
        while i < n:
            if source[i] == "{":
                depth, j = 1, i + 1
                while j < n and depth:
                    if source[j] == "{":
                        depth += 1
                    elif source[j] == "}":
                        depth -= 1
                    j += 1
                selector = " ".join(prelude.split())
                if selector.startswith("@media"):
                    walk(source[i + 1:j - 1], media + (selector,))
                elif selector and not selector.startswith("@"):
                    out.append((media, counter[0], selector, source[i + 1:j - 1]))
                counter[0] += 1
                prelude = ""
                i = j
            elif source[i] == ";":
                prelude = ""
                i += 1
            else:
                prelude += source[i]
                i += 1

    walk(clean, ())
    return out


def _declared(body: str, prop: str) -> str | None:
    """Значение ПОСЛЕДНЕГО объявления prop в теле правила.

    Именно последнего: в каскаде побеждает написанное ниже, а re.search
    брал первое. Здесь ошибка уходила вбок — к отступу 2px вместо -2px,
    то есть к провалу на годном коде, — но по счастливой случайности
    всегда в красную сторону, и заметить её было трудно.
    """
    found = re.findall(rf"(?<![\w-]){re.escape(prop)}\s*:\s*([^;{{}}]+)", body)
    return found[-1].strip() if found else None


def _specificity(selector: str) -> tuple[int, int, int]:
    """Специфичность (id, класс, элемент) по Каскаду 2.

    Псевдокласс считается классом, псевдоэлемент — элементом: именно
    поэтому `.panel .row:focus-visible` (0,3,0) перебивает
    `.row:focus-visible` (0,2,0), даже объявленный ниже.

    Порядок подсчёта важен. Старый вариант искал `[a-zA-Z][\\w-]*` по всей
    строке и находил `visible` в `.row:focus-visible` (перед ним стоит
    дефис, а он в класс запрета не входил) и `href` внутри `[href]` —
    то есть насчитывал лишние элементы: `.row:focus-visible` получался
    (0,2,1) вместо (0,2,0). Решения это не переворачивало, потому что
    лишний элемент появлялся у обоих соперников одинаково, но «по
    Каскаду 2» в докстринге было неправдой. Теперь сначала вырезаются
    атрибуты, id, классы и псевдоклассы, и остаются одни имена тегов.
    """
    ids = len(re.findall(r"#[A-Za-z][\w-]*", selector))
    classes = len(re.findall(r"\.[A-Za-z][\w-]*", selector))
    classes += len(re.findall(r"\[[^\]]*\]", selector))
    classes += len(re.findall(r"(?<!:):(?!:)[A-Za-z][\w-]*", selector))

    rest = re.sub(r"\[[^\]]*\]", " ", selector)
    rest = re.sub(r"#[A-Za-z][\w-]*", " ", rest)
    rest = re.sub(r"\.[A-Za-z][\w-]*", " ", rest)
    rest = re.sub(r"::[A-Za-z][\w-]*", "x", rest)          # псевдоэлемент — элемент
    rest = re.sub(r"(?<!:):[A-Za-z][\w-]*", " ", rest)     # псевдокласс — класс
    elements = len(re.findall(r"(?<![\w-])[A-Za-z][\w-]*", rest))
    return ids, classes, elements


def _subject_of(part: str) -> str:
    """Правая часть селектора — та, к чему он относится.

    `#best .panel` относится к `.panel`, и именно он перебивает
    `.panel { overflow: visible }` по специфичности. Сравнение строкой
    целиком такой селектор отвергло бы, а подстрока нашла бы заодно и
    `.panel__title`, а это вовсе не `.panel`.
    """
    right = re.split(r"[\s>+~]+", part.strip())[-1]
    right = re.sub(r"::[A-Za-z][\w-]*", "", right)
    right = re.sub(r":[A-Za-z][\w-]*(?:\([^)]*\))?", "", right)
    right = re.sub(r"\[[^\]]*\]", "", right)
    return " ".join(right.split())


def _print_is_harmless(rules) -> bool:
    """Снимает ли @media print обрезание у .panel.

    Печать исключается из худшего случая не по привычке, а потому что
    на бумаге кольцо обрезать нечем: если ПОБЕДИВШЕЕ правило .panel в
    печати ставит overflow: visible, обрезания там нет. Если кто-нибудь
    это правило снимет или перебьёт, утверждение перестанет быть
    самоочевидным и печать вернётся в разбор — где она и должна
    высказать своё.

    Побеждает каскад, а не порядок в файле: `#best .panel { overflow:
    hidden }` (1,1,0) перебивает `.panel { overflow: visible }` (0,1,0)
    где бы ни стоял. Предикат, который брал последнее по файлу, такую
    печать объявлял безобидной — а кольцо на бумаге срезалось.
    Предыдущий его вариант был строго хуже: сверял селектор подстрокой и
    принимал любое объявление overflow, не спрашивая, какое выигрывает.
    """
    best: tuple[bool, tuple[int, int, int], int, str] | None = None
    for media, order, selector, body in rules:
        if not any("print" in m for m in media):
            continue
        value = _declared(body, "overflow")
        if value is None:
            continue
        for part in selector.split(","):
            part = " ".join(part.split())
            if _subject_of(part) != ".panel":
                continue
            important = "!important" in body
            candidate = (important, _specificity(part), order, value)
            if best is None or candidate[:3] > best[:3]:
                best = candidate
    return best is not None and best[3].startswith("visible")


def _worst_case_offset(rules) -> tuple[float | None, str]:
    """Худший отступ, который строка панели получит хоть где-нибудь.

    Условие @media вычислить нельзя, поэтому все откаты считаются
    действующими разом: если хоть на одном экране кольцо уедет наружу,
    страница не годна, даже если на остальных всё верно. Альтернатива —
    объявить условие неразрешимым и отказаться проверять вовсе, но тогда
    прогон молчал бы на любой будущей правке отката, а это ровно тот
    случай, ради которого проверка написана.

    Печать из худшего случая убрана, если _print_is_harmless.
    """
    skip_print = _print_is_harmless(rules)
    best: tuple[bool, tuple[int, int, int], int, float] | None = None
    where = "—"
    for media, order, selector, body in rules:
        if skip_print and any("print" in m for m in media):
            continue
        value = _declared(body, "outline-offset")
        if value is None:
            continue
        m = re.match(r"(-?[\d.]+)px\s*(!important)?", value)
        if m is None:
            continue
        for part in selector.split(","):
            part = " ".join(part.split())
            if ".row:focus-visible" not in part:
                continue
            candidate = (bool(m.group(2)), _specificity(part), order, float(m.group(1)))
            if best is None or candidate[:3] > best[:3]:
                best = candidate
                where = f"{part} (в {' и '.join(media) if media else 'всегда'})"
    return (best[3] if best else None), where



def test_panel_focus_not_clipped() -> None:
    """Обводка фокуса на строках панели не должна срезаться её же overflow.

    Панель обрезает углы через overflow: hidden, а outline с offset 2px
    рисуется за пределами бокса строки. Клавиатурный пользователь на
    первой строке не видел индикатора фокуса почти совсем.

    Класс строки сегодня `.row`, а не `.card`: плитка проектов стала
    строкой панели. Поэтому проверка спрашивает не «есть ли правило с
    -2px», а «какой отступ в итоге получит строка внутри панели» — см.
    _worst_case_offset. Строка в файле этого не доказывает: правило с
    -2px под общим списком фокуса выглядит в тексте точно так же, как
    живое, а кольцо при этом срезается по-старому. То же и с откатом:
    override с отступом 2px внутри @media ничем не отличается по тексту
    от нужного -2px, пока не посчитаешь каскад целиком.
    """
    css = read("css/style.css")
    panel = re.search(r"\.panel\s*\{(.*?)\}", css, re.DOTALL)
    assert panel is not None, "нет правила .panel"

    has_overflow_hidden = "overflow: hidden" in panel.group(1)
    rules = _rules(css)
    winner, where = _worst_case_offset(rules)

    if winner is None:
        check(
            "focus-ring not clipped in .panel",
            not has_overflow_hidden,
            "у .panel есть overflow: hidden и нет ни одного правила фокуса "
            "для .row — обводка срезается панелью, а индикатора нет вовсе",
        )
        return

    check(
        "focus-ring not clipped in .panel",
        (not has_overflow_hidden) or winner <= 0,
        f"у .panel есть overflow: hidden, а строка внутри него получает "
        f"outline-offset: {winner:g}px (побеждает {where}) — кольцо рисуется "
        "за пределами строки и срезается панелью",
    )


# --- Дефект 2: печать теряет фирменные цвета -----------------------------

def test_print_overrides_brand_colors() -> None:
    """Печать обязана переопределить --brand-ink, --tg и --accent-soft.

    Печать объявлена реальным сценарием (визитку печатают). Без
    переопределения белый GitHub-знак печатался белым по белому и просто
    исчезал, а --accent-soft оставлял голубоватый квадрат аватара.
    """
    css = read("css/style.css")
    m = re.search(r"@media\s*print\s*\{(.*)\}\s*$", css, re.DOTALL)
    assert m is not None, "нет @media print"
    block = m.group(1)

    missing = [t for t in ("--brand-ink", "--tg", "--accent-soft") if t not in block]
    check(
        "print overrides brand colors",
        not missing,
        f"@media print не переопределяет: {', '.join(missing)} — "
        "фирменные знаки печатаются белым по белому или цветным по бумаге",
    )


# --- Дефект 4: знак на акцентной кнопке снова стал бы синим по синему ----

def test_accent_pill_icon_inherits() -> None:
    """Знак на .pill--accent обязан наследовать её цвет, а не быть --tg.

    Глиф главного перехода на канал ложился --tg на --accent: 1.26:1 в
    светлой теме и 1.41:1 в тёмной — вчетверо ниже порога графики, то
    есть знак просто исчезал. Причина была в каскаде, а не в палитре:
    класс висит на внутреннем <span>, и правило с --tg перебивало
    наследование от кнопки.

    Проверка спрашивает не «есть ли где-то color: inherit», а что
    РЕШАЕТ каскад для .pill--accent .pill__icon: побеждает последнее
    объявление для этой пары «селектор + свойство». Иначе откат правила
    к `color: var(--tg)` проходил бы молча — а это ровно тот баг,
    ради которого правило и написано, и возврат его стоит одного
    символа в правке.
    """
    css = read("css/style.css")
    rules = _rules(css)

    winner: tuple[bool, tuple[int, int, int], int, str] | None = None
    where = "—"
    for _media, order, selector, body in rules:
        value = _declared(body, "color")
        if value is None:
            continue
        for part in selector.split(","):
            part = " ".join(part.split())
            # Селектор должен быть именно про знак ВНУТРИ акцентной
            # кнопки. Простое `.pill__icon` не годится: оно и есть
            # правило, которое перебивалось.
            if _subject_of(part) != ".pill__icon":
                continue
            if not re.search(r"(^|\s)\.pill--accent(\s|$)", part):
                continue
            candidate = ("!important" in body, _specificity(part), order, value)
            if winner is None or candidate[:3] > winner[:3]:
                winner = candidate
                where = f"{part} (правило №{order})"

    check(
        "accent pill icon inherits color",
        winner is not None and winner[3] == "inherit",
        "у .pill--accent .pill__icon нет color: inherit"
        + (f", побеждает {where} со значением {winner[3]}" if winner else "")
        + " — --tg на --accent даёт 1.26:1, и знак главного перехода "
        "на канал исчезает с кнопки",
    )


# --- Дефект 3: сеть контрастных пар дырявая -------------------------------

def test_contrast_pairs_cover_actual_usage() -> None:
    """Каждая реально используемая цветовая пара должна быть в проверке.

    Сеть, которая должна ловить следующую правку палитры, обязана
    покрывать все пары, которыми страница реально рисует: иначе
    первая же правка зелёного или приглушённого проходит молча.
    """
    verify = read("tools/verify.py")
    pairs = re.search(r"CONTRAST_PAIRS\s*=\s*\((.*?)\n\)", verify, re.DOTALL)
    assert pairs is not None, "нет CONTRAST_PAIRS"

    present = set(re.findall(r"\(\"(--[a-z0-9-]+)\",\s*\"(--[a-z0-9-]+)\"", pairs.group(1)))

    required = {
        ("--accent", "--bg"),
        ("--accent", "--surface"),
        ("--accent", "--surface-2"),
        ("--text", "--bg"),
        ("--text", "--surface"),
        ("--muted", "--bg"),
        ("--muted", "--surface"),
        ("--muted", "--surface-2"),
        ("--signal", "--bg"),
        ("--signal", "--surface"),
        ("--signal", "--surface-2"),
        ("--tg", "--surface"),
        ("--tg", "--surface-2"),
        ("--brand-ink", "--surface"),
        ("--brand-ink", "--surface-2"),
        # --gold убран из сети вместе с кубками (редизайн 2026-10-09):
        # пара проверяла бы цвет, которого на странице больше нет.
    }

    missing = sorted(required - present)
    check(
        "contrast pairs cover actual usage",
        not missing,
        f"не покрыты реально используемые пары: "
        + ", ".join(f"{a} на {b}" for a, b in missing),
    )


def main() -> int:
    test_panel_focus_not_clipped()
    test_print_overrides_brand_colors()
    test_contrast_pairs_cover_actual_usage()
    test_accent_pill_icon_inherits()

    for p in passes:
        print(f"  PASS: {p}")
    if failures:
        print()
        for f in failures:
            print(f"ПРОВАЛ: {f}")
        print(f"\n{len(failures)} провалов")
        return 1
    print(f"\n✅ OK ({len(passes)} тестов)")
    return 0


if __name__ == "__main__":
    sys.exit(main())