# Фаза 8 — Дашборд: дизайн (спека)

- **Дата:** 2026-06-27
- **Ветка:** `feat/phase-8` (от `main` @ `2822126`)
- **Статус:** черновик (на review пользователем)
- **Канон-источники:** `docs/14-page-dashboard.md`, `docs/32-calculations.md` §3/§5/§6/§9, `docs/superpowers/plans/2026-06-21-crm-ultima-implementation.md` §Фаза 8, `Concept design/index.html` (строки 34–45), `Concept design/zakupki-crm.js` (`rMeters/rFlow/rAlerts/rFeed/rDash`, `tblAwaitingC/tblProcC/tblSuppC`).

---

## 1. Цель / результат

Обзорный экран «Дашборд» — стартовый (`/` → `/dashboard`, сейчас `PlaceholderPage`). **Одинаков для всех ролей**, только просмотр и переходы. Четыре зоны сверху вниз:

1. Полоса из **6 показателей** (`.meters`).
2. **Поток по этапам** (`.flowrail`, 4 стадии).
3. Две панели (`.grid2`): **«Требует внимания»** + **«Лента событий»**.
4. **Компактные таблицы** по 3 этапам (Ожидают закупки / В закупке / В сопровождении).

«Реальное время» — опрос `/dashboard` каждые 60 c + refetch на фокус окна.

---

## 2. Проверенные предположения (не требуют вопроса)

- **Данные глобальные.** Ни один list-эндпоинт не фильтрует по `department`/`user` — RBAC здесь гейтит *действия* по блокам, а не видимость строк. Значит «одинаков для всех ролей» = идентичные глобальные агрегаты для каждого.
- **«Ожидают закупки»** = `ParentRequest` без `Tender` и `status='awaiting'` (см. `requests.py:list_requests`, фильтр `no_tender`).
- **Формулы 6 показателей** зафиксированы в `32 §6` (`Отменена` исключается; завершённые — вне операционных счётчиков, но в финансовых итогах).
- **Все хелперы уже есть** в `calculations.py`: `today_moscow`, `_parse_date`, `position_sum`, `procedure_sum`, `progress`, `is_delivery_overdue`, `is_delivery_late`, `is_procedure_overdue`, `overdue_pct`, `docs_aggregate`, `is_upd_overdue`, `payments_summary` (шаблон db-сводки).

---

## 3. Решения (R1–R10)

**R1 — Один эндпоинт, глобально, для всех ролей.** `GET /dashboard` отдаёт весь payload одним ответом (атомарный срез, один round-trip, один cache-key). Auth = `require_password_changed` (любой аутентифицированный); **без `require_action`** — дашборд доступен всем. Миграций и новых блоков прав — нет.

**R2 — Агрегация в `calculations.dashboard(db, today)`.** Новая функция-сводка по образцу `payments_summary(db, today)`: грузит строки в Python и считает чистыми хелперами. Роутер только вызывает её и формирует ответ. Хелперы переиспользуются, новых чистых функций добавляется минимально (`is_procedure_completed`, `proc_sum`, метры/флоу/attention — либо в `calculations.py`, либо локально в `dashboard.py`).

**R3 — 6 показателей** по `32 §6` с каноническим dot-bar `seg{on,total}`. Точные формулы — в §4.

**R4 — Поток = 4 стадии** по `docs/14 §4` (Ожидают закупки · В закупке · В сопровождении · Оплаты). У концепта есть 5-я «Закрыта» — **опускаем** как неканоническую (документы приоритетнее концепта).

**R5 — «Требует внимания» = 2 уровня** (выбор пользователя): 🔴 ошибки и 🟡 предупреждение. Точные триггеры — в §5. **Документы переопределяют текст концепта:** «УПД без сертификата» = предупреждение («оплату провести можно»), а не «нельзя передать в оплату».

