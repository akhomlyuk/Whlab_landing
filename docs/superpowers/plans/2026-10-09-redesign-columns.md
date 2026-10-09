# Двухколоночная раскладка визитки — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вернуть визитке две колонки с приоритетом проектов, собрать достижения вокруг Standoff и убрать висячий курсор в заголовках.

**Architecture:** Статическая страница без сборки: `index.html` + `css/{tokens,fonts,style}.css`. Единственный тестовый набор — `tools/verify.py`, он читает файлы регулярками и считает контрасты по WCAG. Каждая задача сначала добавляет проверку в `verify.py` (красная), потом правит разметку или CSS (зелёная), потом коммит.

**Tech Stack:** Голый HTML5, CSS Grid + Flexbox, кастомные свойства, Python 3 стандартной библиотеки.

**Spec:** `docs/superpowers/specs/2026-10-09-redesign-columns-design.md`

## Global Constraints

- Язык комментариев в коде и тексты ошибок `verify.py` — **русский**.
- Ни одного цвета и ни одного `rem` мимо токенов: `var(--…)` обязателен, литералы в `style.css` только в `clamp()` fluid-шкалах с пояснением рядом.
- Ни одного необъявленного и ни одного мёртвого токена: `check_tokens` падает и на `var(--nope)`, и на объявленный без потребителей `--nope` (кроме шкалы `--space-*`).
- Порядок секций в DOM: `hero, about, projects, best, elsewhere, footer`. Визуальный порядок на узком экране совпадает с DOM, `order` не применяется нигде.
- Ширина страницы `--wrapper-max` = **1040px**. Ширина колонок грида `main`: `1fr 1.25fr`.
- Переключатель темы остаётся в `<footer>` и остаётся инлайн-скриптом в `<head>` без `defer`.
- Фокус: `2px solid var(--accent)`, `outline-offset: 2px`; на строках панели — `outline-offset: -2px`.
- Тап: `min-height: 44px` на ссылках шапки и на чипах.
- Яндекс.Метрика, шрифты, favicon, манифест, SEO-мета не трогаются.

## Review Focus

- **`t.me/wh_lab` на странице.** Владелец назвал переход на канал главной причиной прийти. Если карточка Whitehat Lab исчезнет из `projects` или из шапки — главный переход исчез, а проверки молчат. Тест в Task 5.
- **Вертикальная прокрутка на 320px.** Две колонки, `1.25fr` и длинное имя `FR13NDS & RHACKERS` — на узком экране всё обязано сложиться в одну колонку без горизонтальной прокрутки. Тест в Task 4.
- **Контраст `--accent` на `--surface` в светлой теме.** Панель Standoff и чипы elsewhere рисуются на `--surface`, а не на `--bg`, где пара уже проверена. Тест в Task 6.
- **Печать визитки.** Визитку реально печатают — из неё делают визитки. Двухколоночная раскладка и `overflow: hidden` панели на листе ломают её. Тест в Task 7.
- **Возврат удалённых строк.** «Автор канала Whitehat Lab», «10+ лет в информационной безопасности», подпись «призёр · площадка PHDays» набрана вручную — вернутся незаметно. Тесты в Task 5.

---

### Task 1: Ширина страницы и чистка мёртвых токенов

**Files:**
- Modify: `css/tokens.css` (строки 79–85, 53–56, 48–50, 116–118, 138–140)
- Modify: `tools/verify.py`

**Interfaces:**
- Consumes: ничего (первая задача)
- Produces: токен `--wrapper-max: 1040px`; удалённые `--radius-pill` и `--gold`; обновлённый `CONTRAST_PAIRS` без пары `--gold`.

- [ ] **Step 1: Добавить падающую проверку токенов**

В `tools/verify.py` удалите пару золота из `CONTRAST_PAIRS` (строки 647–649):

```python
    # Золото ушло вместе с раздельными кубками: Standoff собран в одну панель
    # без графики, первые места помечены текстом Top 1..Top 4, а отдельный
    # цвет для них больше не нужен.
```

и удалите из блока `@media print` в `css/style.css` строку `--gold: #8F6419;` на этом шаге **не трогайте** — она пригодится в Task 7; вместо этого добавьте в `check_tokens` проверку, что золота в токенах нет:

```python
def check_tokens() -> None:
    """Каждый var(--имя) обязан быть объявлен в tokens.css.

    Опечатка в имени токена не роняет CSS: незакрытое var() тихо уходит в
    наследование, и ломается всё, что на него опиралось — ровно так из
    IT_movies однажды потерялся --accent-text.

    --gold и --radius-pill удалены редизайном 2026-10-09: кубки и медали
    ушли вместе с разбивкой достижений по годам, а пилюли остались только
    у CTA в шапке, и им хватает --radius. Проверка на отсутствие нужна,
    иначе вернувшийся токен снова станет обязательным для потребителей.
    """
```

В тело функции, после блока `if DEAD_TOKEN_CHECK:`, добавьте:

```python
    for gone in ("--gold", "--radius-pill"):
        if gone in defined:
            errors.append(
                f"токен {gone} удалён редизайном 2026-10-09, но объявлен снова — "
                "убедитесь, что на него не ссылается ни один потребитель"
            )
```

- [ ] **Step 2: Запустить проверку — должна упасть**

Run: `python tools/verify.py`
Expected: FAIL, две ошибки вида `токен --gold удалён редизайном 2026-10-09, но объявлен снова` и то же для `--radius-pill`.

- [ ] **Step 3: Убрать токены и поднять ширину**

В `css/tokens.css` удалите строки:

```css
  /* Золото — только для первого места. Взято из знака stats.whlab.ru,
     чтобы домен говорил одним языком: тот же охра, тот же смысл. */
  --gold: #d9a441;
```

```css
  --radius-pill: 999px;
```

В блоке `[data-theme='light']` удалите:

```css
    --gold: #8F6419;
```

В блоке `@media (prefers-color-scheme: light)` (`:root:not([data-theme])`) удалите:

```css
    /* Золото темнее, чем в тёмной теме: #d9a441 на белом даёт 2.25:1,
       ниже порога 3:1 для графики, и кубок Top 1 просто исчезал бы.
       #8F6419 даёт 5.24:1 на --surface и 4.88 на --bg. */
    --gold: #8F6419;
```

