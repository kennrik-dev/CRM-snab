# Фаза 9 — «Отчёты + экспорт» (дизайн-спека)

- **Дата:** 2026-06-28
- **Ветка:** `feat/phase-9` (от `main` @ `408781a`; main = фазы 0–8)
- **Цель:** read-only конструктор управленческих выгрузок — **4 типа отчётов** с периодом и фильтрами + экспорт **Excel/PDF/CSV**. Доступ — Руководитель / Админ / Куратор (Куратор видит **все** данные); сотрудники отделов доступа не имеют.
- **Источники истины:** `docs/15-page-otchety.md`, `docs/31-api.md` §6, `docs/32-calculations.md` §8, `docs/03-roles-permissions.md`. Визуальный канон — `Concept design/index.html` (блок `<!-- REPORTS -->`) + `Concept design/zakupki-crm.js:runReport`.
- **Предыдущая фаза:** Фаза 8 «Дашборд» принята и FF-слита в main (`feat/phase-8`→`main` @ `408781a`, 2026-06-28).

---

## 1. Контекст

Реализуется последний «страничный» экран CRM — «Отчёты» (`/otchety`). На момент старта:
- Роут `/otchety` и вкладка «Отчёты» в `Tabs.tsx` существуют как **placeholder** (Фаза 0); гейтинг по роли пока не настроен.
- `backend/app/calculations.py` уже содержит все нужные примитивы: `today_moscow()`, `_parse_date()`, `position_sum`, `procedure_sum`, `proc_sum(proc, positions)` (contract_sum иначе Σ позиций), `progress`, `is_delivery_overdue` / `is_delivery_late`, `is_procedure_overdue`, `overdue_pct`, `is_upd_overdue`, `is_procedure_completed`, `_fmt_money(kopecks)`, а также шаблон `_load_dashboard_ctx(db, today)` + `dashboard(db, today)` — его и копируем.
- `permissions.py`: блок `reports` существует; `require_action("reports","view")` = ровно Админ / Руководитель / Куратор (сотрудник отдела, даже curator-нет → 403); `reports:edit` всегда False.
- `routers/dashboard.py` — эталон тонкого read-only роутера (`APIRouter(prefix=...)`, `Depends(get_db)`, гард-пользователь).
- CSS-классы страницы отчётов **уже есть** в `frontend/src/styles/zakupki-crm.css`: `.rep-layout`, `.rep-params`, `.rep-group`, `.rg-l`, `.rep-opt`(+`.on`), `.rep-sel`, `.rep-go`, `.rep-out`, `.rep-out-h`(+`.exp`), `.rep-kpis`, `.rep-kpi`(+`.l/.v`), `.rtbl`(+`th/td.r/.mono/tfoot`), `.daypill`(+`.warn/.bad`), `.parent-tag`, `.cellsub`. **Нового CSS не нужно.**
- `pyproject.toml`: `openpyxl` и `reportlab` **ещё не установлены** — добавить. `csv` — stdlib.

---

## 2. Ключевые решения (R1–R12)

**R1 — Единый «слепок отчёта».** Каждый билдер возвращает generic-структуру `{type,title,period,kpis[],sections[]}` (см. §5). Этот же слепок кормит и JSON-просмотр, и все 3 формата экспорта → один источник данных, консистентность JSON/файла.

**R2 — Билдеры в `calculations.py`, тонкий роутер.** Добавить `report_time/sums/late/people(db, today, flt)` + общий загрузчик `_load_report_ctx(db, today, flt)` и `_apply_period/_apply_filters`. Роутер `reports.py` только вызывает билдер и сериализует/рендерит. Зеркало `dashboard`/`payments`. Логика покрывается юнит-тестами без HTTP.