**R6 — «Лента событий» = последние 20 `audit_log`** (новее → старее). Актёр = `user.full_name` (через JOIN по `user_id`, иначе «Система»); действие = русская человеко-читаемая метка (карта на бэке); сущность — полиморфный дисплей (`parent`/`parent_request` → `ParentRequest.code`, `procedure` → `Procedure.proc`, `upd_payment` → `UpdPayment.upd`; прочие `entity_kind` — без дисплея); `target{kind,id}` для клика; `created_at` (ISO). Относительное время (`rel_time`) считается **на фронте** чистой функцией из `created_at`.

**R7 — Компактные таблицы** по `docs/14 §7` (колонки = концепт `tblAwaitingC/tblProcC/tblSuppC`): «Поз.» = **по числу позиций** (count-based, решение support-polish). Каждая таблица — **top-10 свежих**, заголовок блока = **истинный total**, кнопка «Открыть раздел →» ведёт на полную страницу.

**R8 — Refresh через React Query.** Query `/dashboard` с `refetchInterval: 60000` и `refetchOnWindowFocus: true` (переопределяет дефолт приложения). Без веб-сокетов.

**R9 — Scope-границы (НЕ Фаза 8):** глобальный поиск (→ Ф10), экспорт (→ Ф9), отдельная страница «История» аудита (→ Ф10), 1С (→ `34 §1`). Лента событий — только read-only на дашборде.

**R10 — Производительность:** масштаб ≤20 пользователей и умеренный объём; Python-агрегация в один проход приемлема (как `payments_summary`). Без преждевременной оптимизации / денормализации.

---

## 4. Показатели (метры)

Каждый метр: `{key, label, value, unit?, sub, seg:{on,total}, color}`. `value` — число или строка; `sub` — короткий контекст (₽-сумма или «X / Y»); `color` — CSS-токен (`--proc/--supp/--ok/--late/--pay/--wait`).

**`seg` — канонический dot-bar (как в концепте): фиксированные `total=14` точек, `on = round(ratio * 14)` (0..14), где `ratio ∈ [0,1]` — семантическая доля метра.** Концепт у всех метров `t:14` (напр. «Поставки в срок» 87% → `on:12`). BE шлёт готовые `{on, total:14}`.

Общие производные:
- `active_procs` = процедуры `block IN ('zakupka','soprovozhdenie')` И не отменены (для закупки: `status_zakup≠'Отменена'`; для сопровождения: `status_postavki≠'Отменена'`) И (если сопровождение) не завершена. `active_total = len(active_procs)`.
- `is_completed(proc, upds)` = `status_postavki=='Поставлено'` И `len(upds)≥1` И `all(u.pay_status=='paid')` (Phase 6 R6).
- `proc_sum(proc, positions)` = `contract_sum` если не None, иначе Σ `position_sum`.

| key | label | value | sub | ratio (→ seg `on`) |
|---|---|---|---|---|
| `in_zakupka` | В закупке | `count(block='zakupka' ∧ status_zakup≠'Отменена')` | «процедур» | value / active_total |
| `in_support` | В сопровождении | `count(block='soprovozhdenie' ∧ not is_completed ∧ status_postavki≠'Отменена')` | `money(Σ contract_sum по ним)` | value / active_total |
| `on_time_pct` | Поставки в срок | `round(on_time / all_deliveries * 100)` (0 если `all=0`) + unit `%` | «{on_time} / {all_deliveries} поставок» | value / 100 |
| `overdue` | Просрочено | `count(block='soprovozhdenie' ∧ status_postavki≠'Отменена' ∧ is_procedure_overdue)` | `money(Σ proc_sum по ним)` | value / active_total |
| `upd_await` | УПД в оплате | `count(pay_status='await')` (искл. УПД отменённых процедур) | `money(Σ amount по ним)` | value / count(all active УПД: await+paid) |
| `upd_overdue` | УПД просрочено | `count(pay_status='await' ∧ is_upd_overdue)` | `money(Σ amount по ним)` | value / count(await УПД) |

(Если знаменатель ratio = 0 → `on = 0`.)

