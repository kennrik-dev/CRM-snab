# 30 · Схема БД (SQLite)

Финальная схема, собранная из `01-domain-model.md`, `02-statuses.md`, `04-auth.md` и полей со страниц. Производные величины (просрочка, прогресс, агрегаты) **не хранятся** — расчёт в `32-calculations.md`.

## Соглашения

- `id INTEGER PRIMARY KEY` (rowid).
- **Даты** — `TEXT` в формате ISO (`YYYY-MM-DD`), метки времени — `YYYY-MM-DD HH:MM:SS`.
- **Деньги** — `INTEGER` в **копейках** (во избежание ошибок округления). Все суммы с НДС.
- **Булевы** — `INTEGER` 0/1.
- FK включить: `PRAGMA foreign_keys = ON;`

---

## Таблицы

```sql
-- Пользователи (04-auth)
CREATE TABLE user (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL,
  account_type TEXT NOT NULL CHECK(account_type IN ('department','global')),
  department TEXT CHECK(department IN ('Комплектация','Закупки','Сопровождение')),
  is_curator INTEGER NOT NULL DEFAULT 0,
  global_role TEXT CHECK(global_role IN ('Админ','Руководитель')),
  is_active INTEGER NOT NULL DEFAULT 1,
  must_change_password INTEGER NOT NULL DEFAULT 0,  -- 1 = требовать смену пароля при следующем входе (04-auth)
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_by INTEGER REFERENCES user(id)
);

-- Заявка-родитель (Т-67)
CREATE TABLE parent_request (
  id INTEGER PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,                 -- Т-67 (вручную)
  title TEXT NOT NULL,
  mtr TEXT,
  srok TEXT,                                 -- желаемый срок поставки
  zagruzka TEXT NOT NULL DEFAULT (date('now')),
  sostavitel TEXT NOT NULL,                  -- ФИО (снимок) = создатель
  created_by INTEGER REFERENCES user(id),
  dept TEXT,
  status TEXT NOT NULL DEFAULT 'awaiting' CHECK(status IN ('awaiting','cancelled')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Запрошенная позиция (уровень родителя)
CREATE TABLE requested_position (
  id INTEGER PRIMARY KEY,
  parent_id INTEGER NOT NULL REFERENCES parent_request(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  qty REAL NOT NULL,
  unit TEXT,
  gost_tu TEXT,
  doc_code TEXT
);

-- Торг (№ заявки, №1488)
CREATE TABLE tender (
  id INTEGER PRIMARY KEY,
  num TEXT UNIQUE,                           -- может быть пустым до заведения
  parent_id INTEGER NOT NULL REFERENCES parent_request(id)
);

-- Процедура (№ процедуры, АП…)
CREATE TABLE procedure (
  id INTEGER PRIMARY KEY,
  proc TEXT UNIQUE,                          -- может быть пустым до заведения
  tender_id INTEGER NOT NULL REFERENCES tender(id),
  supplier TEXT,
  fio_zakupshchik TEXT,
  fio_dogovornik TEXT,
  mtr TEXT,                                  -- переопределение; иначе наследует от родителя
  pub_start TEXT, pub_end TEXT,
  contract TEXT,
  contract_sum INTEGER,                      -- копейки (авто Σ позиций, правится вручную)
  block TEXT NOT NULL DEFAULT 'zakupka' CHECK(block IN ('zakupka','soprovozhdenie')),
  block_entered_at TEXT,                     -- служебное: дата входа в текущий блок (для «времени на этапе»); пользователям не показывается
  status_zakup TEXT,                         -- справочник (dict)
  status_postavki TEXT CHECK(status_postavki IN
     ('Новая','В производстве','В поставке','Частично поставлено','Поставлено','Отменена')),
  status_sdelki TEXT,                        -- справочник (dict)
  srok_dd TEXT,
  plan_date TEXT,
  fakt_date TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Поставка
CREATE TABLE delivery (
  id INTEGER PRIMARY KEY,
  procedure_id INTEGER NOT NULL REFERENCES procedure(id) ON DELETE CASCADE,
  n INTEGER NOT NULL,                        -- № поставки внутри процедуры
  status TEXT NOT NULL DEFAULT 'transit' CHECK(status IN ('transit','done')),
  date TEXT,                                 -- факт получения
  eta TEXT,
  doc_ttn INTEGER DEFAULT 0,
  doc_m15 INTEGER DEFAULT 0,
  doc_upd INTEGER DEFAULT 0,
  doc_sert INTEGER DEFAULT 0
);

-- Позиция процедуры
CREATE TABLE procedure_position (
  id INTEGER PRIMARY KEY,
  procedure_id INTEGER NOT NULL REFERENCES procedure(id) ON DELETE CASCADE,
  source_id INTEGER REFERENCES requested_position(id),   -- NULL = добавлена закупщиком
  name TEXT NOT NULL,
  qty REAL NOT NULL,
  unit TEXT,
  gost_tu TEXT,
  doc_code TEXT,
  price INTEGER,                             -- копейки, с НДС
  delivery_id INTEGER REFERENCES delivery(id)            -- NULL = ожидает отгрузки
);

-- УПД / платёж
CREATE TABLE upd_payment (
  id INTEGER PRIMARY KEY,
  upd TEXT NOT NULL,
  origin TEXT NOT NULL CHECK(origin IN ('delivery','manual','external')),  -- 'external' — резерв под интеграцию (34)
  delivery_id INTEGER REFERENCES delivery(id),           -- для origin='delivery'
  ext_source TEXT,                           -- источник внешней системы (напр. '1c'); резерв, см. 34-extensions
  ext_id TEXT,                               -- идентификатор документа во внешней системе; резерв, см. 34-extensions
  request_label TEXT,                        -- «Т-67 + №…» (текст)
  supplier TEXT,
  contract TEXT,
  zrds TEXT,
  srok TEXT,                                 -- срок оплаты (ручной)
  amount INTEGER,                            -- копейки, с НДС
  pay_status TEXT NOT NULL DEFAULT 'await' CHECK(pay_status IN ('await','paid')),
  pay_date TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Позиции в составе УПД (для ручной УПД, опционально)
CREATE TABLE upd_position (
  id INTEGER PRIMARY KEY,
  upd_payment_id INTEGER NOT NULL REFERENCES upd_payment(id) ON DELETE CASCADE,
  n INTEGER,
  name TEXT,
  unit TEXT,
  qty REAL,
  price INTEGER
);

-- Комментарии (к родителю/торгу/процедуре)
CREATE TABLE comment (
  id INTEGER PRIMARY KEY,
  target_kind TEXT NOT NULL CHECK(target_kind IN ('parent','tender','procedure')),
  target_id INTEGER NOT NULL,
  author_id INTEGER REFERENCES user(id),
  author TEXT,                               -- ФИО (снимок)
  role TEXT,                                 -- отдел/роль (снимок)
  text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- История / аудит («История» в карточках)
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  entity_kind TEXT NOT NULL,                 -- parent | procedure | delivery | upd_payment
  entity_id INTEGER NOT NULL,
  user_id INTEGER REFERENCES user(id),
  action TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Справочники, расширяемые Админом (статусы закупки/сделки)
CREATE TABLE dict (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('status_zakup','status_sdelki')),
  value TEXT NOT NULL,
  sort_order INTEGER DEFAULT 0,
  UNIQUE(kind, value)
);
```

