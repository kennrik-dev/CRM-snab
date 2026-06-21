# CRM Ultima — План реализации

> **Для агентов-исполнителей:** ОБЯЗАТЕЛЬНЫЙ СУБ-СКИЛЛ: используйте `superpowers:subagent-driven-development` (рекомендуется) или `superpowers:executing-plans` для пошаговой реализации. Шаги размечены чекбоксами (`- [ ]`).
>
> **Как читать этот план.** Проект большой (полноценная full-stack CRM), поэтому он разбит на **11 фаз (0–10)**. Каждая фаза — самостоятельный, тестируемый рубеж: после неё система собирается и запускается. В рамках фазы задачи следуют циклу TDD: *написать падающий тест → убедиться, что падает → минимальная реализация → тесты зелёные → коммит*. Для фундаментальных фаз (0–2) шаги расписаны мелко; для фаз с повторяющимся CRUD приведён полный образец паттерна + **точные списки полей/эндпоинтов из `docs/31-api.md`** (это и есть спецификация — не «аналогично задаче N»).
>
> **Протокол остановок.** В конце КАЖДОЙ фазы — блок **⏸ СТОП — ПРОВЕРКА**: точные команды, ожидаемый вывод и что проверяет человек. Исполнитель **останавливается** и ждёт подтверждения пользователя, прежде чем начать следующую фазу.
>
> **UI-проверка.** На фазах с фронтендом — блок **🔎 ui-checker**: диспетчеризация QA-агента `ui-checker` (Playwright MCP) для сверки с визуальным каноном.

**Goal:** Реализовать CRM Ultima — единое окно отслеживания закупочных заявок (Комплектация → Закупки → Сопровождение → Оплаты) для команды ≤20 человек, точно по документации в `docs/`.

**Architecture:** Монолит из двух приложений в одном репозитории. Бэкенд — FastAPI + SQLAlchemy 2.0 + SQLite, сессии в httpOnly-cookie, RBAC на уровне отделов/ролей, производные величины считаются на лету. Фронтенд — Vite + React + TypeScript (SPA, React Router), стили — порт готовой дизайн-системы из `Concept design/zakupki-crm.css`, данные через типизированный API-клиент (`fetch`, `credentials: include`) + TanStack Query. Визуальный канон — концепт-прототип; модель данных — `docs/` (трёхуровневая, блочные статусы).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, passlib[bcrypt], pytest + httpx; Node 20, Vite, React 18, TypeScript, React Router 6, @tanstack/react-query, openpyxl (экспорт Excel на бэке), reportlab (PDF). Playwright (через MCP) — для ui-checker.

---

## Global Constraints

Эти требования действуют во **всех** задачах (копируются из `docs/` дословно).

- **Язык интерфейса** — русский (`ru-RU`). Документация и UI-тексты — на русском.
- **Деньги** — хранение `INTEGER` в **копейках**; отображение `1 234 567 ₽` (пробел — разделитель тысяч). Все суммы — **с НДС**. В денежные поля вводятся только цифры. (`33` §1, `30`)
- **Даты** — хранение ISO `YYYY-MM-DD`; отображение `ДД.ММ.ГГ`. Метки времени — `YYYY-MM-DD HH:MM:SS`. (`33` §1)
- **Часовой пояс** — все «сегодня»/просрочка/метки — по **Europe/Moscow**. (`33` §1, `32` §3)
- **Числа** — разделитель тысяч пробел; дробная часть — запятая. (`33` §1)
- **Авторизация** — сессия в **httpOnly-cookie**; авто-выход по простою **120 минут**; «Запомнить меня» — продлённая cookie; 2FA нет; защита от перебора не на старте. (`04`, `33` §5)
- **Пароли** — только хэш (bcrypt), **минимум 8 символов**; `must_change_password` форсирует смену при первом входе. (`04`)
- **Пагинация** списков — **50** строк (`?page=&page_size=`, ответ с `total`). (`31`, `33` §8)
- **Активные по умолчанию** — GET-списки рабочих страниц отдают только активные; `?include_archived=1` добавляет завершённые/отменённые. Реестр «Оплаты» по умолчанию отдаёт **все** УПД. (`31`, `02` §7.1)
- **Конкурентность** — last-write-wins, без блокировок. (`33` §7)
- **Коды ошибок API** — `401` не авторизован · `403` нет прав · `404` не найдено · `409` конфликт · `422` валидация. (`31`)
- **Аудит** — каждый изменяющий запрос пишет запись в `audit_log`. (`31`, `33` §2)
- **Идентификаторы вводятся вручную** — `Т-67` (комплектовщик), `№ заявки`/`№ процедуры` (закупщик), `№ УПД` (сопровождение). (`01` §3.8)
- **Источник истины — `docs/`.** Прототип (`Concept design/`) — только визуальный канон; его 2-уровневая модель, отдел «Оплата» и поле «Лот» **не реализуются**. (`40` §3)

---

## File Structure

```
backend/
  pyproject.toml
  app/
    main.py            # FastAPI-приложение, CORS, подключение роутеров, обработчики ошибок
    config.py          # настройки: путь к БД, TZ, секрет сессии, idle-timeout
    db.py              # engine, SessionLocal, get_db, PRAGMA foreign_keys
    models.py          # SQLAlchemy-модели всех таблиц (30-db-schema.md)
    security.py        # хэш паролей, выпуск/чтение сессии, current_user, require_password_changed
    permissions.py     # RBAC: can(user, block, action) + зависимости-гарды
    audit.py           # write_audit(db, entity_kind, entity_id, user, action)
    calculations.py    # производные: суммы, прогресс, просрочка, агрегат док-тов, дашборд, отчёты
    seed.py            # первый Админ + справочники dict
    schemas/           # Pydantic-схемы по доменам (auth, requests, procedures, payments, ...)
    routers/           # auth, users, requests, procurement, support, payments,
                       # dashboard, reports, dict, comments, history, search
  migrations/          # Alembic
  tests/               # pytest: conftest, по одному модулю на роутер + calculations + permissions
frontend/
  index.html
  package.json  tsconfig.json  vite.config.ts
  src/
    main.tsx  App.tsx           # роутер вкладок, провайдеры
    styles/zakupki-crm.css      # порт дизайн-токенов и компонентов из концепта
    lib/format.ts               # money/date/number форматирование (ru-RU, копейки, Москва)
    lib/permissions.ts          # клиентское гейтинг прав (зеркало server permissions)
    api/client.ts               # fetch-обёртка (credentials:'include'), обработка 401/403
    api/<domain>.ts             # типизированные вызовы по доменам
    auth/AuthContext.tsx  Login.tsx  ChangePassword.tsx  Guards.tsx
    components/                 # CommandBar, Tabs, DataTable, Chip, DocSquares, Progress,
                                # OverduePct, Modal, FilterBar, ExcelTable, EmptyState
    pages/                      # Dashboard, Komplektaciya, Zakupka, Soprovozhdenie, Oplaty, Otchety
    cards/                      # RequestCard (режимы A/Б1/Б2), PaymentCard
```

**Принципы декомпозиции:** один файл — одна ответственность; роутеры и Pydantic-схемы дробятся по доменам (меняются вместе — лежат вместе); `models.py` единый (≈11 таблиц, удобно держать в одном контексте); тяжёлая бизнес-логика расчётов изолирована в `calculations.py` и покрывается юнит-тестами без HTTP.

---
---

## Фаза 0 — Каркас проекта и инструментарий

**Цель / Результат:** Бэкенд и фронтенд поднимаются по одной команде; есть health-эндпоинт; фронтенд показывает «шапку» приложения (командная строка + вкладки), визуально совпадающую с концептом; настроены тесты и линтер.

**Файлы:**
- Create: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/config.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/zakupki-crm.css`, `frontend/src/components/CommandBar.tsx`, `frontend/src/components/Tabs.tsx`
- Create: `README.md` (как запускать back/front)

**Интерфейсы (Produces):**
- Backend: `GET /health` → `{"status":"ok"}`. Запуск: `uvicorn app.main:app --reload` (порт 8000).
- Frontend: Vite dev-сервер на `http://localhost:5173`; прокси `/api` → `http://localhost:8000`.
- `zakupki-crm.css` с токенами `:root{--canvas,--surface,--ink,--proc,--supp,--pay,--ok,--late,--signal,...}` (порт из `Concept design/zakupki-crm.css`) и шрифтами IBM Plex.

