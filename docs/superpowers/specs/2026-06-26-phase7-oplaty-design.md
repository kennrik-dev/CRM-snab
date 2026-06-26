# Фаза 7 «Оплаты» — дизайн

- **Дата:** 2026-06-26
- **Статус:** одобрен пользователем 2026-06-26; ожидает плана (backend 7.1) и реализации.
- **Базовый коммит:** `main` @ `5eee83c` (Фазы 0–6 слиты).
- **Канон:** `docs/13-page-oplaty.md`, `docs/17-card-platezh.md`, `docs/31-api.md` §5, `docs/32-calculations.md` §7, `docs/02-statuses.md` §5, `docs/03-roles-permissions.md` §4, `docs/30-db-schema.md` (upd_payment/upd_position). Мастер-план: `docs/superpowers/plans/2026-06-21-crm-ultima-implementation.md` §«Фаза 7».
- **Визуальный канон:** `Concept design/index.html` (view-pay, view-paycard), `Concept design/zakupki-crm.js` (`rPay`/`payFin`/`rPayCard`).

---

## 1. Контекст и что уже есть

Фаза 7 = «единое окно оплат»: **параллельный реестр всех УПД** (из поставок + добавленные вручную), сводка (4 показателя + полоса распределения), проведение оплаты (только полной), карточка платежа.

**Уже реализовано в Фазе 6 (не трогаем):**
- Таблицы `upd_payment` + `upd_position` (`backend/app/models.py:267-322`) — полностью сформированы: `pay_status` CHECK `('await','paid')` DEFAULT `'await'`; `origin` CHECK `('delivery','manual','external')`; `delivery_id` FK→`delivery.id` (nullable, без CASCADE — удаление поставки блокируется, если есть УПД); `upd/request_label/supplier/contract/zrds/srok(TXT ISO)/amount(INT коп.)/pay_date(TXT ISO)/ext_source/ext_id/created_at`. `upd_position` (`n/name/unit/qty/price`, CASCADE).
- `POST /deliveries/{id}/upd` (`routers/support.py`) — upsert: создаёт `upd_payment` `origin='delivery'`, `pay_status='await'`, заполняет `supplier/contract` из процедуры, `amount=procedure_sum` позиций поставки. **Путь создания УПД из поставки готов.**
- `calc.is_upd_overdue(upd, today)` (`calculations.py`) — `await` AND `srok<today`. Готов, но никем не вызывается.
- Блок разрешений `oplaty` есть в `ALL_BLOCKS`/`WORK_BLOCKS`, но **ни один эндпоинт его не использует**.
- Фронт: роут `/oplaty` = `PlaceholderPage` (`App.tsx:40`); таб «Оплаты» в `Tabs.tsx` (`showCounter:true`, счётчик заглушён `'—'`). CSS платежей **уже целиком определён** в `frontend/src/styles/zakupki-crm.css:233-264` (`.payhero/.pcard/.pbar/.utbl/.pchip/.pcd*`), но не используется в TSX.

**Отсутствует (объём Фазы 7):** `routers/payments.py`, `schemas/payments.py`, `calculations.payments_summary()`, `test_payments.py`, регистрация роутера; FE `pages/Oplaty.tsx`, `cards/PaymentCard.tsx`, `api/payments.ts`, `payStatusChip`, роут `/oplaty/:id`, счётчик таба.

---

## 2. Зафиксированные решения (brainstorming)