**R3 — Якорь периода = `parent_request.zagruzka`.** Фильтр периода (Текущий месяц / Квартал / С начала года / Произвольный) применяется к дате заведения заявки-родителя (`zagruzka`, `TEXT NOT NULL DEFAULT date('now')`) — единый якорь для всех 4 отчётов; границы `[from,to]` **включительные**. Процедуры присоединяются к родителю через `tender`; awaiting-родители фильтруются по собственной `zagruzka`.

**R4 — `time` = процедуры + заявки в Комплектации; «зависло» ≥3 дня.** Универсум: активные процедуры (не завершена, не `Отменена`, есть `block_entered_at`) **плюс** awaiting-родители (без `tender`). Дней на этапе: процедура — `сегодня − block_entered_at`; awaiting-родитель — `сегодня − zagruzka`, этап «Комплектация». Флаг «зависло» = **≥3 дня** (канон `32`§8.1, §9.3). Цвет day-pill — визуальный канон: `≥14` → `.bad`, `≥10` → `.warn` (цвет и флаг «зависло» — независимы).

**R5 — `sums`: 2 этапа по реальным блокам; завершённые учитываются; «В оплате» — фин. метрика.** Таблица этапов = строки **Закупки** (`block=zakupka`) и **Сопровождение** (`block=soprovozhdenie`), Σ `contract_sum` через `proc_sum`, + `tfoot «Итого»`. **Завершённые процедуры включены** (финансовая полнота, `32`§8 note). Третий KPI «В оплате» = Σ сумм `await`-УПД (искл. отменённые процедуры) — отдельная фин. метрика, **не** строка таблицы этапов (т.к. «оплаты» — это УПД, не `contract_sum`).

**R6 — `late`: просроченные поставки (overdue ∨ late по `32`§3) + просроченные УПД (`is_upd_overdue`).** `Отменена` исключается. Manual-УПД (без связи с процедурой/поставкой) нельзя датировать якорем периода → **при активном периоде исключаются**, при «всё время» (без периода) — входят.

**R7 — `people`: группировка по `sostavitel` (+ `dept`).** `dept` = `parent.dept`; если null — отдел создателя по `created_by → user.department`; иначе «—». Σ = `proc_sum` по не-`Отменена` процедурам родителя; count заявок — родители со `status != 'cancelled'`.

**R8 — `Отменена` исключается везде.** Завершённые процедуры: **учитываются** в финансовых отчётах (`sums`, суммы `people`), **исключаются** из операционного «времени на этапе» (`time`), входят в `late` (исторические просрочки возможны и на завершённых).

**R9 — Экспорт: Excel(openpyxl) / PDF(reportlab) / CSV(stdlib + UTF-8 BOM).** Деньги везде — форматированные строки через `_fmt_money` («1 234 567 ₽») — консистентно с UI и между форматами. Имя файла: `otchety_<type>_<YYYY-MM-DD>.<ext>` (дата = `today_moscow()`).

**R10 — PDF Cyrillic: bundled TTF.** Встроенные шрифты reportlab (Helvetica) **не рисуют кириллицу**. Регистрируем bundled `DejaVuSans.ttf` (+`DejaVuSans-Bold.ttf`) через `pdfmetrics.registerFont(TTFont(...))`; файлы кладём в `backend/app/fonts/` (license-clean, коммитим как бинарники). Альтернатива — IBM Plex (шрифт дизайна), но DejaVu проще и универсальнее.

**R11 — RBAC: `require_action("reports","view")`; Куратор видит все данные; read-only.** Сотрудник отдела (не куратор) → 403; FE прячет вкладку и роут. Запросы глобальные (без блочного scope) — как дашборд. `audit_log` не пишется (чтение).

**R12 — Валидация параметров.** `period=custom` без `date_from/date_to` или с `from>to` → 422. Неизвестный `type` ∉ {time,sums,late,people} → 404. Неизвестный `format` ∉ {excel,pdf,csv} → 422.

---

## 3. Архитектура и файлы