**Задачи:**

- [ ] **Задача 0.1 — Backend-каркас и health.**
  - [ ] Шаг 1 (тест): `backend/tests/test_health.py`
    ```python
    def test_health(client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
    ```
  - [ ] Шаг 2 (conftest): `backend/tests/conftest.py`
    ```python
    import pytest
    from fastapi.testclient import TestClient
    from app.main import app

    @pytest.fixture
    def client():
        return TestClient(app)
    ```
  - [ ] Шаг 3 (красный): `cd backend && pytest tests/test_health.py -v` → FAIL (нет `app.main`).
  - [ ] Шаг 4 (реализация): `backend/app/main.py`
    ```python
    from fastapi import FastAPI
    app = FastAPI(title="CRM Ultima")

    @app.get("/health")
    def health():
        return {"status": "ok"}
    ```
    + `backend/app/config.py` (заготовка: `DB_PATH`, `TZ="Europe/Moscow"`, `SESSION_SECRET`, `IDLE_TIMEOUT_MIN=120`), `pyproject.toml` (deps: fastapi, uvicorn, sqlalchemy, alembic, pydantic, passlib[bcrypt], itsdangerous, httpx, pytest, ruff).
  - [ ] Шаг 5 (зелёный): `pytest -v` → PASS.
  - [ ] Шаг 6 (коммит): `git add backend && git commit -m "chore(backend): FastAPI scaffold + health endpoint"`

- [ ] **Задача 0.2 — Frontend-каркас (Vite + React + TS) и порт дизайн-системы.**
  - [ ] Шаг 1: инициализировать Vite (`npm create vite@latest frontend -- --template react-ts`), установить зависимости (`react-router-dom`, `@tanstack/react-query`).
  - [ ] Шаг 2: **скопировать** `Concept design/zakupki-crm.css` → `frontend/src/styles/zakupki-crm.css` без изменений (это канон токенов); подключить IBM Plex в `index.html` (как в `Concept design/index.html` строки 7–9).
  - [ ] Шаг 3: `App.tsx` — роутер с вкладками **Дашборд / Комплектация / В закупке / В сопровождении / Оплаты / Отчёты**; `CommandBar.tsx` — тёмная шапка `.cmd` (логотип-марка, глобальный поиск-заглушка, блок пользователя), `Tabs.tsx` — `.tabs/.tab` со счётчиками-заглушками (`—`). Разметку взять из `Concept design/index.html` строки 13–31, классы — из CSS.
  - [ ] Шаг 4 (проверка): `npm run dev`, открыть `http://localhost:5173` — видна шапка и вкладки, шрифт IBM Plex, тёмный command bar, активная вкладка подчёркнута.
  - [ ] Шаг 5 (коммит): `git add frontend && git commit -m "chore(frontend): Vite+React+TS scaffold, port design tokens, app shell"`

**⏸ СТОП — ПРОВЕРКА (Фаза 0).**
- Команды: `cd backend && pytest -v` → все PASS; `cd frontend && npm run dev` → старт без ошибок.
- Глазами (человек): на `http://localhost:5173` видна тёмная командная строка с маркой и поиском, ряд вкладок, корректные шрифты/цвета (сверить с `Concept design/index.html`, открытым в браузере рядом). Консоль браузера без ошибок.
- **Жду подтверждения пользователя перед Фазой 1.**

🔎 **ui-checker (лёгкая сверка каркаса).** Диспетчеризовать агента `ui-checker` с задачей: открыть `http://localhost:5173`, снять snapshot+screenshot шапки и вкладок, сверить токены/шрифты/высоту командной строки с каноном `Concept design/index.html`; проверить чистоту консоли. *(Агент уже настроен под проект — достаточно передать сценарий фазы.)* Если `subagent_type: "ui-checker"` недоступен — выполнить ту же проверку напрямую инструментами Playwright MCP.

---

## Фаза 1 — Схема БД, миграции, seed

**Цель / Результат:** Все таблицы из `docs/30-db-schema.md` созданы (с `PRAGMA foreign_keys=ON`, CHECK-ограничениями, индексами); Alembic-миграция применяется; seed создаёт предзаполненного Админа (`must_change_password=1`) и справочники статусов.

**Файлы:**
- Create: `backend/app/db.py`, `backend/app/models.py`, `backend/app/seed.py`, `backend/migrations/` (alembic init + первая ревизия), `backend/tests/test_schema.py`, `backend/tests/test_seed.py`

**Интерфейсы (Produces):**
- SQLAlchemy-модели: `User, ParentRequest, RequestedPosition, Tender, Procedure, Delivery, ProcedurePosition, UpdPayment, UpdPosition, Comment, AuditLog, Dict` — имена полей **дословно** из DDL (`30`).
- `get_db()` — зависимость FastAPI, открывает сессию с `PRAGMA foreign_keys=ON`.
- `seed_initial(db)` — идемпотентно создаёт Админа и `dict`-значения (`status_zakup`: Приём заявок…На сделку; `status_sdelki`: Согласование/Подготовка ДД/Подписано).

**Задачи:**

- [ ] **Задача 1.1 — Модели и таблицы.**
  - [ ] Шаг 1 (тест): `backend/tests/test_schema.py` — создать БД в памяти, проверить наличие всех таблиц и ключевых CHECK:
    ```python
    from sqlalchemy import inspect
    def test_all_tables_exist(db):
        names = set(inspect(db.bind).get_table_names())
        assert {"user","parent_request","requested_position","tender","procedure",
                "delivery","procedure_position","upd_payment","upd_position",
                "comment","audit_log","dict"} <= names

    def test_procedure_status_postavki_check(db):
        # вставка недопустимого статуса поставки должна падать
        ...
    ```
  - [ ] Шаг 2 (красный): `pytest tests/test_schema.py -v` → FAIL.
  - [ ] Шаг 3 (реализация): `backend/app/models.py` — перенести **построчно** DDL из `docs/30-db-schema.md` (строки 17–179) в SQLAlchemy-модели. Сохранить: типы (деньги `Integer` копейки, даты `String` ISO, булевы `Integer` 0/1), `UNIQUE`, `CHECK(...)`, `ON DELETE CASCADE`, дефолты (`datetime('now')`, `date('now')`). `backend/app/db.py` — engine на файл `crm.db`, событие `connect` ставит `PRAGMA foreign_keys=ON`.
  - [ ] Шаг 4: добавить все индексы из `30` (строки 209–225).
  - [ ] Шаг 5 (зелёный): `pytest tests/test_schema.py -v` → PASS.
  - [ ] Шаг 6 (коммит): `git commit -m "feat(db): SQLAlchemy models for full schema (30-db-schema)"`

- [ ] **Задача 1.2 — Alembic-миграция.**
  - [ ] Шаг 1: `alembic init migrations`, настроить `env.py` на `app.models.Base.metadata` и `DB_PATH`.
  - [ ] Шаг 2: `alembic revision --autogenerate -m "initial schema"`; вычитать ревизию — убедиться, что CHECK/индексы попали (autogenerate в SQLite иногда теряет CHECK — дописать руками при необходимости).
  - [ ] Шаг 3 (проверка): `alembic upgrade head` на чистой БД → файл `crm.db` с полной схемой; `alembic downgrade base` → чисто.
  - [ ] Шаг 4 (коммит): `git commit -m "feat(db): initial Alembic migration"`