| # | Решение | Обоснование |
|---|---|---|
| R1 | **RBAC мутаций `/payments` = `require_action('soprovozhdenie','edit')`** (любой сотрудник Сопровождения создаёт/редактирует/оплачивает). Блок `oplaty` остаётся зарезервированным (не используется эндпоинтами, как сегодня). | Пользователь выбрал вариант «Любой сотрудник Сопровождения» — соответствует страничным спекам 13/17 и существующему `POST /deliveries/{id}/upd`. |
| R2 | **FE-гейт действий = `canEdit(perms,'soprovozhdenie')`** (НЕ `oplaty`). | Сотрудник Сопровождения **не** владеет блоком `oplaty` (только куратор) → `canEdit(perms,'oplaty')` скрыл бы ему кнопки, хотя BE разрешает. |
| R3 | **Объём = только ядро.** № УПД в глобальном поиске → Фаза 10; кнопка «Экспорт» → Фаза 9. | Мастер-план дублирует эти пункты в P9/P10; ядро — чёткая граница фазы без дублирования инфраструктуры. |
| R4 | **Две сессии:** BE 7.1 (эта сессия, ⏸ после pytest+curl) → FE 7.2 (след. сессия). | Как Фаза 6 (BE-план + FE-план); экономия контекста; BE независимо тестируется. |
| R5 | Повторный `pay` оплаченной УПД → **409 Conflict**. | `31-api.md` резервировал 409 под «конфликт/дубль». |
| R6 | Audit платежей: `entity_kind='upd_payment'`, actions `payment_create/payment_patch/payment_pay`. Создание УПД из поставки остаётся `'procedure'` (как сейчас). | Чтобы «История» карточки платежа собиралась по самой УПД; не ломать существующий аудит доставки. |
| R7 | Ручная УПД **без FK к процедуре** (`request_label` — свободный текст). | Отложено в `docs/13 §9`, `docs/40 §4`. Без миграции. |
| R8 | Колонки реестра «Заявка»/«Поставка» — **на лету через JOIN** (без денормализации/миграции). | Данные всегда свежие; `request_label` для delivery-УПД и так NULL. |
| R9 | Документы (ТТН/М-15/УПД/Серт) на карточке платежа — **только чтение** (для delivery-УПД из связанной поставки); правка доков остаётся на `PATCH /deliveries`. | Флаги `doc_*` живут на `Delivery`, не на `UpdPayment`; иначе дублирование логики. *(Отклонение от буквального «doc_* в PATCH /payments» мастер-плана.)* |
| R10 | Сводка — **отдельный `GET /payments/summary`**. | Независима от пагинации/фильтров списка; FE зовёт однократно. |
| R11 | Счётчик таба «Оплаты» = **кол-во неоплаченных УПД** (`pay_status='await'`). | «К оплате» как индикатор работы; аналог счётчиков других табов. |
| R12 | Полоса распределения — **полные 4 сегмента по `32 §7`**. | Требование мастер-плана 7.1 (тесты долей); самый сложный кусок BE. |

---

## 3. Бэкенд (Задача 7.1 — эта сессия)

### 3.1. Роутер `backend/app/routers/payments.py`

`router = APIRouter(tags=['payments'])`, **без prefix** (инлайн-пути `/payments*`), зеркально `support.py`. Регистрируется в `main.py` (`from app.routers import …, payments` + `app.include_router(payments.router)`).

Паттерн эндпоинтов (как `requests.py`/`support.py`): чтение — `Depends(require_password_changed)`; мутации — `require_action('soprovozhdenie','edit')`; мутации пишут `write_audit(...)`; списки — `paginate(q, page, page_size=50)`; поиск по кириллице — `func.py_casefold(...)` + `func.instr(...)`.

### 3.2. Эндпоинты