### Backend
| Файл | Действие |
|---|---|
| `backend/app/calculations.py` | **+** `_load_report_ctx(db,today,flt)`, `_period_range(period,date_from,date_to)→(from,to)`, `_flt`-хелперы, `report_time/sums/late/people(db,today,flt)→dict`; добавить имена в `__all__` |
| `backend/app/routers/reports.py` | **новый**: `APIRouter(prefix="/reports")`; `GET /{type}` (JSON) + `GET /{type}/export` (файл); гард `require_action("reports","view")` |
| `backend/app/schemas/reports.py` | **новый**: Pydantic-модели слепка (`ReportOut`, `Kpi`, `Section`, `Column`, cell = `str \| CellObj`) |
| `backend/app/export.py` | **новый**: `render_excel(snapshot)→BytesIO`, `render_pdf(snapshot)→BytesIO`, `render_csv(snapshot)→str`; общий ход по `sections` |
| `backend/app/fonts/DejaVuSans.ttf`, `DejaVuSans-Bold.ttf` | **новый** (бинарники, для PDF) |
| `backend/app/main.py` | подключить роутер `reports` |
| `backend/pyproject.toml` | **+** `openpyxl`, `reportlab` в `dependencies` |
| `backend/tests/test_calculations.py` | **+** юнит-тесты 4 билдеров + период/фильтры |
| `backend/tests/test_reports.py` | **новый**: HTTP-тесты (200/слепок, 403, экспорт, 404/422) |

### Frontend
| Файл | Действие |
|---|---|
| `frontend/src/api/reports.ts` | **новый**: типы слепка + `getReport(type,flt)`, `exportUrl(type,flt,format)` (или `downloadReport`) |
| `frontend/src/pages/Otchety.tsx` | **новый** (вместо placeholder): панель параметров слева + вывод справа; `useQuery(['reports',type,flt])`; экспорт = blob-download |
| `frontend/src/lib/reportsView.ts` | **новый** (pure): `cellClass(kind,level,color)`, `buildFilename(...)` — покрывается vitest |
| `frontend/src/App.tsx`, `Tabs.tsx` | гейтировать `/otchety` и вкладку «Отчёты» по `canView(perms,'reports')` |
| переиспользовать | `lib/format.ts` (money/date), существующие `.rep-*`/`.rtbl` классы |

**Без миграций БД** (все данные производные). **Без нового CSS.**

---

## 4. Четыре отчёта (детальное содержимое)

Общие параметры (`flt`): `period ∈ {month,quarter,year,custom}`, `date_from`, `date_to` (для custom), `mtr`, `supplier`, `author` — все опциональны; «без периода» = всё время.

### 4.1. `time` — «Время на этапе и зависания»
- **Универсум:**
  - процедуры: `block_entered_at` есть, `status_zakup != 'Отменена'`, **не завершена** (`not is_procedure_completed`); этап = `block` → «В закупке»/«В сопровождении»; `дней = сегодня − block_entered_at`; `srok_dd` — срок поставки.
  - awaiting-родители: `status='awaiting'`, без `tender`; этап = «Комплектация»; `дней = сегодня − zagruzka`; `proc='—'`, `supplier='—'`, `srok_dd=parent.srok`.
- **KPI:** «Заявок в работе» (count строк) · «Зависли ≥3 дн.» (count `дней≥3`) · «Ср. время на этапе» (`round(mean(дней))` + « дн.»; 0 если пусто).
- **Колонки:** `claim` Заявка (code+title) · `mono` № (proc) · `text` Поставщик · `stage` Этап (chip, color по этапу) · `days` Дней на этапе (daypill, level по 10/14) · `date` Срок поставки.
- **Сортировка:** по `дней` ↓.
- **Фильтры периода/`mtr`/`supplier`/`author`:** по родителю процедуры / самому awaiting-родителю.