- [ ] **Задача 1.3 — Seed (первый Админ + справочники).**
  - [ ] Шаг 1 (тест): `backend/tests/test_seed.py`
    ```python
    def test_seed_creates_admin(db):
        from app.seed import seed_initial
        seed_initial(db)
        admin = db.query(User).filter_by(email="admin@crm.local").one()
        assert admin.global_role == "Админ"
        assert admin.must_change_password == 1
        assert admin.password_hash and admin.password_hash != "admin"  # хэш, не plain

    def test_seed_dicts(db):
        seed_initial(db); seed_initial(db)  # идемпотентность
        zk = {d.value for d in db.query(Dict).filter_by(kind="status_zakup")}
        assert zk == {"Приём заявок","Торги","Тех. экспертиза","Дозапросы","Согласование","На сделку"}
    ```
  - [ ] Шаг 2 (красный) → FAIL.
  - [ ] Шаг 3 (реализация): `backend/app/seed.py` — хэшировать дефолтный пароль (например `change-me-123`, ≥8), вставить Админа из `30` (строки 186–188) и `dict` (190–200), идемпотентно (проверять существование).
  - [ ] Шаг 4 (зелёный) → PASS.
  - [ ] Шаг 5 (коммит): `git commit -m "feat(db): initial seed — admin + status dicts"`

**⏸ СТОП — ПРОВЕРКА (Фаза 1).**
- Команды: `cd backend && pytest tests/test_schema.py tests/test_seed.py -v` → PASS; `alembic upgrade head && python -c "from app.db import SessionLocal; from app.seed import seed_initial; seed_initial(SessionLocal())"` → создаётся `crm.db`.
- Человек: открыть `crm.db` (DB Browser for SQLite) — проверить 12 таблиц, индексы, запись Админа (`must_change_password=1`, пароль — хэш), 6+3 значения в `dict`.
- **Жду подтверждения перед Фазой 2.** (UI на этой фазе нет — ui-checker не задействуется.)

---

## Фаза 2 — Авторизация и пользователи

**Цель / Результат:** Полный цикл входа/выхода, текущий пользователь и его права, смена пароля (в т.ч. принудительная при первом входе), управление пользователями Админом. На фронте — экран логина, форсированная смена пароля, гейт приложения по сессии.

**Файлы:**
- Create: `backend/app/security.py`, `backend/app/schemas/auth.py`, `backend/app/routers/auth.py`, `backend/app/routers/users.py`, `backend/tests/test_auth.py`, `backend/tests/test_users.py`
- Modify: `backend/app/main.py` (подключить роутеры, middleware сессии)
- Create: `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/Login.tsx`, `frontend/src/auth/ChangePassword.tsx`, `frontend/src/auth/Guards.tsx`
- Modify: `frontend/src/App.tsx` (обернуть в AuthProvider + гейт)

**Интерфейсы (Produces):**
- `current_user(request, db) -> User` — зависимость; читает подписанную cookie сессии, обновляет «последнюю активность», вышибает по простою >120 мин → `401`.
- `require_password_changed(user)` — если `must_change_password=1`, любые изменяющие запросы → `403` (кроме `/auth/change-password`, `/auth/logout`, `/auth/me`). (`31` §1)
- Эндпоинты (`31` §1): `POST /auth/login {email,password,remember_me}`; `POST /auth/logout`; `GET /auth/me` → `{user, permissions, must_change_password}`; `POST /auth/change-password {current,new}`; `GET /users`; `POST /users {...}`; `PATCH /users/{id}`; `POST /users/{id}/reset-password`.
- Frontend: `AuthContext` с `{me, login, logout, changePassword}`; `apiClient` (`credentials:'include'`, на `401`→редирект на логин).

**Задачи:**

- [ ] **Задача 2.1 — Хэш паролей и сессия.** (`security.py`)
  - [ ] Шаг 1 (тест): хэш/верификация bcrypt; round-trip сессии (подпись `itsdangerous`, payload `{user_id, last_active}`); просрочка по простою.
    ```python
    def test_password_hash_roundtrip():
        h = hash_password("secret12")
        assert verify_password("secret12", h) and not verify_password("x", h)

    def test_session_expires_after_idle(monkeypatch):
        token = make_session(user_id=1, remember=False, now=T0)
        assert read_session(token, now=T0 + 119*60) is not None
        assert read_session(token, now=T0 + 121*60) is None  # >120 мин простоя
    ```
  - [ ] Шаг 2 (красный) → FAIL.
  - [ ] Шаг 3 (реализация): `hash_password/verify_password` (passlib bcrypt), `make_session/read_session` (itsdangerous, idle-timeout из `IDLE_TIMEOUT_MIN`, «remember» продлевает срок cookie). Пароль <8 символов → `ValueError` (используется при смене/создании).
  - [ ] Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 2.2 — Логин/логаут/me + форс-смена пароля.** (`routers/auth.py`)
  - [ ] Шаг 1 (тест) `test_auth.py`:
    ```python
    def test_login_sets_cookie_and_me(client_seeded):
        r = client_seeded.post("/auth/login", json={"email":"admin@crm.local","password":"change-me-123","remember_me":False})
        assert r.status_code == 200
        me = client_seeded.get("/auth/me").json()
        assert me["user"]["global_role"] == "Админ"
        assert me["must_change_password"] is True

    def test_must_change_password_blocks_mutations(client_seeded):
        client_seeded.post("/auth/login", json={...})
        # любая изменяющая операция до смены пароля → 403
        assert client_seeded.post("/users", json={...}).status_code == 403

    def test_change_password_clears_flag(client_seeded):
        ...  # после смены must_change_password=False, мутации разрешены

    def test_wrong_credentials_401_no_hint(client_seeded):
        r = client_seeded.post("/auth/login", json={"email":"admin@crm.local","password":"bad"})
        assert r.status_code == 401  # без указания, что именно неверно

    def test_inactive_user_cannot_login(...):
        ...
    ```
  - [ ] Шаг 2 (красный) → FAIL.
  - [ ] Шаг 3 (реализация): эндпоинты `/auth/*`; cookie httpOnly+SameSite=Lax (Secure при HTTPS); `/auth/me` возвращает пользователя + вычисленные права (из `permissions.py`, см. Фаза 3 — на этой фазе вернуть базовую заглушку прав, расширить в 3.1) + `must_change_password`. Зависимость `require_password_changed` навесить на изменяющие роутеры.
  - [ ] Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 2.3 — Управление пользователями (только Админ).** (`routers/users.py`)
  - [ ] Шаг 1 (тест) `test_users.py`: создать пользователя-отдел и пользователя-глоброль; не-Админ получает `403`; `reset-password` ставит `must_change_password=1`; блокировка (`is_active=0`) запрещает вход; email-дубль → `409`. Валидация: `account_type='department'` требует `department`; `'global'` требует `global_role`.
  - [ ] Шаг 2 (красный) → FAIL.
  - [ ] Шаг 3 (реализация): `POST/GET/PATCH /users`, `POST /users/{id}/reset-password`; начальный пароль ставит `must_change_password=1`; деактивация вместо удаления (`04` §6 — жёсткого DELETE нет). Поля — из `04` §2 / `30` (user).
  - [ ] Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 2.4 — Frontend: логин, гейт, форс-смена.**
  - [ ] Шаг 1: `api/client.ts` (`fetch`, `credentials:'include'`, JSON, на `401`→`AuthContext.logout()`); `api/auth.ts` (login/logout/me/changePassword).
  - [ ] Шаг 2: `AuthContext` грузит `/auth/me` при старте; `Guards` — если не залогинен → `Login`; если `must_change_password` → `ChangePassword` (блокирует доступ к приложению).
  - [ ] Шаг 3: `Login.tsx` — форма email+пароль+«Запомнить меня», ошибка входа без подсказки; `ChangePassword.tsx` — текущий+новый (≥8). Стили — токены из `zakupki-crm.css` (поля `.rep-sel`, кнопки `.btn.primary`).
  - [ ] Шаг 4 (проверка): вход дефолтным Админом → форсируется смена пароля → после смены виден shell приложения; «Выйти» → снова логин.
  - [ ] Шаг 5 (коммит): `git commit -m "feat(auth): login, session gate, forced password change"`

**⏸ СТОП — ПРОВЕРКА (Фаза 2).**
- Команды: `cd backend && pytest tests/test_auth.py tests/test_users.py -v` → PASS.
- Человек: на фронте войти `admin@crm.local` / дефолтный пароль → требуется смена → сменить → попасть в приложение; повторный вход новым паролём; «Выйти». Проверить, что чужие изменяющие запросы под не-Админом дают 403 (например, через вкладку Network).
- **Жду подтверждения перед Фазой 3.**