Уточнения:
- **«Поставки в срок»**: `on_time` = поставки `status='done'` И НЕ `is_delivery_late` (`done ∧ date ≤ srok_dd`); знаменатель = **все** поставки (`32 §9.2`). Поставка `done` без `srok_dd` считается «в срок».
- **УПД**: «активные» = УПД, чья процедура (через `delivery→procedure`) не отменена (`status_postavki is null OR ≠ 'Отменена'`); manual-УПД без процедуры учитываются. Фильтр тот же, что в `payments_summary`.
- `is_procedure_overdue` уже гарантирует `status_postavki≠'Поставлено'`; дополнительно исключаем `'Отменена'`.

---

## 5. Поток по этапам (4 стадии)

`flow[]`, каждый `{key, label, count, sub?, route, color}`. Клик → `route`.

| key | label | count | route | color |
|---|---|---|---|---|
| `awaiting` | Ожидают закупки | `count(ParentRequest: status='awaiting' ∧ no Tender)` | `/komplektaciya` | `--wait` |
| `procurement` | В закупке | = метр `in_zakupka` | `/zakupka` | `--proc` |
| `support` | В сопровождении | = метр `in_support` | `/soprovozhdenie` | `--supp` |
| `payments` | Оплаты | `count(await УПД, искл. отменённые)` = метр `upd_await` | `/oplaty` | `--pay` |

---

## 6. «Требует внимания» (2 уровня)

`attention[]`, каждый `{id_label, severity:'error'|'warning', text, target:{kind:'procedure'|'payment', id}}`. Сортировка: ошибки раньше предупреждений; внутри — по срочности (просрочка в днях ↓). **Рендерится top-20**, заголовок панели = истинный total (если >20 — «и ещё N»).

Триггеры:

🔴 **errors**
1. **Просроченная поставка** — для каждой `Procedure` (`block='soprovozhdenie'`, `status_postavki≠'Отменена'`) и каждой её поставки, где `is_delivery_overdue ∨ is_delivery_late`:
   - `id_label` = `{parent.code} · {procedure.proc}`; `text` = `Поставка №{delivery.n} ({supplier or '—'}) — просрочена на {days} дн.`; `days` = `today − srok_dd` (overdue) или `date − srok_dd` (late); `target={kind:'procedure', id}`.
2. **Просроченная оплата** — для каждого `UpdPayment` (`pay_status='await'`, `is_upd_overdue`, искл. отменённые):
   - `id_label` = `УПД {upd}`; `text` = `УПД {upd} просрочена к оплате +{days} дн. · {money(amount)}`; `days` = `today − srok`; `target={kind:'payment', id}`.
3. **Отсутствие документов** — для каждой `Procedure` (`block='soprovozhdenie'`, `status_postavki≠'Отменена'`, **есть ≥1 поставка**), где `docs_aggregate` даёт `False` хотя бы по одному из `{ttn, m15, upd}` (серt тут НЕ учитывается — он отдельный warning):
   - `id_label` = `{parent.code} · {procedure.proc}`; `text` = `Документы не получены: {нет ТТН/М-15/УПД — список отсутствующих}`; `target={kind:'procedure', id}`.
   - Гейт «≥1 поставка» нужен, чтобы не триггерить каждый новый акт сопровождения без поставок.

🟡 **warning**
4. **УПД без сертификата** — для каждого `UpdPayment` (`origin='delivery'`, `pay_status='await'`, искл. отменённые), чья `delivery.doc_sert=0`:
   - `id_label` = `УПД {upd}`; `text` = `УПД {upd} без сертификата — оплату можно провести`; `target={kind:'payment', id}`.

> Note: у одной процедуры могут сработать несколько триггеров (напр. просрочка поставки + отсутствие документов) — это разные проблемы, показываем раздельно.

---

## 7. «Лента событий»