### 4.2. `sums` — «Суммы по этапам и поставщикам»
- **Универсум:** все процедуры со `status_zakup != 'Отменена'` (**включая завершённые**).
- **Секция 1 «По этапам»** (колонки: `stage` Этап · `num` Заявок(count) · `money` Сумма договоров):
  - Закупки (`block=zakupka`): count + Σ `proc_sum`.
  - Сопровождение (`block=soprovozhdenie`): count + Σ `proc_sum`.
  - `footer`: Итого — Σcount + ΣΣ.
- **Секция 2 «По поставщикам»** (колонки: `text` Поставщик · `num` Кол-во · `money` Сумма): группировка по непустому `supplier`, Σ `proc_sum`, сортировка ↓.
- **KPI:** «Всего по договорам» (Σ `proc_sum` по всем строкам секции 1) · «В сопровождении» (Σ supp) · «В оплате» (Σ `amount` await-УПД, искл. отменённые процедуры).

### 4.3. `late` — «Просрочки: поставки и оплаты»
- **KPI:** «Просроч. поставок» · «Просроч. оплат».
- **Секция 1 «Поставки»** (колонки: `claim` Заявка · `mono` № · `text` Поставщик · `text` Поставка («№n» + « (с задержкой)» если `is_delivery_late`) · `percent` % позиций (`overdue_pct`) · `date-late` Срок ДД): поставки где `is_delivery_overdue ∨ is_delivery_late`, процедура не `Отменена`.
- **Секция 2 «Оплаты»** (колонки: `mono` УПД · `claim` Заявка(code+proc) · `text` Поставщик · `money` Сумма(красн.)): УПД где `is_upd_overdue`, искл. отменённые процедуры; manual-УПД — по R6.
- Пустая секция → строка `«нет»` (`cellsub`, colspan).

### 4.4. `people` — «Сводка по составителям/отделам»
- **Универсум:** родители со `status != 'cancelled'`, сгруппировано по `sostavitel`.
- **Колонки:** `text` Составитель · `text` Отдел (`dept` по R7) · `num` Заявок (Т-) (count родителей в группе) · `num` Доч. заявок (count процедур) · `money` Сумма договоров (Σ `proc_sum` по не-`Отменена` процедурам).
- Сортировка по Σ ↓.

---

## 5. Контракт данных (generic-слепок)

```jsonc
{
  "type": "time",                       // time | sums | late | people
  "title": "Время на этапе и зависания",
  "period": { "key": "month", "label": "Текущий месяц", "from": "2026-06-01", "to": "2026-06-30" },  // null если без периода
  "kpis": [ { "label": "Заявок в работе", "value": "12", "color": null }, … ],
  "sections": [
    {
      "title": null,                    // null для единственной секции; «По поставщикам» и т.п.
      "columns": [ { "key": "claim", "label": "Заявка", "kind": "claim", "align": "left" }, … ],
      "rows":  [ [ <cell>, <cell>, … ], … ],
      "footer": [ <cell>, … ]           // null если нет
    }
  ]
}
```

**Cell:** `string` **ИЛИ** объект `{ "text": str, "kind"?: str, "color"?: str, "level"?: str }`.
- `kind` ∈ `claim | mono | text | stage | days | money | date | date-late | percent`. `column.kind` — стратегия рендера колонки (FE) и выравнивания (экспорт); объект-ячейка добавляет **построчные** данные (`color`/`level`/`code`), когда они варьируются между строками.
- `claim`: `{kind:'claim', code:'Т-67', title:'Название'}` (FE: `<parent-tag>code</parent-tag> title`; экспорт: `code + ' ' + title`).
- `stage`: `{kind:'stage', text:'В закупке', color:'--proc'}` (FE → chip). Цвет этапа: В закупке → `--proc`, В сопровождении → `--supp`, Комплектация → `--wait`.
- `days`: `{kind:'days', text:'5 дн.', level:''|'warn'|'bad'}` (FE → daypill).
- `money`: `{kind:'money', text:'1 500 ₽'}`.
- `date-late`: `{kind:'date-late', text:'12.04.26'}` (FE → красная дата).
- plain `string` — текст без спец-стиля.

