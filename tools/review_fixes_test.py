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

def test_panel_focus_not_clipped() -> None:
    """Обводка фокуса на строках панели не должна срезаться её же overflow.

    Панель обрезает углы через overflow: hidden, а outline с offset 2px
    рисуется за пределами бокса строки. Клавиатурный пользователь на
    первой строке не видел индикатора фокуса почти совсем.
    """
    css = read("css/style.css")
    panel = re.search(r"\.panel\s*\{(.*?)\}", css, re.DOTALL)
    assert panel is not None, "нет правила .panel"

    has_overflow_hidden = "overflow: hidden" in panel.group(1)
    has_inset_focus = re.search(
        r"\.panel\s+\.card:focus-visible\s*\{[^}]*outline-offset:\s*-2px", css, re.DOTALL
    )

    check(
        "focus-ring not clipped in .panel",
        (not has_overflow_hidden) or has_inset_focus is not None,
        "у .panel есть overflow: hidden и нет outline-offset: -2px — "
        "обводка фокуса на строках обрезается панелью",
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