`feed[]` — последние **20** записей `audit_log` (`order by created_at desc, id desc`). Каждая:
```
{ actor, action_label, entity_display?, target?:{kind,id}, created_at }
```
- `actor` = `User.full_name` (JOIN по `user_id`); если `user_id is null` → `"Система"`.
- `action_label` — карта action→русский глагол на бэке (`create→«создал(а)»`, `update→«обновил(а)»`, `cancel→«отменил(а)»`, `uncancel→«восстановил(а)»`, `take_to_work→«взял(а) в работу»`, `to_support→«передал(а) в сопровождение»`, `split→«разбил(а) по поставщикам»`, `pay→«провёл(а) оплату»`, `positions_add→«добавил(а) позиции»`, прочие → `action` как есть). + род существительного по `entity_kind` (`parent/parent_request→«заявку»`, `procedure→«процедуру»`, `upd_payment→«УПД»`, …).
- `entity_display` — полиморфный лукап по `entity_kind`: `parent`/`parent_request`→`ParentRequest.code`, `procedure`→`Procedure.proc`, `upd_payment`→`UpdPayment.upd`; для остальных (`position`, `delivery`, `comment`, `tender`) → `null`.
- `target` — для клика: `parent/parent_request→{kind:'parent',id}`, `procedure→{kind:'procedure',id}`, `upd_payment→{kind:'payment',id}`; иначе `null`.
- `rel_time` считается **на фронте** (`lib/dashView.ts`, чистая функция, TDD): «только что» / «N мин назад» / «N ч назад» / «вчера» / «N дн назад» / дата `DD.MM.YYYY`.

> Богатые детали концепта («1,29 млн», «на 3 поставщика») не восстановимы — `audit_log` их не снэпшотит. Это сознательный lean.

---

## 8. Компактные таблицы

`tables.{awaiting,procurement,support}` = `{total, items[]}`; `items` — top-10 свежих (по `created_at` ↓). Клик по строке → карточка; «Открыть раздел →» → полная страница.

**awaiting** (`ParentRequest`, `status='awaiting' ∧ no Tender`) → `/komplektaciya/:id`
| # | Наименование (`{code, title}`) | Тип МТР (`mtr`) | Срок (`srok`) | Поз. (`count(RequestedPosition)`) | Статус (chip «Ожидает») |

**procurement** (`Procedure`, `block='zakupka' ∧ status_zakup≠'Отменена'`) → `/zakupka/:id`
| # | Наименование (`{parent.code, parent.title}`) | № заявки (`procedure.proc`) | Поставщик (`supplier`) | Поз. (`count(ProcedurePosition)`) | Статус (`status_zakup` chip) |

**support** (`Procedure`, `block='soprovozhdenie' ∧ not is_completed ∧ status_postavki≠'Отменена'`) → `/soprovozhdenie/:id`
| # | Наименование (`{parent.code, parent.title}`) | № заявки (`procedure.proc`) | Поставщик (`supplier`) | Сумма договора (`proc_sum`, ₽) | Статус поставки (`status_postavki` chip) | Просроч. (`overdue_pct`, %) | Прогресс (`progress` → `delivered/total`) |

«Наименование» = тег `code` + `title` (как в концепте). Позиции — по числу позиций (count). `parent` получаем через `Procedure.tender → Tender.parent`.

---

## 9. Backend — файлы и контракт

**Create:**
- `backend/app/routers/dashboard.py` — `GET /dashboard` (prefix `/dashboard`), auth `require_password_changed`; вызывает `calculations.dashboard(db, today_moscow())` и формирует ответ; `write_audit` НЕ нужен (только чтение).
- `backend/app/schemas/dashboard.py` — Pydantic v2 response-модели (`DashboardOut` и вложенные).
- `backend/tests/test_dashboard.py` — фикстура с известными числами; см. §11.

**Modify:**
- `backend/app/calculations.py` — добавить `dashboard(db, today)` и при необходимости `is_procedure_completed`, `proc_sum` (чистые). Регистр в `__all__`.
- `backend/app/main.py` — подключить роутер `dashboard`.

Payload (канонический): `DashboardOut = {meters:list[Meter], flow:list[FlowStage], attention:list[AttentionItem], feed:list[FeedItem], tables:DashboardTables}`.

---