🔎 **ui-checker.** Сценарий: открыть `5173`, снять экран логина и модалку форс-смены пароля; проверить, что неверный вход показывает обобщённую ошибку; консоль/сеть чистые (login → 200, me → 200). Канон стиля — токены `zakupki-crm.css`.

---

## Фаза 3 — Ядро прав (RBAC), общие хелперы, справочники, аудит

**Цель / Результат:** Единая точка проверки прав «роль → блок → действие»; общие механизмы списков (активные/архив, пагинация); запись аудита; эндпоинты справочников и (скелет) глобального поиска. Это фундамент, на который опираются все страничные фазы.

**Файлы:**
- Create: `backend/app/permissions.py`, `backend/app/audit.py`, `backend/app/routers/dict.py`, `backend/app/routers/search.py`, `backend/tests/test_permissions.py`, `backend/tests/test_dict.py`
- Create: `frontend/src/lib/permissions.ts`
- Modify: `backend/app/routers/auth.py` (`/auth/me` отдаёт полную карту прав)

**Интерфейсы (Produces):**
- `can(user, block, action) -> bool`, где `block ∈ {komplektaciya, zakupka, soprovozhdenie, oplaty, reports, admin}`. Матрица — из `03-roles-permissions.md` §4:
  - Сотрудник отдела — действия своего блока; чужие блоки — только просмотр.
  - Куратор — полный доступ к своему блоку (Сопровождение → `soprovozhdenie` **и** `oplaty`); + `reports`.
  - Руководитель — только просмотр + `reports`; изменяющих действий нет.
  - Админ — всё + `admin` (пользователи, справочники).
- Гард-зависимости: `require_action(block, action)` для роутеров.
- `paginate(query, page, page_size=50) -> {items, total}`; `apply_archive_filter(query, include_archived)`.
- `write_audit(db, entity_kind, entity_id, user, action)`.
- `/auth/me` → `permissions`: словарь блок→{view,edit} для клиентского гейтинга.

**Задачи:**

- [ ] **Задача 3.1 — Матрица прав.** (`permissions.py`)
  - [ ] Шаг 1 (тест) `test_permissions.py` — табличный тест по `03` §4/§4-границы:
    ```python
    @pytest.mark.parametrize("user,block,action,expected", [
      (zakupki_emp, "zakupka", "edit", True),
      (zakupki_emp, "komplektaciya", "edit", False),
      (zakupki_emp, "komplektaciya", "view", True),
      (soprov_curator, "oplaty", "edit", True),     # куратор Сопровождения владеет и Оплатами
      (soprov_curator, "zakupka", "edit", False),
      (ruk, "zakupka", "edit", False), (ruk, "reports", "view", True),
      (admin, "admin", "edit", True),
      (kompl_emp, "reports", "view", False),          # сотрудники отделов не видят отчёты
    ])
    def test_can(user, block, action, expected):
        assert can(user, block, action) is expected
    ```
  - [ ] Шаг 2 (красный) → FAIL.
  - [ ] Шаг 3 (реализация): чистые функции по `03` §3 (видимость) и §4 (действия); маппинг отдел→блок (Комплектация→komplektaciya, Закупки→zakupka, Сопровождение→{soprovozhdenie,oplaty}); `require_action` бросает `403`. Видимость страниц: рабочие — всем (view), `reports` — Куратор/Руководитель/Админ (`03` §3).
  - [ ] Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 3.2 — Аудит + хелперы списков.** (`audit.py`, в `permissions.py`/`db.py` — пагинация/архив)
  - [ ] Шаг 1 (тест): `write_audit` пишет строку с `entity_kind/entity_id/user_id/action/created_at`; `paginate` возвращает `total` и срез по `page_size=50`.
  - [ ] Шаг 2 (красный) → FAIL. Шаг 3 (реализация). Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 3.3 — Справочники.** (`routers/dict.py`, `31` §7)
  - [ ] Шаг 1 (тест): `GET /dict/status_zakup` (все, view) возвращает seed-значения по `sort_order`; `POST/DELETE /dict/{kind}` — только Админ (иначе 403); добавление/удаление работает.
  - [ ] Шаг 2 (красный) → FAIL. Шаг 3 (реализация). Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 3.4 — Скелет глобального поиска.** (`routers/search.py`, `31` §6.1)
  - [ ] Реализовать `GET /search?q=` с группировкой по типам (`Т-67`/№заявки/№процедуры/поставщик/№УПД). На этой фазе — поиск по родителям/процедурам (что уже есть); расширять по мере появления сущностей. Тест: пустой результат при отсутствии данных, корректная группировка на фикстуре.

- [ ] **Задача 3.5 — Клиентский гейтинг прав.** (`frontend/src/lib/permissions.ts`)
  - [ ] Зеркало серверной карты: хелпер `canEdit(me, block)` для скрытия/блокировки кнопок. Источник — `permissions` из `/auth/me` (UI не доверяет себе — сервер всё равно проверяет).

**⏸ СТОП — ПРОВЕРКА (Фаза 3).**
- Команды: `pytest tests/test_permissions.py tests/test_dict.py -v` → PASS (особое внимание — граница «куратор Сопровождения владеет Оплатами» и «сотрудники не видят Отчёты»).
- Человек: через `/auth/me` под разными ролями (создать тестовых пользователей Админом) убедиться, что карта прав соответствует `03` §5.
- **Жду подтверждения перед Фазой 4.** (Самостоятельного UI нет — ui-checker не нужен.)

---

## Фаза 4 — Комплектация (заявки-родители) — сквозной срез

**Цель / Результат:** Первый полный вертикальный срез: бэкенд + страница + карточка. Комплектация заводит `Т-67` с позициями (включая **массовую вставку из Excel**), редактирует (пока `awaiting`), дублирует, отменяет/возвращает; Закупки «берут в работу» (создаётся торг + процедура по умолчанию, заявка уходит в «В закупке»).

**Файлы:**
- Create: `backend/app/schemas/requests.py`, `backend/app/routers/requests.py`, `backend/tests/test_requests.py`
- Create: `frontend/src/api/requests.ts`, `frontend/src/pages/Komplektaciya.tsx`, `frontend/src/cards/RequestCard.tsx` (режим A), `frontend/src/components/ExcelTable.tsx`, `frontend/src/components/DataTable.tsx`, `frontend/src/components/Chip.tsx`, `frontend/src/components/FilterBar.tsx`, `frontend/src/components/Modal.tsx`, `frontend/src/components/EmptyState.tsx`, `frontend/src/lib/format.ts`
- Modify: `frontend/src/App.tsx`, `Tabs.tsx` (счётчик Комплектации)

**Интерфейсы (Produces) — из `31` §2:**
- `GET /requests?status=&search=&sort=&page=&page_size=` — список «Ожидают закупки» = родители **без процедур** (`02` §7.1); по умолчанию активные, `?include_archived=1` добавляет `cancelled`.
- `POST /requests {code,title,mtr,srok, positions:[{name,qty,unit,gost_tu,doc_code}]}` — `sostavitel/created_by` = текущий, `zagruzka` = сегодня, `status='awaiting'`. Дубль `code` → `409`.
- `GET /requests/{id}` — заявка + позиции + торги + процедуры.
- `PATCH /requests/{id}` — правка (только `awaiting`).
- `POST /requests/{id}/cancel` · `/uncancel` — `awaiting ⇄ cancelled`.
- `POST /requests/{id}/duplicate {code}` — копия с новым кодом.
- `POST /requests/{id}/take-to-work` (Закупки) — создаёт `tender` + `procedure` по умолчанию (`block='zakupka'`, `status_zakup='Новая'`, `block_entered_at=now`), копирует запрошенные позиции в позиции процедуры (`source_id` ссылается на запрошенную). Возвращает id процедуры.
- `GET/POST/PATCH/DELETE /requests/{id}/positions` — ведение запрошенных позиций; `POST` принимает **массив** строк (массовая вставка из Excel).
- `format.ts`: `money(kopecks)→"1 234 567 ₽"`, `dateRu(iso)→"ДД.ММ.ГГ"`, `num(n)`.

**Задачи:**