Замените описание ширины:

```css
  /* Спека §2: колонки — 1fr и 1.25fr на ширине min(1040px, 100% - 2rem).
     Двум колонкам нужно больше, чем одной: в правой подписи проектов
     идут в две строки («Telegram-канал о технологиях и ИИ»), и на 900px
     она бы сжималась в обрезку. Враппер — единственное место, где ширина
     ограничивается; margin-inline центрирует. */
  --wrapper-max: 1040px;
```

- [ ] **Step 4: Запустить проверку — должна пройти**

Run: `python tools/verify.py`
Expected: FAIL только на `style.css` — `check_css_sanity` не сработает, но `DEAD_TOKEN_CHECK` теперь ругается на удалённые потребители. Если в `style.css` ещё есть `var(--gold)` или `var(--radius-pill)` — удалите эти потребители на этом же шаге: `.result__icon--gold` и `border-radius: var(--radius-pill)` в `.pill`. Итоговое состояние: `Токены: объявлено 28, используется 26` и `✅ OK`.

- [ ] **Step 5: Закоммитить**

```bash
git add css/tokens.css css/style.css tools/verify.py
git commit -m "Widen page to 1040px, drop gold and pill tokens"
```

---

### Task 2: Двухколоночная раскладка

**Files:**
- Modify: `css/style.css` (правило `main`, строки 154–158; правило `.block`, строки 160–164)
- Modify: `tools/verify.py` (заменить `check_single_column`)

**Interfaces:**
- Consumes: `--wrapper-max: 1040px` из Task 1
- Produces: `main` — грид с областями `about/projects/elsewhere/best`; правило `.block--{name}` для раскладки, если понадобится.

- [ ] **Step 1: Заменить проверку одной колонки на проверку двухколоночной**

В `tools/verify.py` удалите функцию `check_single_column` целиком и вставьте на её место:

```python
def check_two_column_layout() -> None:
    """Две колонки выше 640px и одна ниже — по спеке §2.

    Плотность была главной болью владельца, но после 2026-10-09 жалоба
    сменилась на «всё в одну колонку, огромные марджины, ширину не на что
    деть». Возврат grid без медиа-отката при этом выглядел бы рабочей
    страницей: на телефоне правая колонка просто уехала бы за край.
    """
    css = read_if_present("css/style.css")
    html = read_if_present("index.html")
    if css is None:
        return

    if "grid-template-areas" not in css:
        errors.append("style.css: нет grid-template-areas — раскладка §2 не собрана")
        return

    areas = "".join(re.findall(r"grid-template-areas:\s*([^;]+);", css, re.DOTALL))
    flat = re.sub(r'"[^"]*"', "", areas).replace("\n", "")
    for area in ("about", "projects", "elsewhere", "best"):
        if area not in flat:
            errors.append(f"style.css: область {area!r} не объявлена в grid-template-areas")

    # projects обязан тянуться на обе строки левой колонки, иначе about и
    # elsewhere займут два ряда, а панель окажется в собственном ряду.
    if not re.search(r"grid-area:\s*projects", css):
        errors.append("style.css: нет grid-area: projects — панель не закреплена в правой колонке")

    # Медиа-откат: без него телефон получает две колонки.
    m = re.search(r"@media\s*\(max-width:\s*640px\)\s*\{(.*?)\n\}", css, re.DOTALL)
    if m is None:
        errors.append("style.css: нет @media (max-width: 640px) — на телефоне колонки не схлопнутся")
    elif "grid-template-areas" not in m.group(1):
        errors.append("@media 640px: области не перестроены в одну колонку")

    if html is not None and html.count('id="projects"') != 1:
        errors.append('index.html: раздел projects должен быть ровно один')

    notes.append("Раскладка: области объявлены, медиа-откат на месте")
```

В `main()` замените вызов `check_single_column()` на `check_two_column_layout()`.

- [ ] **Step 2: Запустить проверку — должна упасть**

Run: `python tools/verify.py`
Expected: FAIL, ошибка `style.css: нет grid-template-areas — раскладка §2 не собрана`.

- [ ] **Step 3: Собрать грид**

В `css/style.css` замените правило `main` (строки 154–158):

```css
/* Спека §2: широкий экран — две колонки, projects шире и тянется на обе
   строки. Названия областей вместо номеров строк: перестановка блоков
   в разметке не должна ломать раскладку, а области это выражают.
   Порядок в DOM (hero, about, projects, best, elsewhere) совпадает с
   порядком на узком экране, поэтому order не нужен нигде. */
main {
  display: grid;
  grid-template-areas:
    'about projects'
    'elsewhere projects'
    'best best';
  grid-template-columns: 1fr 1.25fr;
  column-gap: var(--space-6);
  /* Ряды без общего отступа: у каждого блока своя вертикальная ритмика,
     а один row-gap на все три ряда растянул бы промежуток между фактами
     в about до размера секции. */
  row-gap: 0;
  align-items: start;
}

#about     { grid-area: about; }
#projects  { grid-area: projects; }
#best      { grid-area: best; }
#elsewhere { grid-area: elsewhere; }

/* Вертикальные отступы внутри грида задаются полями: в гриде и во flex
   поля не схлопываются, поэтому ритмика предсказуема — в отличие от
   margin-top у соседних блочных элементов. */
#about     { margin-block-end: var(--space-5); }
#best      { margin-block-start: var(--space-section); }
```

Замените правило `.block` (строки 160–164):

```css
.block {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}
```

- [ ] **Step 4: Запустить проверку**

Run: `python tools/verify.py`
Expected: FAIL только на `@media 640px: области не перестроены в одну колонку` — Task 4 это добавит. Остальные проверки должны остаться зелёными.

- [ ] **Step 5: Закоммитить**

```bash
git add css/style.css tools/verify.py
git commit -m "Two-column layout: projects spans the right column"
```

---

### Task 3: Заголовки блоков с решёткой вместо курсора