---

## Начальные данные (seed при первом запуске)

```sql
-- Предзаполненный Админ: дефолтный пароль, обязательная смена при первом входе
INSERT INTO user (email, password_hash, full_name, account_type, global_role, is_active, must_change_password)
VALUES ('admin@crm.local', '<хэш дефолтного пароля>', 'Администратор', 'global', 'Админ', 1, 1);

-- Справочники статусов. 'Новая' и 'Отменена' — служебные, в dict НЕ входят (см. примечание).
INSERT INTO dict (kind, value, sort_order) VALUES
  ('status_zakup','Приём заявок',1),
  ('status_zakup','Торги',2),
  ('status_zakup','Тех. экспертиза',3),
  ('status_zakup','Дозапросы',4),
  ('status_zakup','Согласование',5),
  ('status_zakup','На сделку',6),
  ('status_sdelki','Согласование',1),
  ('status_sdelki','Подготовка ДД',2),
  ('status_sdelki','Подписано',3);
```

> **`status_zakup`:** значения `Новая` (начальный, ставит система при входе в блок) и `Отменена` (ставит действие «Отменить процедуру») — валидные хранимые значения, но **не входят в `dict`** и не выбираются вручную. В справочнике — только рабочие статусы `Приём заявок … На сделку`.

---

## Индексы