| Метод | Путь | RBAC | Поведение |
|---|---|---|---|
| GET | `/payments` | read (все) | Реестр **всех** УПД. Query: `search?`, `hide_paid:bool=False`, `sort:str`, `page:int=1`, `page_size:int=50`. **Исключает УПД отменённых процедур** (manual-УПД без процедуры — включаются). Ответ: `Paginated[PaymentListItem]`. |
| GET | `/payments/summary` | read | Сводка `{meters, bar}`. **Определять РАНЬШЕ** `/payments/{id}`, чтобы не ловить `summary` как path-param (id — int, но порядок безопаснее). |
| POST | `/payments` | `soprovozhdenie edit` | Ручная УПД: `origin='manual'`, `pay_status='await'`, поля из `PaymentCreate`. `amount`: из payload, иначе `Σ position_sum(positions)` если позиции даны. Создаёт `upd_position` при наличии. 201 + `PaymentDetail`. Audit `payment_create`. |
| GET | `/payments/{id}` | read | `PaymentDetail` (все поля + `positions` + связанная поставка для `origin=delivery`). 404 если нет. |
| PATCH | `/payments/{id}` | `soprovozhdenie edit` | `PaymentPatch` → `srok/zrds/contract/supplier/amount/positions`. Audit `payment_patch`. |
| POST | `/payments/{id}/pay` | `soprovozhdenie edit` | `pay_status='await'→'paid'`, `pay_date=сегодня(ISO)`. Если уже `paid` → **409**. 404 если нет. Audit `payment_pay`. Ответ: `PaymentDetail`. |

**Сборка строки реестра (`PaymentListItem.request_display` / `delivery_n`):**
Базовый запрос с LEFT JOIN: `upd_payment` ← `delivery` (по `delivery_id`) ← `procedure` (по `delivery.procedure_id`) ← `parent_request` (по `procedure.parent_request_id`). В Python:
- `request_display`: `manual` → `upd.request_label`; `delivery` → `parent_request.code` (+ № процедуры — поле уточняется по `models.py` при реализации).
- `delivery_n`: `delivery.n` для `origin=delivery`, иначе `None`.
- `is_overdue`: `calc.is_upd_overdue(row, today)`.

**Исключение отменённых:** в `WHERE` — УПД исключается, если её `procedure` (через delivery) имеет статус «Отменена» (или архив). Manual-УПД (без procedure) не исключаются.

**Поиск (`search`):** OR (py_casefold+instr) по полям `upd, request_label, parent_request.code, supplier, contract, zrds`. `parent_request.code` доступен через базовый LEFT JOIN → покрывает поиск по Т-67 для delivery-УПД (у которых `request_label` пуст).

**Семантика `positions` (POST и PATCH):** если `positions` передан — **полная замена** строк `upd_position` (delete существующих + insert новых); `None`/отсутствие поля — позиции не трогаются. В POST при отсутствии `amount` он вычисляется как `Σ position_sum(positions)`.

### 3.3. `calculations.payments_summary(db, today)` (`backend/app/calculations.py`)

Авторитет — `docs/32-calculations.md §7` (буквально). Концептуально:

**Метры (Σ в копейках, исключая УПД отменённых процедур):**
- `paid` = Σ `amount` где `pay_status='paid'`.
- `await_` = Σ `amount` где `pay_status='await'`.
- `overdue` = Σ `amount` где `pay_status='await'` AND `is_upd_overdue` (`srok<today`).
- `in_work` = `paid + await_`.

**Полоса (доли от законтрактованной суммы):**
- `paid` = `meters.paid`.
- `await_` = `meters.await_`.
- `delivered_no_upd` = Σ сумм **доставленных позиций, не покрытых УПД** (доставка без `upd_payment`).
- `contracted_no_delivery` = Σ сумм **позиций недоставленных процедур** (процедуры без поставок).

> Точная агрегация `delivered_no_upd` / `contracted_no_delivery` (через `delivery_position`/`procedure_position`/`upd_payment`) фиксируется в **плане** по буквальному тексту `32 §7` и проверяется **фикстурными тестами** с вручную посчитанными ожиданиями.

Возвращает `{meters:{paid,await_,overdue,in_work}, bar:{paid,await_,delivered_no_upd,contracted_no_delivery}}`. Все суммы — int коп.; `None`-amount трактуется как 0.

### 3.4. Схемы `backend/app/schemas/payments.py`

`ConfigDict(from_attributes=True)`; деньги — `int` (коп.), даты — `Optional[str]` (ISO).