- [ ] **Задача 4.1 — Backend: CRUD заявок + позиции.**
  - [ ] Шаг 1 (тест) `test_requests.py`: создание с позициями; уникальность `code` (409); список «ожидают» исключает родителей с процедурами; правка запрещена не в `awaiting` (409/422); cancel/uncancel; duplicate с новым кодом; массовая вставка позиций (POST массивом); права: создавать может Комплектация/Куратор-Комплектации/Админ, иначе 403; каждое изменение пишет аудит.
  - [ ] Шаг 2 (красный) → FAIL.
  - [ ] Шаг 3 (реализация): `schemas/requests.py` (Pydantic), `routers/requests.py`; гарды `require_action("komplektaciya","edit")`; список — фильтр «без процедур»; `write_audit` на каждое изменение.
  - [ ] Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 4.2 — Backend: «Взять в работу».**
  - [ ] Шаг 1 (тест): `take-to-work` под Закупками создаёт 1 торг + 1 процедуру (block=zakupka, статус `Новая`, `block_entered_at` установлен), копирует позиции (`source_id` проставлен), и заявка **исчезает** из `/requests` (появились процедуры). Под Комплектацией → 403.
  - [ ] Шаг 2 (красный) → FAIL. Шаг 3 (реализация) — инвариант «торг всегда ≥1 процедуру» (`30` Инварианты). Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 4.3 — Frontend: общие компоненты.**
  - [ ] `format.ts`, `Chip.tsx` (классы `.chip.wait/.proc/.supp/.pay/.ok/.late/.cancel` из CSS), `DataTable.tsx` (`.reg`-таблица, клик по строке), `FilterBar.tsx`, `Modal.tsx` (закрытие по Esc и клику вне), `EmptyState.tsx`.
  - [ ] `ExcelTable.tsx` — **использовать скилл `excel-table`** (drop-in компонент со вставкой TSV из Excel/Sheets, навигацией стрелками/Tab/Enter, диапазонным выделением). Колонки позиций: Наименование, Кол-во, Ед. изм., ГОСТ/ТУ, Шифр документации (**без цены**).
  - [ ] Коммит после готовности базовых компонентов.

- [ ] **Задача 4.4 — Frontend: страница «Комплектация» + карточка (режим A).**
  - [ ] Шаг 1: `Komplektaciya.tsx` — заголовок «Ожидают закупки» + счётчик; кнопки «+ Заявка», «Экспорт»; `FilterBar` (статус, переключатель «Показать отменённые», поиск по коду/наименованию/составителю, сортировка); таблица колонок из `10` §3. Разметку и классы взять из прототипа (`tblAwaiting`, `Concept design/zakupki-crm.js`).
  - [ ] Шаг 2: модалка «+ Заявка» — поля шапки + `ExcelTable` позиций; на сохранении `POST /requests`.
  - [ ] Шаг 3: `RequestCard.tsx` режим A (`16` §2) — шапка заявки, таблица позиций с ведением (добавить/изменить/удалить/копировать + Excel-вставка), действия по роли (Комплектация: редактировать/дублировать/отменить; Закупки: «Взять в работу»), блок комментариев (заглушка до Фазы 10 или сразу через `/comments`).
  - [ ] Шаг 4 (проверка): создать `Т-67`, вставить позиции из Excel, сохранить; «Взять в работу» → заявка уходит из списка; счётчик вкладки обновился.
  - [ ] Шаг 5 (коммит): `git commit -m "feat(komplektaciya): page + create modal + request card (mode A)"`

**⏸ СТОП — ПРОВЕРКА (Фаза 4).**
- Команды: `pytest tests/test_requests.py -v` → PASS.
- Человек: на фронте под Комплектацией — создать заявку с Excel-вставкой позиций; отредактировать; отменить и вернуть; дублировать (новый код); под Закупками — «Взять в работу» (заявка исчезает из «Ожидают закупки»). Под Руководителем кнопки действий скрыты.
- **Жду подтверждения перед Фазой 5.**

🔎 **ui-checker.** Сценарии: страница «Комплектация» (сверка колонок/чипов/плотности с `tblAwaiting` концепта), модалка создания (обязательность кода/наименования; вставка из Excel заполняет строки), карточка режима A, переключатель «Показать отменённые» (чип `cancel` — зачёркнутый серый). Проверить даты `ДД.ММ.ГГ`, консоль/сеть чистые (POST `/requests`→2xx). Канон — `Concept design/index.html`. Формат отчёта агента: PASS/FAIL + расхождения с критичностью.

---

## Фаза 5 — В закупке (процедуры)

**Цель / Результат:** Закупщик ведёт процедуру: заводит № заявки/№ процедуры, дробит по поставщикам (с дроблением количества), ведёт позиции с **ценой (с НДС)**, ставит рабочие статусы (`Приём заявок…На сделку`), отменяет/возвращает, передаёт в сопровождение.

**Файлы:**
- Create: `backend/app/schemas/procedures.py`, `backend/app/routers/procurement.py`, `backend/tests/test_procurement.py`
- Create: `frontend/src/api/procedures.ts`, `frontend/src/pages/Zakupka.tsx`; Modify: `frontend/src/cards/RequestCard.tsx` (режим Б1: переключатель «сестёр», позиции с ценой, разбиение)

**Интерфейсы (Produces) — из `31` §3:**
- `GET /procurement?filter*&sort&search&page` — процедуры `block='zakupka'`, активные (≠`Отменена`) по умолчанию. Колонки/фильтры/сортировки — `11` §3.
- `GET /procedures/{id}` — детали (общий для фаз 5–6).
- `PATCH /procedures/{id}` (Закупки) — `tender.num, proc, supplier, fio_zakupshchik, pub_start, pub_end, mtr, status_zakup` (валидировать `status_zakup` по `dict` + служебные `Новая/Отменена` вне справочника, `30`).
- `POST /procedures/{id}/split {positions:[{source_position_id, qty}], proc?, num?, supplier?}` — новая процедура в том же торге + перенос позиций с дроблением `qty`; **инвариант:** Σ qty по одной `source_id` ≤ qty запрошенной (`01` §3) → иначе `422`.
- `POST /procedures/{id}/cancel` · `/uncancel` — `Отменена` (обратимо, остаётся в блоке).
- `POST /procedures/{id}/to-support` — из `На сделку` → `block='soprovozhdenie'`, `status_postavki='Новая'`, `block_entered_at=now`; иначе `409`.
- `GET/POST/PATCH/DELETE /procedures/{id}/positions` — позиции процедуры (+`price` копейки, копирование, массовая вставка; `source_id=null` для добавленных закупщиком).

**Задачи:**

- [ ] **Задача 5.1 — Backend: чтение/правка процедур + статусы.**
  - [ ] Тесты: список закупки (только zakupka/активные); PATCH полей; недопустимый `status_zakup` (не из dict и не служебный) → 422; cancel/uncancel; права (Закупки/Куратор-Закупок/Админ edit; иначе 403); аудит.
  - [ ] Красный → реализация → зелёный → коммит.

- [ ] **Задача 5.2 — Backend: разбиение и позиции с ценой.**
  - [ ] Тесты: `split` создаёт процедуру-сестру, переносит позиции, дробит qty, нарушение инварианта → 422; ведение позиций с `price`; копирование строки; `to-support` только из `На сделку` (иначе 409) и проставляет `block_entered_at`.
  - [ ] Красный → реализация → зелёный → коммит.

- [ ] **Задача 5.3 — Frontend: страница «В закупке» + карточка (режим Б1).**
  - [ ] `Zakupka.tsx` — таблица процедур (колонки `11` §3, чип `proc`/`cancel`), расширенные фильтры/сортировка/поиск; in-place правка № заявки/№ процедуры/поставщика/дат/статуса в строке (optimistic, last-write-wins); кнопка «+ Заявка» — **заглушка** (`11` §9); «Экспорт».
  - [ ] `RequestCard` режим Б1 (`16` §3): шапка с **переключателем сестёр** (`.sib`), № заявки/№ процедуры, поставщик, ФИО закупщика; позиции процедуры с ценой и Excel-вставкой; действия Закупок (разбить, выбрать поставщика, статус, отменить, передать в сопровождение из `На сделку`); комментарии + «История».
  - [ ] Проверка: разбить процедуру на двух поставщиков с дроблением; провести по статусам до «На сделку»; «Передать в сопровождение». Коммит.