```sql
CREATE INDEX ix_reqpos_parent     ON requested_position(parent_id);
CREATE INDEX ix_tender_parent     ON tender(parent_id);
CREATE INDEX ix_proc_tender       ON procedure(tender_id);
CREATE INDEX ix_proc_block        ON procedure(block);
CREATE INDEX ix_proc_supplier     ON procedure(supplier);
CREATE INDEX ix_procpos_proc      ON procedure_position(procedure_id);
CREATE INDEX ix_procpos_delivery  ON procedure_position(delivery_id);
CREATE INDEX ix_procpos_source    ON procedure_position(source_id);
CREATE INDEX ix_delivery_proc     ON delivery(procedure_id);
CREATE INDEX ix_upd_delivery      ON upd_payment(delivery_id);
CREATE INDEX ix_upd_paystatus     ON upd_payment(pay_status);
CREATE INDEX ix_updpos_upd        ON upd_position(upd_payment_id);
CREATE INDEX ix_comment_target    ON comment(target_kind, target_id);
CREATE INDEX ix_audit_entity      ON audit_log(entity_kind, entity_id);
CREATE INDEX ix_parent_status     ON parent_request(status);
```

---

## Производное (НЕ хранится, считается — `32-calculations.md`)

- Сумма позиции = `qty * price`; сумма процедуры/УПД = Σ позиций (можно `GENERATED`-колонкой или на лету).
- **Просрочка** (поставки/процедуры/оплаты) — по сроку и факту.
- **Прогресс** «поставлено X из Y», **% просрочки**, **агрегат документов** (есть во всех поставках).
- Показатели дашборда и отчётов.

---

## Инварианты (контроль на стороне приложения)

- Торг всегда содержит **≥1 процедуру** (одна по умолчанию).
- Поставка **не пустая** (≥1 позиция; `procedure_position.delivery_id` указывает на неё).
- Дробление: Σ `qty` позиций процедур по одной `source_id` ≤ `qty` запрошенной.
- `procedure.status_zakup` / `status_sdelki` валидируются по `dict` (плюс служебные `Новая` / `Отменена` для `status_zakup` — вне справочника).

---

## Решения и открытые вопросы

1. ✅ **Деньги** — `INTEGER` (копейки).
2. ✅ **Справочники** `status_zakup` / `status_sdelki` — через таблицу `dict` (Админ пополняет список); `status_postavki` — фиксированный `CHECK`.
3. **Состав аудита** (`audit_log`) — какие события писать — детализируем в `33-nonfunctional.md`.
4. **МТР / Поставщик / Ед. изм.** — свободный текст (не справочники).
5. ✅ **Точки расширения** (`34-extensions.md`) — заложены: в `upd_payment` зарезервированы `origin='external'`, `ext_source`, `ext_id` (под интеграцию с 1С). Таблица вложений и поля уведомлений добавляются позже без переделки текущих таблиц.
