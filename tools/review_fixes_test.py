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

def _rules(css: str) -> list[tuple[int, str, str]]:
    """Правила файла как (номер по порядку, селектор, тело).

    Порядок в файле — часть каскада, поэтому он и сохраняется: два
    правила одинаковой специфичности решает именно то, которое ниже.
    Комментарии снимаются, иначе объяснение про -2px посчиталось бы за
    само объявление.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out: list[tuple[int, str, str]] = []
    prelude = ""
    i, n, order = 0, len(css), 0
    while i < n:
        if css[i] == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            selector = " ".join(prelude.split())
            if selector and not selector.startswith("@"):
                out.append((order, selector, css[i + 1:j - 1]))
            order += 1
            prelude = ""
            i = j
        elif css[i] == ";":
            prelude = ""
            i += 1
        else:
            prelude += css[i]
            i += 1
    return out


def _specificity(selector: str) -> tuple[int, int, int]:
    """Специфичность (id, класс, элемент) по Каскаду 2.

    Псевдокласс — это класс, псевдоэлемент — элемент: именно поэтому
    `.panel .row:focus-visible` (0,3,0) и перебивает `.row:focus-visible`
    (0,2,0), даже объявленный ниже.
    """
    ids = len(re.findall(r"#[\w-]+", selector))
    elements = len(re.findall(r"(?<![\w.#:])[a-zA-Z][\w-]*", selector)) + len(re.findall(r"::[\w-]+", selector))
    classes = len(re.findall(r"\.[\w-]+", selector)) + len(re.findall(r"(?<!:):(?!:)[\w-]+", selector))
    classes += len(re.findall(r"\[[^\]]*\]", selector))
    return ids, classes, elements


def _winning_offset(rules) -> float | None:
    """Какой outline-offset в итоге получит строка панели.

    Считается каскад, а не ищется подстрока. Разница между этими двумя
    подходами стоила одного провалившегося теста: правило
    `.panel .row:focus-visible` с -2px есть, общий список фокуса ниже
    тоже есть, но стоит ли ПОСЛЕ него — вопрос каскада, и на него
    отвечает специфичность. Если бы специфичности у правила не было,
    побеждал бы общий отступ 2px, а правило с -2px так и осталось бы
    мёртвым — присутствующим в файле и ни на что не влияющим.
    """
    best: tuple[tuple[int, int, int], int, float] | None = None
    for order, selector, body in rules:
        m = re.search(r"(?<![\w-])outline-offset\s*:\s*(-?[\d.]+)px", body)
        if m is None:
            continue
        for part in selector.split(","):
            part = " ".join(part.split())
            if ".row:focus-visible" not in part:
                continue
            candidate = (_specificity(part), order, float(m.group(1)))
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return best[2] if best else None


def test_panel_focus_not_clipped() -> None:
    """Обводка фокуса на строках панели не должна срезаться её же overflow.

    Панель обрезает углы через overflow: hidden, а outline с offset 2px
    рисуется за пределами бокса строки. Клавиатурный пользователь на
    первой строке не видел индикатора фокуса почти совсем.

    Класс строки сегодня `.row`, а не `.card`: плитка проектов стала
    строкой панели. Поэтому проверка спрашивает не «есть ли правило с
    -2px», а «какой отступ в итоге получит строка внутри панели» — см.
    _winning_offset. Строка в файле этого не доказывает: мёртвое правило
    с -2px под общим списком фокуса выглядит в тексте точно так же, как
    живое, а кольцо при этом срезается по-старому.
    """
    css = read("css/style.css")
    panel = re.search(r"\.panel\s*\{(.*?)\}", css, re.DOTALL)
    assert panel is not None, "нет правила .panel"

    has_overflow_hidden = "overflow: hidden" in panel.group(1)
    rules = _rules(css)
    winner = _winning_offset(rules)

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
        f"outline-offset: {winner:g}px — кольцо рисуется за пределами строки "
        "и срезается панелью",
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