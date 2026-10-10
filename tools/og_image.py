#!/usr/bin/env python3
"""Собрать превью для соцсетей из палитры самой страницы.

Картинка og:image раньше была сделана руками один раз и с тех пор лежала
бинарём: правки страницы её не трогали, и к моменту редизайна на ней
остались зелёный `$` из удалённой терминальной эстетики и строка «10+ лет
в информационной безопасности», которую страница уже не повторяет.
Превью в Telegram или Discord показывало то, чего на странице нет.

Скрипт читает палитру из css/tokens.css и собирает картинку из тех же
токенов, которыми нарисован сам whlab.ru. Превью и страница расходятся
теперь только если разойдутся токены — а токены проверяются verify.py.

Запуск: python tools/og_image.py
Код возврата: 0 — картинка собрана, 1 — нет.

Зависимости: Node не нужен. Нужен установленный Edge и Pillow.
    pip install Pillow

Почему рендер браузером, а не рисование Pillow'ом: карточка набирается
теми же шрифтами, что и страница, а шрифты в проекте лежат в woff2, а
Pillow понимает только ttf/otf. Конвертировать через браузер значит
рисовать ровно тем, что видит посетитель.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "og_image.html"
OUTPUT = ROOT / "static" / "ogimage.webp"

WIDTH = 1200
HEIGHT = 630

# Edge — самый предсказуемый из установленных: путь один и тот же на
# любой машине этой команды, в отличие от Chrome, которого может не быть.
EDGE_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)


def die(message: str) -> "None":
    print(f"ОШИБКА: {message}", file=sys.stderr)
    sys.exit(1)


def find_edge() -> Path:
    for path in EDGE_CANDIDATES:
        if path.exists():
            return path
    die("не найден Microsoft Edge — путь к нему задан в EDGE_CANDIDATES")


def palette() -> dict[str, str]:
    """Цвета тёмной темы из tokens.css.

    Берётся блок :root, а не [data-theme='light']: превью показывается
    в ленте, где фон тёмный, и светлая палитра там выглядела бы пятном.
    Значения берутся как есть, без разбора rgba — превью непрозрачное.
    """
    raw = (ROOT / "css" / "tokens.css").read_text(encoding="utf-8")
    m = re.search(r":root\s*\{(.*?)\n\}", raw, re.DOTALL)
    if m is None:
        die("в tokens.css не найден блок :root")
    clean = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    found = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})\s*;", clean))
    needed = ("--bg", "--surface", "--surface-2", "--text-strong", "--muted", "--accent", "--border")
    missing = [n for n in needed if n not in found]
    if missing:
        die("в :root нет токенов: " + ", ".join(missing))
    return {n: found[n] for n in needed}


def render(html: Path, png: Path, edge: Path, profile: Path) -> None:
    """Снять скриншот шаблона.

    --user-data-dir обязателен и обязан быть отдельным: без него Edge
    берёт профиль пользователя, где накопленные расширения и флаги
    могут изменить результат. Меньший профиль — предсказуемее.
    """
    cmd = [
        str(edge),
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size={WIDTH},{HEIGHT}",
        f"--user-data-dir={profile}",
        f"--screenshot={png}",
        html.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=60)
    if not png.exists():
        die(f"Edge не собрал скриншот (код {proc.returncode}): {proc.stderr.decode(errors='replace')[:400]}")


def encode(png: Path, webp: Path) -> None:
    """PNG → WebP.

    Webp, а не png: превью улетает в ленты при каждом репосте, и 5 КБ
    против 10 КБ на плоской карточке — это разница, которую видно в
    сети мобильного оператора, а не только в байтах репозитория.
    """
    try:
        from PIL import Image, features
    except ImportError:
        die("нужен Pillow: pip install Pillow")
    if not features.check("webp"):
        die("сборка Pillow без поддержки webp")
    with Image.open(png) as im:
        im.convert("RGB").save(webp, "WEBP", quality=88, method=6)


def main() -> int:
    if not TEMPLATE.exists():
        die(f"нет шаблона {TEMPLATE.relative_to(ROOT)}")
    edge = find_edge()
    colors = palette()

    html = TEMPLATE.read_text(encoding="utf-8")
    for token, value in colors.items():
        html = html.replace(f"{{{{{token}}}}}", value)
    leftover = re.findall(r"\{\{[a-z-]+\}\}", html)
    if leftover:
        die("в шаблоне остались неподставленные токены: " + ", ".join(sorted(set(leftover))))

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        page = tmpdir / "og.html"
        png = tmpdir / "og.png"
        # Шрифты лежат в static/, а страница-шаблон лежит во временной
        # папке: путь к шрифтам в шаблоне задан абсолютным файловым URL и
        # подставляется сюда, иначе относительный ушёл бы в никуда.
        html = html.replace("{{FONT_MONO}}", (ROOT / "static" / "fonts" / "jetbrains-mono-latin.woff2").as_uri())
        html = html.replace("{{FONT_SANS}}", (ROOT / "static" / "fonts" / "ubuntu-latin-700-normal.woff2").as_uri())
        page.write_text(html, encoding="utf-8")
        render(page, png, edge, tmpdir / "profile")
        encode(png, OUTPUT)

    before = OUTPUT.stat().st_size if OUTPUT.exists() else 0
    print(f"Превью собрано: {OUTPUT.relative_to(ROOT)} — {WIDTH}x{HEIGHT}, {OUTPUT.stat().st_size} байт")
    return 0


if __name__ == "__main__":
    sys.exit(main())