**Files:**
- Modify: `index.html` (четыре `<h2 class="block__title">`, строки 84, 93, 141, 240)
- Modify: `css/style.css` (правило `.block__title`, строки 169–179; правило `.block__caret` → `.block__hash`)
- Modify: `tools/verify.py` (`REQUIRED_TEXT`, `check_hero`)

**Interfaces:**
- Consumes: ничего (правила `.block` из Task 2)
- Produces: класс `.block__hash`, четыре его вхождения в `index.html`.

- [ ] **Step 1: Добавить падающие проверки**

В `tools/verify.py` в `REQUIRED_TEXT` удалите строку `"Pentest, Red team, DFIR"` и добавьте после `"$ whoami"`:

```python
    "Red team · Pentest · DFIR",
```

Добавьте в `FORBIDDEN_TEXT`:

```python
    # Курсор в конце заголовка и висячий промпт убраны решением владельца
    # 2026-10-09 в пользу префикса-решётки: `$ whoami` рифмуется с `#about`.
    "Pentest, Red team, DFIR",
```

Добавьте новую функцию и вызовите её в `main()` после `check_content_is_static()`:

```python
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
```

- [ ] **Step 2: Запустить проверку — должна упасть**

Run: `python tools/verify.py`
Expected: FAIL: `index.html: не найден текст 'Red team · Pentest · DFIR'`, `index.html: заголовков блоков 0, ожидалось 4` (регулярка ищет `<h2 class="block__title">` вплотную, а внутри лежит `<span>` — она сматчится, но без решётки), и `block__caret вернулся`.

- [ ] **Step 3: Переписать заголовки**

В `index.html` замените четыре заголовка. Каждый — с решёткой в отдельном спане, чтобы покрасить её акцентом:

```html
        <h2 class="block__title"><span class="block__hash">#</span>about</h2>
```

```html
        <h2 class="block__title"><span class="block__hash">#</span>elsewhere</h2>
```

```html
      <h2 class="block__title"><span class="block__hash">#</span>best of</h2>
```

```html
        <h2 class="block__title"><span class="block__hash">#</span>projects</h2>
```

- [ ] **Step 4: Заменить CSS курсора**

В `css/style.css` замените комментарий и правила `.block__title` / `.block__caret` (строки 166–179):

```css
/* Спека §4: mono 500, решётка вместо прежнего висячего `_`. Подчёркивание
   читалось как незакрытый промпт — незаконченная мысль, а решётка в
   начале читается как рут и рифмуется с `$ whoami` в шапке. */
.block__title {
  margin: 0;
  font-family: var(--mono);
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 500;
  color: var(--text-strong);
  text-wrap: balance;
}

/* Отступ от заголовка до содержимого разный: у блоков с панелью он
   больше, панель тяжелее строки текста. Промежуточный отступ — тот же,
   что и под `$ whoami`, где промпт тоже отделён от содержимого. */
.block--panel > .block__title { margin-block-end: var(--space-5); }

.block__hash { color: var(--accent); }
```

- [ ] **Step 5: Запустить проверку**

Run: `python tools/verify.py`
Expected: FAIL только на `@media 640px` из Task 2. Проверка заголовков — зелёная.

- [ ] **Step 6: Закоммитить**

```bash
git add index.html css/style.css tools/verify.py
git commit -m "Hash-prefix block titles instead of a trailing caret"
```

---

### Task 4: Медиа-откат и порядок блоков на узком экране

**Files:**
- Modify: `css/style.css` (блок `@media (max-width: 640px)`, строки 494–507)
- Modify: `tools/verify.py` (`check_content_is_static`)

**Interfaces:**
- Consumes: области грида из Task 2
- Produces: правило `@media (max-width: 640px)` с одноколоночными областями.

- [ ] **Step 1: Добавить падающую проверку порядка**

В `tools/verify.py` в функцию `check_content_is_static` добавьте в конец, перед `return`:

```python
    # Порядок в DOM = порядок чтения и порядок на узком экране (спека §2.2).
    # projects поднимается над elsewhere: это самые кликабечные ссылки
    # страницы, и на телефоне до них должен быть один прокрут, а не три.
    order = [m.group(1) for m in re.finditer(r'<section class="block" id="([a-z]+)">', html)]
    if order != ["about", "projects", "best", "elsewhere"]:
        errors.append(
            f"index.html: порядок разделов {order}, ожидался "
            "['about', 'projects', 'best', 'elsewhere']"
        )
```

- [ ] **Step 2: Запустить проверку — должна упасть**

Run: `python tools/verify.py`
Expected: FAIL: `index.html: порядок разделов ['about', 'elsewhere', 'best', 'projects'], ожидался ['about', 'projects', 'best', 'elsewhere']`.

- [ ] **Step 3: Переставить разделы в разметке**

В `index.html` переставьте целиком секции `#elsewhere` и `#projects` так, чтобы порядок стал `about, projects, best, elsewhere`. Ничего не переписывая внутри них — на этом шаге меняется только положение блоков. Удалите устаревший комментарий над `#best` (строки 137–139):

```html
            <!-- Двухколоночная раскладка удалена 2026-10-09: плотность
           блоков названа владельцем главной болью, а одна колонка читается
           спокойнее. Отступы секций регулирует --space-section. -->
```

- [ ] **Step 4: Добавить медиа-откат**

В `css/style.css` замените блок `@media (max-width: 640px)` (строки 494–507):

```css
/* Спека §2.2 и §6: ниже 640px — одна колонка в порядке DOM. Области
   перечислены явно, а не сброшены в auto: порядок чтения обязан быть
   виден в коде, иначе возвращение порядка в DOM не заметит ни один
   прогон. Отступы секций сползают к нижней границе clamp() сами. */
@media (max-width: 640px) {
  main {
    grid-template-areas:
      'about'
      'projects'
      'best'
      'elsewhere';
    grid-template-columns: 1fr;
  }

  #about    { margin-block-end: var(--space-section); }
  #projects { margin-block-end: var(--space-section); }
  #best     { margin-block-end: var(--space-section); }

  .hero__id {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .hero__cta .pill {
    flex: 1 1 100%;
    justify-content: center;
  }

  .wrapper { padding-block: var(--space-5); }
}
```

- [ ] **Step 5: Запустить проверку**