**⏸ СТОП — ПРОВЕРКА (Фаза 5).**
- Команды: `pytest tests/test_procurement.py -v` → PASS (особо — инвариант дробления и переход `to-support`).
- Человек: «Взять в работу» заявку из Фазы 4 → в «В закупке» появилась процедура по умолчанию; задать № заявки/процедуры/поставщика, цены позиций; разбить на 2 поставщика; довести до «На сделку»; передать в сопровождение (процедура уходит из блока). Проверить независимость статусов «сестёр».
- **Жду подтверждения перед Фазой 6.**

🔎 **ui-checker.** Сценарии: страница «В закупке» (колонки/чипы/«не выбран» курсивом для пустого поставщика), in-place правка ячейки (optimistic, при ошибке — toast), карточка Б1 с переключателем сестёр, диалог разбиения. Сверка с `tblProc` концепта; консоль/сеть чистые. Канон — `Concept design/index.html`.

---

## Фаза 6 — В сопровождении + поставки + расчёты

**Цель / Результат:** Сопровождение ведёт договор и сумму, создаёт **частичные поставки** (не пустые) из «ожидают отгрузки», отмечает документы (ТТН/М-15/УПД/Серт), ставит статусы поставки/сделки, вводит № УПД (→ создаётся запись в «Оплаты»). Реализованы все производные расчёты страницы.

**Файлы:**
- Create: `backend/app/calculations.py`, `backend/app/schemas/deliveries.py`, `backend/app/routers/support.py`, `backend/tests/test_calculations.py`, `backend/tests/test_support.py`
- Create: `frontend/src/api/support.ts`, `frontend/src/pages/Soprovozhdenie.tsx`, `frontend/src/components/DocSquares.tsx`, `frontend/src/components/Progress.tsx`, `frontend/src/components/OverduePct.tsx`; Modify: `RequestCard.tsx` (режим Б2)

**Интерфейсы (Produces):**
- `calculations.py` (чистые функции, по `32`): `position_sum`, `procedure_sum`, `progress(proc)→(x,y,pct)`, `is_delivery_overdue`, `is_delivery_late`, `is_procedure_overdue`, `overdue_pct(proc)`, `docs_aggregate(proc)→{ТТН,М15,УПД,Серт: bool}`, `is_upd_overdue`. «Сегодня» — `Europe/Moscow`.
- API (`31` §4): `GET /support?...`; `PATCH /procedures/{id}` (Сопровождение): `contract, fio_dogovornik, contract_sum, status_sdelki, status_postavki, srok_dd, plan_date, fakt_date`; `POST /procedures/{id}/deliveries {positions:[procedure_position_id,...]}` (≥1, иначе 422); `DELETE /deliveries/{id}` (только `transit`, иначе 409); `PATCH /deliveries/{id}` (`status transit→done`, `date/eta`, флаги `doc_*`); `POST /deliveries/{id}/upd {upd}` → создаёт `upd_payment(origin='delivery', pay_status='await')`.

**Задачи:**

- [ ] **Задача 6.1 — Backend: расчётный модуль (юнит-тесты без HTTP).**
  - [ ] Шаг 1 (тест) `test_calculations.py` — таблично по `32`: суммы; прогресс X/Y (Y=всего позиций, X=в полученных поставках); просрочка поставки (`not done && srok_dd<today`); «с задержкой» (`done && date>srok_dd`); `overdue_pct` с порогами цвета 0/>0/≥50; агрегат документов («во всех поставках»; нет поставок → все false); просрочка УПД (`await && srok<today`). Зафиксировать «сегодня» = 2026-06-21 (Москва) через инъекцию.
  - [ ] Шаг 2 (красный) → FAIL. Шаг 3 (реализация) — формулы `32` §1–5 дословно. Шаг 4 (зелёный) → PASS. Коммит.

- [ ] **Задача 6.2 — Backend: список/правка сопровождения + поставки + УПД.**
  - [ ] Тесты: список (block=soprovozhdenie, активные = не завершена и ≠Отменена; `?include_archived` добавляет завершённые/отменённые, `02` §7.1); PATCH полей; создание поставки (не пустая, позиции уходят из «ожидают отгрузки»); расформирование только `transit` (done→409); переключение `doc_*`; `status transit→done` подставляет факт; ввод № УПД создаёт `upd_payment`; завершённость (`Поставлено`+все УПД оплачены) убирает из активных; права Сопровождения; аудит.
  - [ ] Красный → реализация → зелёный → коммит.

- [ ] **Задача 6.3 — Frontend: страница «В сопровождении» + карточка (режим Б2).**
  - [ ] `DocSquares.tsx` (4 квадрата `.docsq`), `Progress.tsx` (`.prog` доставлено/всего), `OverduePct.tsx` (`.ovd` с классами цвета). `Soprovozhdenie.tsx` — **fit-таблица** без горизонтального скролла (`table.reg.fit` + `colgroup` из `tblSupp` концепта), колонки `12` §3; расширенные фильтры; in-place правка статусов/План/Факт.
  - [ ] `RequestCard` режим Б2 (`16` §4): договор/сумма/ФИО договорника; статусы сделки/поставки; **поставки** (таблица позиций, кнопки-переключатели документов красный↔зелёный, № УПД, статус оплаты; создать/расформировать поставку, отметить получение); блок «Ожидают отгрузки» с «+ Создать поставку»; ввод № УПД; «История»; комментарии. Кнопка «+ Отгрузка» на странице — **заглушка** (`12` §9).
  - [ ] Проверка: завести договор и сумму; создать частичную поставку; отметить документы; отметить получение; ввести № УПД (появляется в «Оплаты» на след. фазе); проверить колонки «Просроч.»/«Док-ты»/«Поз.». Коммит.

**⏸ СТОП — ПРОВЕРКА (Фаза 6).**
- Команды: `pytest tests/test_calculations.py tests/test_support.py -v` → PASS (расчётный модуль — критичен).
- Человек: провести процедуру из Фазы 5 по сопровождению; создать ≥2 частичных поставки; убедиться в корректности прогресса, агрегата документов («зелёный только если во всех поставках»), % просрочки и цветовой семантики; расформировать `transit`-поставку (для `done` кнопка недоступна); ввести № УПД.
- **Жду подтверждения перед Фазой 7.**

🔎 **ui-checker.** Сценарии: «В сопровождении» — fit-таблица **без горизонтального скролла** на ≥1280px (ключевое требование `SPECIFICATION` §4.3), цвета `.ovd`/`.docsq`/`.prog`, чипы статусов; карточка Б2 — переключатели документов (красный с крестиком ↔ зелёный с галкой), создание/расформирование поставки, «ожидают отгрузки» (пунктирная рамка). Консоль/сеть чистые. Канон — `tblSupp`/`.delivery` из концепта. Проверить `browser_resize` 1280 и 1440.

---

## Фаза 7 — Оплаты (реестр УПД) + карточка платежа

**Цель / Результат:** Параллельный реестр всех УПД (из поставок + добавленные вручную), сводка (4 показателя + полоса распределения), проведение оплаты (только полная), карточка платежа.

**Файлы:**
- Create: `backend/app/schemas/payments.py`, `backend/app/routers/payments.py`, `backend/tests/test_payments.py`
- Create: `frontend/src/api/payments.ts`, `frontend/src/pages/Oplaty.tsx`, `frontend/src/cards/PaymentCard.tsx`
- Modify: `backend/app/calculations.py` (сводка «Оплаты»), `backend/app/routers/search.py` (искать по № УПД)

**Интерфейсы (Produces) — из `31` §5, `32` §7:**
- `GET /payments?...` — **все** УПД (полный реестр), переключатель «скрыть оплаченные» по умолчанию выкл.; фильтры/сортировки `13` §4.
- `POST /payments {upd, request_label, supplier, srok, amount, zrds, positions?}` (Сопровождение) — `origin='manual'`, `pay_status='await'`.
- `GET /payments/{id}`; `PATCH /payments/{id}` (`srok, zrds, contract, supplier, amount, positions`, флаги `doc_*`); `POST /payments/{id}/pay` → `paid` + дата (только полная).
- `calculations.payments_summary()` → `{paid, await, overdue, in_work}` + доли полосы: `{paid, await_, delivered_no_upd, contracted_no_delivery}` (`32` §7). Исключать УПД отменённых процедур; завершённые — учитывать.