FE имеет карту рендера `kind → cellClass/element`; экспорт рендерит `text` (для `claim` — `code + ' ' + title`), выравнивание по `column.align`. Бэкенд — источник styling-решений (как `color` в дашборде).

---

## 6. API

| Метод | Путь | Кто | Назначение |
|---|---|---|---|
| GET | `/reports` | Руководитель, Админ, Куратор | опции фильтров `{mtr[],supplier[],author[]}` (distinct из БД) |
| GET | `/reports/{type}` | те же | слепок JSON; `?period=&date_from=&date_to=&mtr=&supplier=&author=` |
| GET | `/reports/{type}/export` | те же | файл; `?format=excel|pdf|csv&<те же фильтры>` |

> Роут `GET /reports` (без path-сегмента) регистрируется на том же роутере и **не конфликтует** с `/{type}` (у того обязателен сегмент).

- Гарды: `Depends(require_action("reports","view"))` на обоих (через `require_password_changed`).
- `type` — path-параметр; валидация по R12 (404 при неизвестном).
- `export` возвращает `Response`/`StreamingResponse`:
  - excel → `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `.xlsx`
  - pdf → `application/pdf`, `.pdf`
  - csv → `text/csv; charset=utf-8` **с UTF-8 BOM**, `.csv`
  - `Content-Disposition: attachment; filename="otchety_<type>_<YYYY-MM-DD>.<ext>"`
- Read-only → `write_audit` **не вызывается**.

---

## 7. Экспорт (детали)

- Общий ход: `title` → KPI-блок (`label: value` построчно) → каждая секция (`title?` → header из `columns[].label` → rows → `footer?`).
- **Excel (openpyxl):** workbook in-memory `BytesIO`; жирный title; KPI-строки; на секцию — строка заголовков (жирный), данные, `footer` (жирный, верхняя граница). Авто-ширина колонок по max-длине. Деньги-строки.
- **PDF (reportlab):** `SimpleDocTemplate` (A4 landscape, если широкие таблицы — иначе portrait); `Paragraph` для title; KPI — `Table` 1×N или строка; каждая секция — `Table` c `TableStyle` (header bg, grid, right-align для `align='right'`/money). **Шрифт — зарегистрированный DejaVuSans** (R10), кириллица обязательна.
- **CSV (stdlib `csv`):** `io.StringIO`; префикс `﻿` (UTF-8 BOM); `QUOTE_MINIMAL`; разделитель **`;`** (российский Excel по умолчанию). KPI-строки + секции.

---

## 8. Frontend

- `Otchety.tsx`: `.rep-layout` (grid 280px/1fr) → слева `.rep-params` (sticky): группа «Тип отчёта» (`.rep-opt`-радио, 4 шт.), «Период» (`.rep-sel`: Текущий месяц/Квартал/С начала года/Произвольный; при «Произвольный» — 2 date-input), «Фильтры» (`.rep-sel` для mtr/supplier/author, опции = distinct-значения из БД через отдельный лёгкий эндпоинт ИЛИ фиксированный список — см. §9), кнопка `.rep-go` «Сформировать». Справа `.rep-out`: `.rep-out-h` (title + `.exp` кнопки Excel/PDF/CSV) + `.rep-kpis` + `.rtbl`-таблицы секций.
- Состояние: `type`, `period`, `date_from/date_to`, `mtr/supplier/author`; `useQuery(['reports',type,flt])` (staleTime ~60s, refetchOnWindowFocus). Клик «Сформировать» → `refetch()` (или query enabled по submit-флагу).
- Экспорт: `fetch('/api/reports/<type>/export?format=…&<flt>', {credentials:'include'})` → `blob()` → `URL.createObjectURL` → клик по `<a download>`. Имя файла из `Content-Disposition` или `buildFilename(type, today, format)`.
- Гейтинг: вкладка и роут видны только если `canView(perms,'reports')`; иначе редирект на `/dashboard` (403 на BE всё равно).
- Пустое состояние: `sections` пусты/без строк → «По выбранным параметрам нет данных».

### 9. Опции фильтров (mtr/supplier/author)
МТР/Поставщик — свободный текст (`docs/30` §решения #4: не справочники). Опции dropdown’ов = **distinct-значения из БД**:
- `mtr`: `SELECT DISTINCT mtr FROM (parent_request UNION procedure) WHERE mtr IS NOT NULL`.
- `supplier`: `SELECT DISTINCT supplier FROM procedure WHERE supplier IS NOT NULL`.
- `author`: `SELECT DISTINCT sostavitel FROM parent_request`.
Реализуется эндпоинтом **`GET /reports`** (корень роутера, без path-сегмента — не конфликтует с `/{type}`) → `{mtr[],supplier[],author[]}`, под тем же гардом. FE грузит на маунте, кэширует (`staleTime` long), использует для наполнения `.rep-sel`.

---

## 10. Тестирование (TDD)

**Backend — `tests/test_calculations.py` (+):** на in-memory фикстурах с известными числами:
- `time`: процедура 5 дней (зависло), 1 день (нет); awaiting-родитель 4 дня (зависло); завершённая исключена; `Отменена` исключена; среднее; период по `zagruzka` отсекает.
- `sums`: Σ по 2 блокам + Итого; завершённая процедура в сумме; группировка по поставщику; KPI «В оплате» = await-УПД.
- `late`: overdue + late поставка; overdue УПД; manual-УПД при периоде исключён.
- `people`: группировка по sostavitel; dept fallback; Σ исключает `Отменена`.
- период `month/quarter/year/custom` → корректные `(from,to)`; фильтры mtr/supplier/author.

**Backend — `tests/test_reports.py` (новый):** HTTP через `TestClient`:
- 200 + корректный слепок на каждый `type`; поля/title/KPI-формы.
- 403 для сотрудника отдела (не куратор); 200 для Куратора/Руководителя/Админа.
- `export` каждого `format` → статус 200, верный `Content-Type`, непустое тело, `Content-Disposition` с именем.
- 404 (неизвестный `type`), 422 (`custom` без диапазона / `from>to`, неизвестный `format`).
- `GET /reports/filters` → списки distinct.

**Frontend — vitest:** `lib/reportsView.test.ts` для `cellClass(kind,level,color)` и `buildFilename`; монтажные/рендер-тесты страницы — по минимуму (страница презентационная).

---

## 11. Вне обзора (явно отложено)
- Сохранение/расписание/подписка на отчёты; e-mail-рассылка.
- Экспорт в 1С — `docs/34-extensions.md` (отложено).
- Drill-down: клик из строки отчёта в карточку (прототип не предусматривает) — не делаем.
- Числовые деньги в Excel (сейчас строки) — может быть добавлено позже без переделки.

---

## 12. Риски и подводные камни
- **Cyrillic в PDF** — обязательно зарегистрировать DejaVuSans (R10); иначе «квадратики». Тестировать, что тело PDF непустое и содержит кириллицу (достаточно непустого + Content-Type; декодing PDF в тесте избыточен).
- **CSV + Excel** — UTF-8 BOM обязателен для кириллицы при открытии в Excel; разделитель `;`.
- **`block_entered_at` может быть NULL** у старых процедур (до Фазы 5) — в `time` такие исключать (нет даты входа); учитывать в тесте.
- **Manual-УПД без процедуры** — не имеют родителя/`zagruzka` → R6.
- **`dept` у родителя** может быть NULL — fallback по `created_by` (R7).
- **Производительность** — объёмы ≤20 польз., небольшое число процедур; пагинация отчётов не нужна (это выгрузки). Если строк > некоторого предела — ограничить в §реализации не требуется.