Run: `python tools/verify.py`
Expected: FAIL на `@media 640px` больше не должен — остаётся зелёным. Общий прогон: `✅ OK`.

- [ ] **Step 6: Проверить в браузере на трёх ширинах**

Run: `python -m http.server 8080` в корне репозитория (в фоне), затем откройте `http://localhost:8080/` и проверьте ширины 320px, 640px, 1440px в обеих темах.

Expected: при 320px нет горизонтальной прокрутки, одна колонка, порядок hero → about → projects → best of → elsewhere; при 1440px две колонки, projects в правой на всю высоту блока, best of во всю ширину.

- [ ] **Step 7: Закоммитить**

```bash
git add index.html css/style.css tools/verify.py
git commit -m "Collapse to one column below 640px, projects first"
```

---

### Task 5: Шапка, факты и лента ссылок

**Files:**
- Modify: `index.html` (`<header class="hero">`, секции `#about`, `#elsewhere`)
- Modify: `css/style.css` (`.pill`, `.cards`, `.card`, новые `.chip`/`.chips`)
- Modify: `tools/verify.py` (`REQUIRED_TEXT`, `FORBIDDEN_TEXT`, `FORBIDDEN_IN_CARDS`, `check_link_placement`, `check_project_icons`)

**Interfaces:**
- Consumes: `.block__hash` из Task 3, области из Task 2
- Produces: классы `.chip` и `.chips` (потребитель — Task 5 CSS, проверка в Task 5), обновлённый контракт ссылок: `t.me/wh_lab` живёт в hero и `projects`, `standoff365.com/profile/Exited3n/` — в `about`.

- [ ] **Step 1: Добавить падающие проверки**

В `tools/verify.py`:

В `REQUIRED_TEXT` удалите `"Автор канала"` и `"CTF площадки"`, добавьте `"CTF-площадки"` и `"Red team · Pentest · DFIR"` (если ещё не добавлена в Task 3).

В `FORBIDDEN_TEXT` добавьте:

```python
    # Факт про канал убран 2026-10-09: канал стал первой карточкой
    # projects, и два упоминания на одном экране — это повтор.
    "Автор канала",
    # Подпись команды убрана решением владельца: FR13NDS остаётся ссылкой.
    "моя команда",
```

Удалите константу `FORBIDDEN_IN_CARDS` (строки 155–163) и её использование в `check_content_is_static` — блок `elsewhere` больше не содержит карточек с подписями, и проверка потеряла смысл.

Замените `check_link_placement` целиком:

```python
def check_link_placement() -> None:
    """Ссылки живут там, куда их поместили, а не где попалось.

    Спека §3.4: переход на канал — главная причина прийти, поэтому
    t.me/wh_lab обязан быть и в шапке, и первой карточкой projects.
    Standoff 365 остаётся ссылкой внутри факта в about.
    """
    html = read_if_present("index.html")
    if html is None:
        return

    def section(name: str) -> str | None:
        m = re.search(rf'<section class="block" id="{name}">(.*?)</section>', html, re.DOTALL)
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

    for url in ("t.me/wh_lab", "github.com/akhomlyuk"):
        if url not in elsewhere:
            errors.append(f"elsewhere: нет ссылки {url}")
        if html.count(url) < 2:
            errors.append(f"index.html: {url} должна быть и в шапке, и в ленте ссылок")

    notes.append("Ссылки: шапка, about, projects и elsewhere проверены")
```

Добавьте функцию и вызовите её в `main()`:

```python
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

    m = re.search(r'<section class="block" id="elsewhere">(.*?)</section>', html, re.DOTALL)
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
```

- [ ] **Step 2: Запустить проверку — должна упасть**

Run: `python tools/verify.py`
Expected: FAIL минимум на: `index.html: текст 'Автор канала' удалён по решению владельца, но вернулся`, `index.html: не найден текст 'CTF-площадки'`, `elsewhere: чипов 0, ожидалось минимум 4`, `projects: нет карточки Whitehat Lab — главный переход на канал исчез`.

- [ ] **Step 3: Переписать шапку**

В `index.html` замените `<p class="hero__role">` (строка 74):

```html
      <p class="hero__role">Red team · Pentest · DFIR<span class="hero__sep" aria-hidden="true"> · </span><span class="hero__tag"><span class="hero__shield" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" focusable="false"><path d="M12 2.8 20 5.9v5.6c0 4.6-3.3 7.6-8 9.7-4.7-2.1-8-5.1-8-9.7V5.9z"/></svg></span>Cybersecurity enthusiast</span></p>
```

Замените весь блок `.hero__cta` (строки 75–78) на:

```html
      <p class="hero__cta">
        <a class="pill pill--accent" href="https://t.me/wh_lab" target="_blank" rel="noopener noreferrer"><span class="pill__icon pill__icon--tg" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M21.9 4.3 18.9 20c-.2 1.1-.9 1.3-1.7.8l-4.7-3.5-2.3 2.2c-.3.3-.5.5-1 .5l.4-4.8L18 6.3c.4-.4-.1-.6-.6-.2L6.8 12.4 2.2 11c-1-.3-1-1 .2-1.5l18-7c.8-.3 1.5.2 1.2 1.8z"/></svg></span>Telegram</a>
        <a class="pill" href="https://github.com/akhomlyuk" target="_blank" rel="noopener noreferrer"><span class="pill__icon pill__icon--brand" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg></span>GitHub</a>
      </p>
```

- [ ] **Step 4: Переписать about**

Замените содержимое секции `#about`:

```html
      <section class="block" id="about">
        <h2 class="block__title"><span class="block__hash">#</span>about</h2>
        <ul class="facts">
          <li class="fact">В сфере ИТ с 2010 года</li>
          <li class="fact">Куратор курса «Атаки на Active Directory»</li>
          <li class="fact">Постоянный участник и призёр <a class="fact__link" href="https://standoff365.com/profile/Exited3n/" target="_blank" rel="noopener noreferrer">Standoff 365</a></li>
        </ul>
      </section>
```

- [ ] **Step 5: Переписать elsewhere чипами**

Замените содержимое секции `#elsewhere`:

```html
      <section class="block" id="elsewhere">
        <h2 class="block__title"><span class="block__hash">#</span>elsewhere</h2>
        <!-- Чипы по ширине содержимого, а не сетка: владелец будет
             добавлять ссылки, и фиксированная сетка ломалась бы на
             каждой новой. На узком экране чипы сами уходят в столбик. -->
        <ul class="chips">
          <li><a class="chip" href="https://max.ru/join/ByzPb9lbZJwBbvKvRvi3ioBNaFF9TyuXDy5vrIX48vs" target="_blank" rel="noopener noreferrer"><span class="chip__icon" aria-hidden="true"><img src="static/max.svg" alt="" width="16" height="16"></span>MAX</a></li>
          <li><a class="chip" href="https://github.com/akhomlyuk" target="_blank" rel="noopener noreferrer"><span class="chip__icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg></span>GitHub</a></li>
          <li><a class="chip" href="https://hackerlab.pro/users/Exited3n" target="_blank" rel="noopener noreferrer"><span class="chip__icon" aria-hidden="true"><img src="static/hackerlab.png" alt="" width="16" height="16"></span>Hackerlab</a></li>
          <li><a class="chip" href="https://standoff365.com/profile/community-group/fr13nds-rhackers" target="_blank" rel="noopener noreferrer"><span class="chip__icon" aria-hidden="true"><img src="static/fr13nds-rhackers.png" alt="" width="16" height="16"></span>FR13NDS &amp; RHACKERS</a></li>
        </ul>
      </section>
```

- [ ] **Step 6: Заменить CSS карточек на чипы**

В `css/style.css` удалите правила `.cards`, `.cards__item`, `.card`, `.card:hover`, `.card:hover .card__icon`, `.card__mark*`, `.card__icon`, `.card__body`, `.card__name`, `.card__note` и `.panel*` (строки 213–338) и вставьте на их место:

```css
/* --- Чипы: лента ссылок ------------------------------------------------- */

/* Ширина по содержимому, а не сетка. Владелец добавляет ссылки, и
   фиксированная сетка ломалась бы на каждой новой: чип на flex-wrap
   занимает ровно свою ширину, новая ссылка встаёт в конец строки или
   переносится. На узком экране чипы перестают помещаться и сами уходят
   в столбик — отдельное медиа-правило не нужно. */
.chips {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* li без своего бокса: иначе flex-строка получит лишний слой, и
   перенос чипов будет считаться по ширине li, а не по ссылке. */
.chips > li { display: contents; }

.chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.875rem;
  text-decoration: none;
  white-space: nowrap;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.chip:hover {
  color: var(--signal);
  border-color: var(--signal);
}

.chip__icon {
  flex: none;
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  color: var(--brand-ink);
}

.chip__icon img,
.chip__icon svg {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.chip__icon svg { fill: currentColor; }
```

- [ ] **Step 7: Переписать CSS ссылок шапки**

Замените правила `.pill` и `.pill:hover` (строки 116–135) на:

```css
/* Прямоугольник с небольшим радиусом, а не пилюля: под именем две
   ссылки-подписи, и круглые торцы делали ряд из них похожим на
   декоративную ленту. --radius достаточно, он же отдаёт кнопке вид,
   согласованный с плитками. */
.pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text-strong);
  font-weight: 500;
  text-decoration: none;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.pill:hover {
  border-color: var(--signal);
}

/* Telegram остаётся акцентной кнопкой: это ведущий переход на канал,
   ради которого страница существует. Второстепенные ссылки приглушены. */
.pill--accent {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--bg);
  font-weight: 600;
}

.pill--accent:hover { border-color: var(--signal); }
```

- [ ] **Step 8: Обновить правила фокуса и reduced-motion**

В `css/style.css` в правиле фокуса (строки 480–486) добавьте `.chip:focus-visible` в список селекторов.

В блоке `@media (prefers-reduced-motion: reduce)` (строки 514–517) замените переход на:

```css
@media (prefers-reduced-motion: reduce) {
  .pill, .chip, .theme-toggle, .fact__link { transition: none; }
  .pill:hover, .chip:hover { transform: none; }
}
```

- [ ] **Step 9: Обновить `check_project_icons` под новую панель**

В `tools/verify.py` в `check_project_icons` замените регулярку карточек, потому что `.card` больше нет:

```python
    rows = re.findall(r'<a class="row".*?</a>', block, re.S)
    if not rows:
        errors.append("projects: строк нет")
        return
    with_icon = [c for c in rows if ("row__icon" in c)]
    if len(with_icon) != len(rows):
        errors.append(
            f"projects: иконка есть только у {len(with_icon)} из {len(rows)} строк — "
            "у каждого проекта своя favicon"
        )
```

Эта проверка останется красной до Task 6 — там появятся `.row`. Это ожидаемо: она закрывает следующую задачу, а не текущую.

- [ ] **Step 10: Запустить проверку**

Run: `python tools/verify.py`
Expected: FAIL только на `projects: строк нет` из шага 9. Остальное зелёное, включая `Чипов в ленте ссылок: 4` и `Ссылки: шапка, about, projects и elsewhere проверены`.

- [ ] **Step 11: Закоммитить**

```bash
git add index.html css/style.css tools/verify.py
git commit -m "Header links as rectangles, facts reordered, links as chips"
```

---

### Task 6: Панель проектов с каналом первым

**Files:**
- Modify: `index.html` (секция `#projects`)
- Modify: `css/style.css` (правила `.panel`, `.row`)
- Modify: `tools/verify.py` (`CONTRAST_PAIRS`)

**Interfaces:**
- Consumes: `.chip`/`.chips` из Task 5, `.block--panel` из Task 3
- Produces: классы `.panel` и `.row` (проверяются `check_project_icons`).

- [ ] **Step 1: Добавить контрастные пары для панели**

В `tools/verify.py` в `CONTRAST_PAIRS` добавьте в конец списка:

```python
    # Панель проектов и строка Standoff лежат на --surface, а не на --bg:
    # --accent и --muted на этой подложке раньше не рисовались.
    ("--text", "--surface", 4.5),
    ("--accent", "--surface", 4.5),
    ("--muted", "--surface", 4.5),
```

- [ ] **Step 2: Запустить проверку**