## 10. Frontend — файлы и структура

**Create:**
- `frontend/src/api/dashboard.ts` — `getDashboard()` (типы `DashboardData`, `Meter`, `FlowStage`, …; зеркало `api/payments.ts`).
- `frontend/src/lib/dashView.ts` — чистые хелперы (TDD): `relTime(iso)`, цвет/класс метра по `key`, человеко-метка если нужно.
- `frontend/src/pages/Dashboard.tsx` — `useQuery(['dashboard'], getDashboard, {refetchInterval:60000, refetchOnWindowFocus:true})`; скелетон при загрузке, `EmptyState`/ошибка.
- Под-компоненты: `Meters`, `FlowRail`, `AttentionPanel`, `FeedPanel`, `CompactTables` (в `pages/dashboard/` или рядом).

**Modify:**
- `frontend/src/App.tsx` — заменить `PlaceholderPage` на `<Dashboard />` на `/dashboard`.

Разметка — из `index.html` (34–45) + концепт-функции: `.meters`/`.meter`/`.seg`, `.flowrail`/`.fstage`, `.grid2`/`.panel`/`.phead`, `.alert` (`--al`), `.fitem`, блоки `.block` (через `blockWrap`-аналог) с «Открыть раздел →». Чипы/цвета — `lib/statusColors.ts`, `money`/`dateRu` — `lib/format`. Клик стадии/строки → `useNavigate`. RBAC-гейтинг действий **отсутствует** (только просмотр); поэтому `useAuth()` нужен только если понадобится (напр. текст «Система»/аватар) — по минимуму.

---

## 11. Тесты

**Backend (`test_dashboard.py`):** фикстура с известным набором (несколько процедур в закупке/сопровождении, поставки done/transit/late, УПД await/paid/overdue, отменённая процедура, завершённая процедура, parent awaiting/cancelled, audit-записи). Проверки:
- Каждый из 6 метров даёт ожидаемое число на фикстуре.
- `Отменена` исключена из счётчиков; завершённая процедура — вне операционных счётчиков, но её УПД — в финансовых.
- «Поставки в срок» % = on_time/all; знаменатель = все поставки.
- «Требует внимания»: каждый триггер даёт ожидаемый item, в т.ч. УПД-без-серта = `warning`; процедуры без поставок не дают «отсутствие документов»; `severity` и `target` корректны.
- `flow`: 4 стадии, counts совпадают с метрами; «Оплаты» = await-УПД.
- `feed`: последние N, новее первым, `actor`/`action_label`/`entity_display` корректны.
- `tables`: top-N, total истинный, колонки/row-targets корректны; «Поз.» count-based.
- Auth: без логина → 401; `must_change_password=1` → 403; любая роль (сотрудник отдела) получает данные.

**Frontend:** `dashView.test.ts` — `relTime` (граничные случаи: сейчас/минуты/часы/вчера/дни/дата), цвет/класс метра. Компонентные тесты — по минимуму (vitest, node-env, без jsdom): рендер счётчиков/флоу из мока данных; навигация по клику (mock `useNavigate`).

---

## 12. Приёмка (⏸ СТОП перед Фазой 9)

- `cd backend && "$PY" -m pytest tests/test_dashboard.py -v` → PASS (и весь бэкенд без регрессий).
- `cd frontend && npm test && npm run lint && npm run build` → зелёно, tsc 0.
- 🔎 **ui-checker**: дашборд — главный экран канона. Сетка 6 метров (≤1080px → 3 колонки, ≤720px → 2), `flowrail` со стрелками-разделителями, две панели, 3 компактные таблицы в `.block`. Сверка плотности/токенов с `index.html`. Переходы (стадия → страница, строка → карточка, «Открыть раздел»). Консоль/сеть чистые. `browser_resize` 1280/1440. Дашборд одинаков под всеми ролями.
- Человек: ручной пересчёт 6 метров по `32 §6` на небольшом наборе; «Требует внимания» содержит ожидаемые триггеры; лента событий осмыслена; переходы работают.