- `UpdPositionBase { n:Optional[int]; name:Optional[str]; unit:Optional[str]; qty:Optional[float]; price:Optional[int] }`; `UpdPositionIn(UpdPositionBase)`; `UpdPositionOut(UpdPositionBase)`.
- `PaymentCreate { upd:str(min_length=1); request_label:Optional[str]=None; supplier:Optional[str]=None; srok:Optional[str]=None; amount:Optional[int]=None; zrds:Optional[str]=None; positions:Optional[List[UpdPositionIn]]=None }`.
- `PaymentPatch { srok:Optional[str]=None; zrds:Optional[str]=None; contract:Optional[str]=None; supplier:Optional[str]=None; amount:Optional[int]=None; positions:Optional[List[UpdPositionIn]]=None }` (все Optional — частичный patch).
- `PaymentListItem { id:int; upd:str; origin:str; request_display:Optional[str]; supplier,contract,zrds:Optional[str]; delivery_n:Optional[int]; pay_status:str; is_overdue:bool; srok,pay_date:Optional[str]; amount:Optional[int]; created_at:str }`.
- `PaymentDetail` = все поля `upd_payment` + `positions:List[UpdPositionOut]` + `delivery:Optional[{n:int; procedure_id:int; parent_code:Optional[str]}]=None` + `is_overdue:bool`.
- `PaymentsSummary { meters:{paid,await_,overdue,in_work:int}; bar:{paid,await_,delivered_no_upd,contracted_no_delivery:int} }`.

### 3.5. RBAC / audit / ошибки

- Мутации: `require_action('soprovozhdenie','edit')` (R1). Другой отдел → 403.
- Чтение: `require_password_changed` (все аутентифицированные — «единое окно»).
- Audit: `write_audit(db, entity_kind='upd_payment', entity_id=payment.id, user=current_user, action=<…>)` (R6).
- Ошибки: не найдено → 404; повторная оплата → 409 (R5); невалидный payload → 422.

---

## 4. Фронтенд (Задача 7.2 — следующая сессия, дизайн-уровень)

- **`api/payments.ts`** (новый, зеркало `api/support.ts`): `listPayments/getPayment/createPayment/patchPayment/payPayment/getPaymentsSummary` + типы (`PaymentListItem/PaginatedPayments/PaymentDetail/PaymentCreate/PaymentPatch/PaymentsSummary`). `buildQuery` — переиспользовать из support.
- **`lib/statusColors.ts`** + `payStatusChip(status, isOverdue)` → `{kind, label}`: `await`/не-overdue → `{proc,'Ожидает оплаты'}`; `await`/overdue → `{late,'Просрочена'}`; `paid` → `{ok,'Оплачено'}`.
- **`pages/Oplaty.tsx`** (новый, копия структуры `Soprovozhdenie.tsx`):
  - Сверху `.payhero` (4 `.pcard`: «Сумма в работе»/«Оплачено»/«К оплате»/«Просрочено»; `style={{'--c': 'var(--ok|proc|late|pay)'}}`) + `.pbar` (4 сегмента `.sp-paid/.sp-out/.sp-del/.sp-con` с `%`-подписями) — данные из `getPaymentsSummary`.
  - `FilterBar`: поиск + `<select>` сортировки + чекбокс «скрыть оплаченные» (`hide_paid`).
  - `DataTable` (колонки: УПД(`.updn`) · Заявка · Поставщик · Договор(прочерк) · ЗРДС(прочерк) · Поставка(№/прочерк) · Статус(`PayChip`/`Chip` через `payStatusChip`) · Срок(`dateRu`) · Сумма(`money`)); `className="fit"`; row-click → `/oplaty/:id`.
  - Кнопка «+ Добавить УПД» → `Modal` с формой `PaymentCreate` (№ УПД, Заявка, Поставщик, Срок, Сумма, ЗРДС, позиции-опц.). Гейт `canEdit(perms,'soprovozhdenie')` (R2).
  - Query-ключи: `['payments',{search,hide_paid,sort,page}]` для списка; `['payments','summary']` для сводки; `['payments',{tabCounter:true}]` для счётчика (отдельный, чтобы инвалидация списка не била счётчик).