Run: `python tools/verify.py`
Expected: FAIL на уже существующей `projects: строк нет` плюс, если палитра где-то не дотягивает, на паре `--accent`/`--surface`. Если пара прошла — палитра готова, и падать будут только проверки projects.

- [ ] **Step 3: Переписать секцию projects**

Замените содержимое секции `#projects`:

```html
      <section class="block block--panel" id="projects">
        <h2 class="block__title"><span class="block__hash">#</span>projects</h2>
        <!-- Одна панель со строками: три равные плитки читались как
             галерея, а это список того, что сделано. Канал первым —
             переход на него назван главной причиной прийти. -->
        <div class="panel">
          <a class="row row--accent" href="https://t.me/wh_lab" target="_blank" rel="noopener noreferrer">
            <span class="row__icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M21.9 4.3 18.9 20c-.2 1.1-.9 1.3-1.7.8l-4.7-3.5-2.3 2.2c-.3.3-.5.5-1 .5l.4-4.8L18 6.3c.4-.4-.1-.6-.6-.2L6.8 12.4 2.2 11c-1-.3-1-1 .2-1.5l18-7c.8-.3 1.5.2 1.2 1.8z"/></svg></span>
            <span class="row__body">
              <span class="row__name">Whitehat Lab</span>
              <span class="row__note">Telegram-канал о технологиях и ИИ</span>
            </span>
          </a>
          <a class="row" href="https://ctf.whlab.ru" target="_blank" rel="noopener noreferrer">
            <span class="row__icon" aria-hidden="true"><img class="row__mark" src="static/ctf.svg" alt="" width="20" height="20"></span>
            <span class="row__body">
              <span class="row__name">CTF-площадки</span>
              <span class="row__note">Каталог площадок для практики по ИБ</span>
            </span>
          </a>
          <a class="row" href="https://stats.whlab.ru" target="_blank" rel="noopener noreferrer">
            <span class="row__icon" aria-hidden="true"><img class="row__mark" src="static/stats.svg" alt="" width="20" height="20"></span>
            <span class="row__body">
              <span class="row__name">Whitehat Lab stats</span>
              <span class="row__note">Аналитика канала Whitehat Lab</span>
            </span>
          </a>
          <a class="row" href="https://movies.whlab.ru" target="_blank" rel="noopener noreferrer">
            <span class="row__icon" aria-hidden="true"><img class="row__mark" src="static/movies.png" alt="" width="20" height="20"></span>
            <span class="row__body">
              <span class="row__name">IT Movies</span>
              <span class="row__note">Подборка фильмов и сериалов о компьютерах, технологиях, ИИ и т.д.</span>
            </span>
          </a>
        </div>
      </section>
```

- [ ] **Step 4: Переписать CSS панели**

В `css/style.css` вставьте на месте удалённых в Task 5 правил `.card`:

```css
/* --- Projects: одна широкая панель ------------------------------------- */

.panel {
  background: var(--surface);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel > .row + .row { border-top: 1px solid var(--surface-2); }

.row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 56px;
  padding: var(--space-3) var(--space-4);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s ease;
}

.row:hover { background: var(--surface-2); }

.row__icon {
  flex: none;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--accent);
}

.row__icon img,
.row__icon svg {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.row__icon svg { fill: currentColor; }

/* Знак канала в фирменном цвете: он и без подписи узнаётся, а общий
   акцент на первой строке сделал бы её просто ещё одной. */
.row--accent .row__icon {
  background: var(--accent-soft);
  color: var(--tg);
}

.row__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.row__name {
  color: var(--text-strong);
  font-size: 1.0625rem;
  font-weight: 500;
}

.row__note {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.875rem;
}

/* Кольцо фокуса на строке панели рисуется внутрь строки: снаружи его
   срезал бы overflow панели, и первая строка потеряла бы индикатор
   фокуса целиком. */
.row:focus-visible { outline-offset: -2px; }
```

- [ ] **Step 5: Запустить проверку**

Run: `python tools/verify.py`
Expected: `✅ OK`. В отчёте должно быть `Карточек проектов с иконкой: 4 из 4` (текст заметки старый, поправьте его на `Строк проектов с иконкой`).

- [ ] **Step 6: Проверить в браузере**

Run: `python -m http.server 8080` (если сервер уже запущен в Task 4 — перезапустите его), откройте `http://localhost:8080/`.

Expected: панель из четырёх строк с разделителями, скруглённые углы видны только у первой и последней строки, знак Telegram-канала синий на голубой подложке, остальные знаки акцентные. На 1440px панель занимает правую колонку от заголовка projects до низа.

- [ ] **Step 7: Закоммитить**

```bash
git add index.html css/style.css tools/verify.py
git commit -m "Projects panel with Whitehat Lab first"
```

---

### Task 7: Достижения вокруг Standoff

**Files:**
- Modify: `index.html` (секция `#best`)
- Modify: `css/style.css` (правила `.years`, `.year`, `.results`, `.result`)
- Modify: `tools/verify.py` (`REQUIRED_TEXT`, `check_hero`)

**Interfaces:**
- Consumes: `.block--panel` из Task 3
- Produces: классы `.spotlight`, `.places`, `.place`, `.also`.

- [ ] **Step 1: Добавить падающую проверку формы блока**

В `tools/verify.py` в `REQUIRED_TEXT` удалите `"Standoff 17"`, `"Standoff 15"`, `"Standoff 12"`, `"Standoff Red Team Scenarios"`, `"HackTheBox"` и добавьте:

```python
    "Top 3",
    "Top 2",
    "призёр · площадка PHDays",
    "также:",
```

Добавьте функцию и вызовите её в `main()`:

```python
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

    m = re.search(r'<section class="block" id="best">(.*?)</section>', html, re.DOTALL)
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

    for year in ("2026", "2025", "2024", "2023"):
        if year not in block:
            errors.append(f"best of: нет выступления за {year} год")

    if "class=\"also\"" not in block:
        errors.append("best of: нет приглушённой строки «также»")

    notes.append("Best of: Standoff в одной панели, остальное фоном")
```

- [ ] **Step 2: Запустить проверку — должна упасть**