**Задачи:**

- [ ] **Задача 7.1 — Backend: реестр, ручная УПД, оплата, сводка.**
  - [ ] Тесты: реестр содержит и `delivery`-, и `manual`-УПД; ручное добавление; `pay` переводит в `paid`+дата (повторно → 409/422); просрочка УПД производная; сводка и доли полосы по `32` §7 (с исключением отменённых); права Сопровождения/Куратора-Сопровождения/Админа; аудит.
  - [ ] Красный → реализация → зелёный → коммит.

- [ ] **Задача 7.2 — Frontend: страница «Оплаты» + карточка платежа.**
  - [ ] `Oplaty.tsx` — `payhero` (4 `.pcard`), полоса `.pbar` (4 сегмента `sp-paid/sp-out/sp-del/sp-con`), реестр `.utbl` (колонки `13` §4, чипы `.pchip await/paid/late`), переключатель «скрыть оплаченные», «+ Добавить УПД» (форма `13` §6), «Экспорт». Разметка — из `rPay`/`index.html` (строки 73–81).
  - [ ] `PaymentCard.tsx` (`17`): шапка (№ УПД, статус, сумма), поля (Заявка/Поставщик/Договор/ЗРДС/Срок), связанная поставка, документы-переключатели (для `delivery`), позиции, «История» (комментариев нет), действие «Провести оплату».
  - [ ] Проверка: УПД из Фазы 6 видна в реестре; добавить ручную УПД; провести оплату; сверить сводку/полосу. Коммит.

**⏸ СТОП — ПРОВЕРКА (Фаза 7).**
- Команды: `pytest tests/test_payments.py -v` → PASS.
- Человек: реестр показывает все УПД; ручная УПД; «Провести оплату» (полная) меняет статус и дату; просроченная УПД подсвечена; показатели сводки и доли полосы соответствуют `32` §7; переключатель «скрыть оплаченные» по умолчанию выключен.
- **Жду подтверждения перед Фазой 8.**

🔎 **ui-checker.** Сценарии: сводка (`payhero` + полоса распределения — доли и подписи), реестр (`pchip` статусы, прочерки для ручных УПД), форма «+ Добавить УПД», карточка платежа (документы только для УПД из поставки), «Провести оплату». Консоль/сеть чистые. Канон — `index.html` §payments.

---

## Фаза 8 — Дашборд

**Цель / Результат:** Обзорный экран (одинаков для всех ролей): 6 показателей, поток по этапам, «Требует внимания» + «Лента событий», компактные таблицы. Только просмотр/переходы.

**Файлы:**
- Create: `backend/app/routers/dashboard.py`, `backend/tests/test_dashboard.py`; Modify: `calculations.py` (6 показателей, поток, триггеры внимания)
- Create: `frontend/src/pages/Dashboard.tsx` (+ под-компоненты Meters, FlowRail, AttentionPanel, FeedPanel, CompactTables)

**Интерфейсы (Produces) — из `14`, `32` §6:**
- `GET /dashboard` → `{meters[6], flow, attention[], feed[], tables:{awaiting,procurement,support}}`.
- Показатели (`32` §6, **`Отменена` исключается**; завершённые — вне операционных счётчиков, но в финитогах): В закупке; В сопровождении (+Σ contract_sum); Поставки в срок (%); Просрочено (+Σ); УПД в оплате (+Σ); УПД просрочено (+Σ).
- «Требует внимания» (`14` §5 / `32`): просроченные поставки, отсутствие документов, **УПД без сертификата** (предупреждение — оплату провести можно), просроченные оплаты.
- «Лента событий» — последние N записей `audit_log` (глубина — деталь реализации, `14` §9).

**Задачи:**

- [ ] **Задача 8.1 — Backend: агрегаты дашборда.**
  - [ ] Тесты: каждый из 6 показателей на фикстуре с известными числами; исключение `Отменена`; учёт завершённых только в финитогах; состав «требует внимания» (включая УПД-без-серта как предупреждение); поток по стадиям. Красный → реализация → зелёный → коммит.

- [ ] **Задача 8.2 — Frontend: дашборд.**
  - [ ] `Dashboard.tsx` — `meters` (6 `.meter` с сегментами), `flowrail` (стадии с переходом по клику), `grid2` (Требует внимания/Лента), компактные таблицы (`14` §7, меньше колонок, чем на страницах). Разметка — из `index.html` (строки 34–45) и `rMeters/rFlow/rAlerts/rFeed/rDash` концепта. Клики ведут на страницы/карточки.
  - [ ] Проверка: цифры совпадают с расчётами; клики по стадиям/строкам открывают нужные экраны. Коммит.

**⏸ СТОП — ПРОВЕРКА (Фаза 8).**
- Команды: `pytest tests/test_dashboard.py -v` → PASS.
- Человек: сверить 6 показателей с данными (ручной пересчёт по `32` §6 на небольшом наборе); «Требует внимания» содержит ожидаемые триггеры; переходы по потоку и строкам работают; дашборд одинаков под всеми ролями.
- **Жду подтверждения перед Фазой 9.**

🔎 **ui-checker.** Дашборд — **главный экран канона**: сетка 6 показателей (на ≤1080px → 3 колонки, ≤720px → 2), `flowrail` со стрелками-разделителями, две панели, компактные таблицы. Сверка плотности/токенов с `index.html`. Проверить переходы (клик по стадии → страница). Консоль/сеть чистые. `browser_resize` 1280/1440.

---

## Фаза 9 — Отчёты + экспорт

**Цель / Результат:** Конструктор выгрузок (4 типа отчётов, период, фильтры) с экспортом Excel/PDF/CSV. Доступ — Куратор/Руководитель/Админ (Куратор видит все данные).

**Файлы:**
- Create: `backend/app/routers/reports.py`, `backend/tests/test_reports.py`; Modify: `calculations.py` (отчётные агрегаты `32` §8)
- Create: `frontend/src/pages/Otchety.tsx`