- **`cards/PaymentCard.tsx`** (новый, копия `SupportCard.tsx` — draft/diff-save/refresh-await-before-reset/savedTick/pending-флаги):
  - `.pcd-h` (№УПД + чип статуса + `.amt-big` суммы), `.pcd-meta` (Заявка/Поставщик/Договор/ЗРДС/Срок), связанная поставка (для `origin=delivery`), документы **только чтение** (R9), позиции (для `manual` — редактируемые через patch), кнопка «Провести оплату» (disabled если `paid`).
- **`App.tsx`**: `PlaceholderPage`→`<Oplaty/>`; добавить `<Route path="/oplaty/:id" element={<PaymentCard/>}/>`.
- **`Tabs.tsx`**: `OPLAT_COUNTER_KEY` + `useQuery(()=>listPayments({page_size:1}))` + ветка резолвера → кол-во `await` (R11).
- **CSS:** ничего не добавлять — все классы/токены есть; только `style={{'--c':…}}` на каждом `.pcard`.

---

## 5. Тестирование

**`backend/tests/test_payments.py`** (TDD red→green→commit):
- Реестр содержит и `delivery`-, и `manual`-УПД; `request_display`/`delivery_n` корректны для обоих origin.
- Ручное создание (POST) → `origin='manual'`, `pay_status='await'`, позиции создаются, `amount` из позиций при отсутствии в payload.
- `pay` → `paid` + `pay_date=сегодня`; повторный `pay` → **409**; 404 на несуществующий.
- `is_overdue` производный (await + srok<сегодня); paid не overdue.
- `payments_summary` — метры и 4 доли полосы по `32 §7` (фикстуры с ручным подсчётом).
- Исключение УПД отменённой процедуры из реестра и сводки.
- RBAC: сотрудник/куратор Сопровождения и Админ мутируют (200/201); сотрудник другого отдела → 403 на мутациях; чтение — всем.
- `write_audit` вызывается (entity_kind=`upd_payment`) на create/patch/pay.
- Поиск/сортировка/`hide_paid`/пагинация.

**vitest (FE):** `payStatusChip` (pure) — 3 ветви + overdue.

---

## 6. Граница фазы (что НЕ входит)

- № УПД в глобальном поиске (`/search`) → **Фаза 10**.
- Кнопка «Экспорт» реестра + Excel/PDF/CSV → **Фаза 9**.
- Привязка ручной УПД к процедуре (FK) → отложено (`docs/13 §9`).
- Частичная оплата → не модель (только полная).
- 1С-интеграция (`/integrations/1c/payments`, `ext_source/ext_id`) → `docs/34 §1`, отложено.
- Дашборд-показатели по УПД → Фаза 8.

---

## 7. ⏸ Стоп-проверка Фазы 7 (после BE 7.1)

- `cd backend && "$PY" -m pytest tests/test_payments.py -v` → PASS (без регрессий в остальном suite).
- Ручной smoke (curl): `GET /payments` (реестр), `POST /payments` (manual УПД), `POST /payments/{id}/pay` (→paid), `GET /payments/summary`.
- **Жду подтверждения перед frontend 7.2.**

🔎 **ui-checker** (после FE 7.2): сводка (`payhero`+`pbar` — доли и подписи), реестр (`pchip` статусы, прочерки для manual), форма «+ Добавить УПД», карточка платежа (документы только для УПД из поставки), «Провести оплату». Канон — `index.html` §payments.

---

## 8. Порядок исполнения

1. **writing-plans** → детальный план BE 7.1 (TDD, шаги, фикстуры сводки).
2. **BE 7.1** в этой сессии (subagent-driven `Workflow`, red→green→commit). ⏸ стоп выше.
3. **FE 7.2** — отдельный план + следующая сессия. ⏸ стоп перед Фазой 8.