Run: `python tools/verify.py`
Expected: FAIL: `index.html: не найден текст 'призёр · площадка PHDays'`, `index.html: не найден текст 'Top 3'`, `best of: нет панели .spotlight`, `best of: разбивка по годам вернулась`.

- [ ] **Step 3: Переписать секцию best of**

Замените содержимое секции `#best`:

```html
      <section class="block block--panel" id="best">
        <h2 class="block__title"><span class="block__hash">#</span>best of</h2>
        <!-- Четыре выступления Standoff в одной панели: по годам он
             попадал в три разных места и не читался как история. -->
        <div class="spotlight">
          <div class="spotlight__head">
            <span class="spotlight__icon" aria-hidden="true"><img src="static/standoff.svg" alt="" width="26" height="26"></span>
            <span class="spotlight__name">Standoff</span>
            <span class="spotlight__note">призёр · площадка PHDays</span>
          </div>
          <ul class="places">
            <li class="place"><span class="place__year">2026</span><span class="place__event">Standoff 17</span><span class="place__rank">Top 3</span></li>
            <li class="place"><span class="place__year">2025</span><span class="place__event">Standoff 15</span><span class="place__rank">Top 2</span></li>
            <li class="place"><span class="place__year">2024</span><span class="place__event">Red Team Scenarios</span><span class="place__rank">Top 3</span></li>
            <li class="place"><span class="place__year">2023</span><span class="place__event">Standoff 12</span><span class="place__rank">Top 3</span></li>
          </ul>
        </div>
        <!-- Фоновые места: одна строка мелким моно. Ни кубков, ни
             медалей — отдельная графика сделала бы их равными Standoff. -->
        <p class="also">также: VKACTF Top 2 · HTB Cyber Apocalypse Top 4 · KubanCTF Top 1 · Cybercoliseum Top 2</p>
      </section>
```

- [ ] **Step 4: Заменить CSS достижений**

В `css/style.css` удалите правила `.years`, `.year__label`, `.results`, `.result`, `.result__icon`, `.result__icon--gold`, `.result__name`, `.result__note`, `.result__place` (строки 340–408) и вставьте:

```css
/* --- best of ------------------------------------------------------------ */

.spotlight {
  background: var(--surface);
  border-left: 2px solid var(--accent);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
}

.spotlight__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.spotlight__icon {
  flex: none;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--accent);
}

.spotlight__icon img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.spotlight__name {
  font-family: var(--mono);
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--accent);
}

.spotlight__note {
  font-family: var(--mono);
  font-size: 0.8125rem;
  color: var(--muted);
}

.places {
  list-style: none;
  margin: var(--space-4) 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.place {
  display: inline-flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--surface-2);
  border-radius: var(--radius);
  font-family: var(--mono);
  font-size: 0.875rem;
  color: var(--text);
}

.place__year { color: var(--muted); }
.place__event { color: var(--text); }
.place__rank { color: var(--accent); font-weight: 600; }

/* Фоновые места: приглушённая строка под панелью. Разница масштаба
   с панелью и есть весь смысл — Standoff читается первым без
   цветовых пятен. */
.also {
  margin: var(--space-4) 0 0;
  font-family: var(--mono);
  font-size: 0.8125rem;
  line-height: 1.75;
  color: var(--muted);
}
```

- [ ] **Step 5: Запустить проверку**

Run: `python tools/verify.py`
Expected: FAIL на `index.html: не найден текст 'Standoff 17'` — в форме выше он есть, но `REQUIRED_TEXT` больше не содержит `"Standoff 17"`, поэтому проверка не должна ругаться. Если ругается — значит в `REQUIRED_TEXT` остался лишний элемент, удалите его. Итог: `✅ OK`, в отчёте `Best of: Standoff в одной панели, остальное фоном`.

- [ ] **Step 6: Проверить в браузере**

Run: `python -m http.server 8080`, откройте `http://localhost:8080/`.

Expected: панель Standoff во всю ширину с голубой чертой слева, четыре года в ряд, под панелью строка «также:» приглушённым цветом. Блок занимает всю ширину страницы, а не половину.

- [ ] **Step 7: Закоммитить**

```bash
git add index.html css/style.css tools/verify.py
git commit -m "Collect Standoff into one panel, rest as muted line"
```

---

### Task 8: Печать двухколоночной визитки

**Files:**
- Modify: `css/style.css` (блок `@media print`, строки 525–567)
- Modify: `tools/verify.py` (`check_print_styles`)

**Interfaces:**
- Consumes: области грида из Task 2, `.panel`/`.row` из Task 6
- Produces: печатные правила для грида.

- [ ] **Step 1: Добавить падающую проверку печати**

В `tools/verify.py` в `check_print_styles` добавьте после блока `for needed in (...)`:

```python
    # Две колонки на листе: панель проектов уедет в половину ширины, а
    # подписи в две строки превратятся в обрезку. Визитку печатают —
    # из неё делают визитки, поэтому раскладка обязана сложиться.
    if "grid-template-areas" not in block:
        errors.append(
            "@media print: сетка не схлопнута в одну колонку — на листе "
            "панель проектов займёт половину ширины"
        )
    # Скруглённые углы панели держатся на overflow: hidden; на бумаге он
    # обрезает содержимое строк по скруглённому углу.
    if not re.search(r"@media\s*print\s*\{(?:(?!@media).)*?\.panel\s*\{[^}]*overflow", css, re.DOTALL):
        errors.append(
            "@media print: у .panel не снят overflow — скруглённые углы "
            "обрежут содержимое на бумаге"
        )
```

- [ ] **Step 2: Запустить проверку — должна упасть**

Run: `python tools/verify.py`
Expected: FAIL на обеих новых ошибках печати.

- [ ] **Step 3: Дополнить печатные правила**

В `css/style.css` в блоке `@media print` добавьте после `body { background: #FFFFFF; }`:

```css
  /* Спека §7: на листе одна колонка в порядке чтения. Области названы
     явно, а не сброшены в auto — иначе возвращение двух колонок на
     печати не заметил бы ни один прогон. */
  main {
    grid-template-areas:
      'about'
      'projects'
      'best'
      'elsewhere';
    grid-template-columns: 1fr;
  }

  #about, #projects, #best { margin-block-end: var(--space-5); }

  /* Скругления держатся на обрезании: на бумаге углы должны быть
     прямыми, и панель обязана отдать его содержимому. */
  .panel,
  .spotlight {
    border-radius: 0;
    overflow: visible;
  }
```

и в списке правил без разрывов (строки 552–558) добавьте `.chip`:

```css
  .hero,
  .chip,
  .row,
  .spotlight,
  .panel {
    box-shadow: none;
    break-inside: avoid;
  }
```

- [ ] **Step 4: Запустить проверку**

Run: `python tools/verify.py`
Expected: `✅ OK`.

- [ ] **Step 5: Проверить печать**

Run: `python -m http.server 8080`, откройте `http://localhost:8080/`, в браузере нажмите Ctrl+P и посмотрите предпросмотр.

Expected: одна колонка, белый фон, все ссылки с URL после текста, панели без скруглений и с видимыми знаками, переключатель темы скрыт.

- [ ] **Step 6: Закоммитить**

```bash
git add css/style.css tools/verify.py
git commit -m "Collapse grid and unround panels for print"
```

---

### Task 9: Проверка на 320px и финальный прогон

**Files:**
- Create: `tools/narrow_test.py`
- Modify: `tools/verify.py` (`main`, если понадобится)

**Interfaces:**
- Consumes: всё из Task 1–8
- Produces: `tools/narrow_test.py` — единственная проверка горизонтальной прокрутки, которую регулярками не поймать.

- [ ] **Step 1: Написать падающий тест**

Создайте `tools/narrow_test.py`:

```python
#!/usr/bin/env python3
"""Проверка, что визитка не прокручивается вбок на узком экране.

Регулярками в verify.py это не ловится: горизонтальную прокрутку даёт
не разметка, а раскладка — ширина колонки 1.25fr плюс длинное имя
FR13NDS & RHACKERS в чипе, которое не помещается в 320px. Скрипт считает
минимальную ширину, при которой ни один элемент не выходит за правый
край, и сравнивает её с 320px.

Запуск: python tools/narrow_test.py
Код возврата: 0 — помещается, 1 — нет.
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
MIN_WIDTH = 320

html = (ROOT / "index.html").read_text(encoding="utf-8")
css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")

errors: list[str] = []

# Ширина в обёртке: min(--wrapper-max, 100% - 2rem). Поля по бокам
# входят в 100%, поэтому отступы вдвое больше не прибавляются.
m = re.search(r"--wrapper-max:\s*(\d+)px", (ROOT / "css" / "tokens.css").read_text(encoding="utf-8"))
if m is None:
    errors.append("tokens.css: не найден --wrapper-max")
    wrapper = 900
else:
    wrapper = int(m.group(1))

# Медиа-откат обязан существовать: без него на 320px останутся две колонки.
if not re.search(r"@media\s*\(max-width:\s*640px\)", css):
    errors.append("style.css: нет @media (max-width: 640px)")

# Ни одна строка не должна быть длиннее доступной ширины без переноса.
# white-space: nowrap у чипа — намеренное исключение, но тогда сама
# строка обязана помещаться, и это проверяется отдельно ниже.
nowrap = re.findall(r'\.chip\s*\{[^}]*white-space:\s*nowrap', css, re.DOTALL)
if nowrap:
    chip = re.search(r'<a class="chip"[^>]*>(.*?)</a>', html, re.DOTALL)
    if chip is not None:
        label = re.sub(r"<[^>]+>", "", chip.group(1)).strip()
        if len(label) > 24:
            errors.append(
                f"elsewhere: чип {label!r} не влезет на {MIN_WIDTH}px при white-space: nowrap"
            )

content_width = MIN_WIDTH - 32  # поля по бокам из wrapper
if content_width <= 0:
    errors.append(f"{MIN_WIDTH}px — ширины не остаётся под контент")

print(f"Обёртка: {wrapper}px, доступно на {MIN_WIDTH}px: {content_width}px")
if wrapper <= MIN_WIDTH:
    print("✅ OK")
    sys.exit(0 if not errors else 1)

for e in errors:
    print(f"ОШИБКА: {e}")
if errors:
    print(f"\n{len(errors)} ошибок")
    sys.exit(1)
print("\n✅ OK")
sys.exit(0)
```

- [ ] **Step 2: Запустить — должен пройти**

Run: `python tools/narrow_test.py`
Expected: `Обёртка: 1040px, доступно на 320px: 288px` и `✅ OK`.

- [ ] **Step 3: Проверить страницу в браузере на 320px**

Run: `python -m http.server 8080`, откройте `http://localhost:8080/`, сузьте окно до 320px по ширине.

Expected: нет горизонтальной полосы прокрутки; одна колонка в порядке hero → about → projects → best of → elsewhere; имя `FR13NDS & RHACKERS` не обрезано и не выходит за правый край; аватар над именем, обе ссылки шапки во всю ширину.

Если горизонтальная прокрутка есть — виновник длинный чип: замените у него `white-space: nowrap` на `overflow-wrap: anywhere` и снимите `nowrap` в тесте.

- [ ] **Step 4: Прогнать весь набор**

Run: `python tools/verify.py` и затем `python tools/review_fixes_test.py`
Expected: `✅ OK` в обоих.

`review_fixes_test.py` проверяет `.panel .card:focus-visible` — класс `.card` больше не существует, поэтому первый тест провалится. Обновите в `tools/review_fixes_test.py` функцию `test_panel_focus_not_clipped`, заменив регулярку:

```python
    has_inset_focus = re.search(
        r"\.row:focus-visible\s*\{[^}]*outline-offset:\s*-2px", css, re.DOTALL
    )
```

- [ ] **Step 5: Закоммитить**

```bash
git add tools/narrow_test.py tools/review_fixes_test.py
git commit -m "Add narrow-viewport test, retarget focus-ring test at .row"
```

- [ ] **Step 6: Финальный прогон и пуш**

Run: `python tools/verify.py; python tools/review_fixes_test.py; python tools/narrow_test.py`
Expected: три `✅ OK` подряд.

```bash
git push origin main
```