**Интерфейсы (Produces) — из `31` §6, `15`, `32` §8:**
- `GET /reports/{type}?period=&mtr=&supplier=&author=`, `type ∈ time/sums/late/people`. Доступ: Руководитель/Админ/Куратор (иначе 403; обычные сотрудники — нет страницы).
- `GET /reports/{type}/export?format=excel|pdf|csv`.
- Отчёты: время на этапе (`сегодня − block_entered_at`, флаг «зависло ≥3 дней`, `32` §8.1); суммы по этапам/поставщикам; просрочки (поставки+УПД); сводка по составителям/отделам. `Отменена` исключается; завершённые учитываются.

**Задачи:**

- [ ] **Задача 9.1 — Backend: 4 отчёта + экспорт.**
  - [ ] Тесты: каждый тип на фикстуре; права (403 для сотрудников; Куратор видит все данные, не только свой блок, `15` §1); «зависание ≥3 дней»; экспорт возвращает корректный `Content-Type` и непустое тело для excel/pdf/csv. Красный → реализация (openpyxl/reportlab/csv) → зелёный → коммит.

- [ ] **Задача 9.2 — Frontend: страница «Отчёты».**
  - [ ] `Otchety.tsx` — `rep-layout` (панель параметров слева sticky + вывод справа), типы (`rep-opt`), период/фильтры (`rep-sel`), «Сформировать», KPI-плашки и таблицы (`rtbl`), кнопки экспорта. Разметка — из `index.html` (90–108) и `runReport` концепта. Вкладка «Отчёты» видна только ролям с доступом.
  - [ ] Проверка: каждый тип отчёта; экспорт скачивает файл; сотруднику отдела вкладка недоступна. Коммит.

**⏸ СТОП — ПРОВЕРКА (Фаза 9).**
- Команды: `pytest tests/test_reports.py -v` → PASS.
- Человек: под Руководителем/Админом/Куратором — сформировать все 4 отчёта, проверить экспорт во всех форматах; под сотрудником отдела убедиться, что вкладка «Отчёты» отсутствует.
- **Жду подтверждения перед Фазой 10.**

🔎 **ui-checker.** Страница «Отчёты»: переключение типов, sticky-панель параметров, таблицы `rtbl` с итоговой строкой `tfoot`, кнопки экспорта. Видимость вкладки по роли. Консоль/сеть чистые. Канон — `index.html` §reports.

---

## Фаза 10 — Сквозное: поиск, история, комментарии, нефункциональное, регресс

**Цель / Результат:** Достроить сквозные механизмы и навести лоск: глобальный поиск в шапке, «История» (аудит) в карточках, комментарии, форматы/локаль, бэкап, и финальная регрессионная UI-проверка по чек-листу приёмки `40` §6.

**Файлы:**
- Modify: `backend/app/routers/search.py` (полный сквозной поиск); Create: `backend/app/routers/comments.py`, `backend/app/routers/history.py`, `backend/tests/test_search.py`, `backend/tests/test_comments.py`, `scripts/backup.py` (`33` §3)
- Modify: `frontend/src/components/CommandBar.tsx` (живой поиск), карточки (блоки «История»/«Комментарии»)

**Интерфейсы (Produces) — из `31` §6.1/§7, `33`:**
- `GET /search?q=` — сквозной по `Т-67`/№заявки/№процедуры/поставщику/№УПД, результаты сгруппированы по типу.
- `GET/POST /comments?target_kind=&target_id=` — лента + добавление (автор = текущий); привязка к parent/tender/procedure (`01` §2.7).
- `GET /history?entity_kind=&entity_id=` — аудит из `audit_log` (`33` §2), отображается как «История» в карточках `16`/`17`.
- `scripts/backup.py` — ежедневная копия `crm.db` (хранить 14), бэкап перед миграциями.

**Задачи:**

- [ ] **Задача 10.1 — Глобальный поиск (полный) + комментарии + история.**
  - [ ] Тесты: поиск находит сущности всех типов и группирует; комментарии добавляются с автором-снимком; история отдаёт записи аудита по сущности. Красный → реализация → зелёный → коммит.

- [ ] **Задача 10.2 — Frontend: поиск в шапке, История/Комментарии в карточках.**
  - [ ] Живой поиск в `CommandBar` (выпадающие сгруппированные результаты → переход на карточку); блок «История» в `RequestCard`/`PaymentCard`; лента комментариев (`.comments`, новые снизу) в карточках заявки.
  - [ ] Коммит.

- [ ] **Задача 10.3 — Нефункциональное: форматы, бэкап, проверка локали.**
  - [ ] Тесты формата (`format.ts`): деньги `1 234 567 ₽`, даты `ДД.ММ.ГГ`, дробные через запятую; `scripts/backup.py` создаёт копию и ротирует до 14. Коммит.

- [ ] **Задача 10.4 — Финальная сверка по чек-листу приёмки `40` §6.**
  - [ ] Пройти критерии приёмки: маршрут заявки сквозь все блоки; иерархия (1 `Т-67` → ≥1 торг → ≥1 процедура, независимость); статусы блочной модели, просрочка вычисляется, «Закрыта» нет; права (отдел/Куратор/Руководитель/Админ); деньги (копейки↔₽ с НДС); Excel-вставка; Оплаты (все УПД, полная оплата); расчёты по `32`.

**⏸ СТОП — ПРОВЕРКА (Фаза 10, финальная).**
- Команды: `cd backend && pytest -v` → **весь** набор PASS; `cd frontend && npm run build` → сборка без ошибок.
- Человек: пройти **полный маршрут** одной заявки от создания `Т-67` до оплаты всех УПД, под соответствующими ролями на каждом шаге; проверить глобальный поиск, «Историю», комментарии; сверить с чек-листом `40` §6.
- **Жду подтверждения — это завершение проекта.**

🔎 **ui-checker (полный регресс).** Прогнать все ключевые экраны (Дашборд, 4 рабочие страницы, 2 карточки, Отчёты, логин) на 1280 и 1440; сверить с каноном `Concept design/index.html`; проверить все сценарии приёмки `40` §6 (создание заявки, смена статусов, передача между блоками, частичные поставки, документы, проведение оплаты); консоль и сеть полностью чистые. Итоговый отчёт PASS/FAIL с перечнем расхождений по критичности.

---
---

## Самопроверка (Self-Review)

**1. Покрытие спецификации** (каждый документ → фаза):
- `01-domain-model` (сущности/инварианты) → Фазы 1 (схема), 4–7 (логика инвариантов: дробление 5, поставка-не-пустая 6, завершённость 6–7).
- `02-statuses` (блочная модель, переходы, активные/архив) → Фазы 4 (awaiting/cancel), 5 (status_zakup, to-support), 6 (status_postavki/sdelki), 7 (await/paid), фильтры архива во всех страничных фазах.
- `03-roles-permissions` → Фаза 3 (RBAC) + гарды во всех роутерах.
- `04-auth` → Фаза 2.
- `10–13` (страницы) → Фазы 4/5/6/7. `14` (дашборд) → 8. `15` (отчёты) → 9. `16` (карточка заявки A/Б1/Б2) → 4/5/6. `17` (карточка платежа) → 7.
- `30-db-schema` → Фаза 1. `31-api` → распределён по фазам 2–10 (ссылки в «Интерфейсах»). `32-calculations` → Фаза 6 (ядро) + 7/8/9 (сводки/дашборд/отчёты). `33-nonfunctional` → Global Constraints + Фаза 10 (бэкап/форматы) + Фаза 2 (сессии).
- `34-extensions` → **намеренно не реализуется** (MVP); схема уже содержит заделы (`upd_payment.origin='external'`, `ext_source/ext_id`) из Фазы 1 — не блокируются.
- `40-acceptance` → Фаза 10 §10.4 (сверка по чек-листу).

**Пробелы:** не найдено нереализованных требований MVP. Осознанно отложены (по `40` §4): выбор размещения (интернет/локально), кнопки-заглушки «+ Заявка» (В закупке) и «+ Отгрузка» (В сопровождении), привязка ручной УПД к процедуре, интеграции `34` (1С/вложения/уведомления).

**2. Скан плейсхолдеров:** в плане нет «TBD/потом»; для повторяющихся CRUD приведён образец-паттерн + **точные** списки полей/эндпоинтов из `31-api.md` (это спецификация, а не «аналогично задаче N»).

**3. Согласованность типов/имён:** имена полей в моделях (Фаза 1) дословно из `30-db-schema.md`; имена эндпоинтов и тел — из `31-api.md`; функции расчётов — из `32-calculations.md`. Деньги — копейки везде; даты — ISO в хранении.

**Замечание по агенту `ui-checker`:** файл `.claude/agents/ui-checker.md` **переписан под проект** (стек Vite/React + FastAPI/SQLite, URL `http://localhost:5173`, канон `Concept design/index.html`, корректные термины и сценарии блочной модели). Поэтому при диспетчеризации достаточно передать в промпте **сценарии конкретной фазы** — переопределять стек/URL/канон больше не нужно. Если `subagent_type:"ui-checker"` окажется недоступен в рантайме — те же проверки выполнять напрямую инструментами Playwright MCP (`browser_navigate/snapshot/screenshot/console_messages/network_requests/...`).

---

## Execution Handoff

План сохранён в `docs/superpowers/plans/2026-06-21-crm-ultima-implementation.md`.

Учитывая требование пользователя «**после каждого этапа останавливаться и сообщать, что проверить**», рекомендуется исполнять план **по одной фазе за раз с контрольной остановкой**. Два варианта механики:

1. **Subagent-Driven (рекомендуется)** — на каждую задачу фазы диспетчеризуется свежий субагент, между задачами — ревью; в конце фазы — блок ⏸ СТОП + 🔎 ui-checker, затем ожидание подтверждения пользователя. Суб-скилл: `superpowers:subagent-driven-development`.
2. **Inline Execution** — задачи выполняются в текущей сессии пакетами с чекпоинтами на границах фаз. Суб-скилл: `superpowers:executing-plans`.

Перед стартом реализации стоит создать изолированное рабочее пространство (`superpowers:using-git-worktrees`) и инициализировать git (репозиторий ещё не создан — `git init`).
