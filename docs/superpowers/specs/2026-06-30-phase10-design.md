# Фаза 10 — «Сквозное: поиск, история, комментарии, нефункциональное, регресс» (дизайн-спека)

- **Дата:** 2026-06-30
- **Ветка:** `feat/phase-10` (от `main` @ `3de8c1e`; main = фазы 0–9)
- **Статус:** черновик (на review пользователем)
- **Цель:** достроить сквозные механизмы и навести лоск — глобальный поиск в шапке (живой, 5 измерений), «История» (аудит) и «Комментарии» в карточках, `scripts/backup.py` + обязательный бэкап перед миграциями, проверка форматов/локали, и финальная регрессионная UI-приёмка по `docs/40-acceptance.md` §6. **Последняя фаза проекта.**
- **Источники истины:** `docs/31-api.md` §6.1 (поиск), §7 (комментарии + история), §Общее; `docs/01-domain-model.md` §2.7 (Comment); `docs/30-db-schema.md` (таблицы `comment`, `audit_log`); `docs/33-nonfunctional.md` §1/§2/§3/§5/§8/§9; `docs/40-acceptance.md` §4/§6; `docs/16-card-zayavka.md`, `docs/17-card-platezh.md`; мастер-план `docs/superpowers/plans/2026-06-21-crm-ultima-implementation.md` §Фаза 10. Визуальный канон — `Concept design/index.html` + `zakupki-crm.js/css`.
- **Предыдущая фаза:** Фаза 9 «Отчёты + экспорт» принята и FF-слита в main (`feat/phase-9`→`main` @ `3de8c1e`, 2026-06-30).

---

## 1. Контекст (состояние на старте)

Существенная часть Фазы 10 уже построена предыдущими фазами — Фаза 10 это преимущественно **достроение и проводка**, а не «с нуля»:

- **Глобальный поиск (backend) — ГОТОВ частично.** `GET /search?q=&limit=` (`backend/app/routers/search.py`) реализован, кириллица через `func.py_casefold` + `instr`, auth = `require_password_changed` (все аутентифицированные, без блочного гейта). Но отдаёт **3 группы** (`parents/procedures/suppliers`), тогда как спека §6.1/§8 обещает **5 измерений**: не хватает поиска по `Tender.num` (№ заявки) и `UpdPayment.upd` (№ УПД; плейсхолдер `CommandBar` уже упоминает «УПД»).
- **`Comment` (таблица + модель) — есть, но мёртвая.** `backend/app/models.py:328-350`, присутствует в `crm.db` (миграция `initial_schema`). Колонки: `target_kind` (CHECK ∈ `parent/tender/procedure`), `target_id` (INTEGER, **без FK** — может «висеть»), `author_id` (FK→`user`, nullable), `author`/`role` (TEXT-снимок), `text`, `created_at`. Индекс `ix_comment_target`. **Нет ни роутера, ни схем, ни использования** — ноль ссылок в коде.
- **`AuditLog` + `write_audit()` — пишется, но без чтения.** `write_audit(db, entity_kind, entity_id, user, action)` пишет ровно 4 колонки данных (`entity_kind, entity_id, user_id, action`) — **без снимков полей до/после**. Вызывается из каждого мутирующего роутера. **Read-эндпоинта нет** — «Истории» не откуда взяться. `entity_kind` — свободный TEXT (без CHECK); в данных уже есть `parent, procedure, position, upd_payment, dict, delivery`, плюс **неконсистентность**: `backend/app/routers/requests.py:743` пишет `'parent_request'`, тогда как везде иначе `'parent'`.
- **CSS комментариев — уже портирован, не используется:** `.comments, .cmt, .cmt-av(+.me), .cmt-b, .cmt-h, .cmt-r, .cmt-t, .cmt-x, .cmt-empty, .cmt-new` (`frontend/src/styles/zakupki-crm.css:217-231`).
- **FE-плейсхолдеры «появится в Фазе 10»** уже стоят: `RequestCard.tsx:482-487` (Комментарии, parent), `ProcedureCard.tsx:739-744` (Комментарии, procedure) + `:757-760` (История, procedure). В `SupportCard.tsx` и `PaymentCard.tsx` **своих плейсхолдеров нет** — разделы добавляются заново.
- **Переиспользуемое:** `frontend/src/lib/dashView.ts` (`relTime`, `targetRoute` — единый источник роутов), `lib/format.ts` (`money/dateRu/num` — соответствуют спеке), `Dashboard.tsx` `FeedPanel` (разметка `.fitem`), `api/reports.ts` (эталон типизированного клиента + blob-download), `apiFetch`, `paginate()` (`audit.py`, `page_size=50`), `app/export` (download-паттерн `reports.py`).
- **Форматы/нефункциональное — уже обеспечены сквозно:** копейки-INTEGER, ISO-даты, Europe/Moscow (`config.py`), пагинация 50, last-write-wins, деактивация-вместо-удаления. Требуют **только проверки**, а не построения.
- **`scripts/backup.py` — нет** (нет каталога `scripts/`); §3/§9 требуют ежедневный бэкап файла SQLite (хранить 14) + обязательный бэкап перед миграциями.

---

## 2. Ключевые решения (R1–R14)

**R1 — «История» = action-only, без расширения схемы.** `audit_log` хранит `{entity_kind, entity_id, user_id, action, created_at}` и **не** хранит диффов полей «было→стало». Этого достаточно для канонического «кто / что / когда» (`16-card-zayavka.md` §6, `33` §2). Фаза 10 **не** меняет схему `audit_log`, **не** меняет сигнатуру `write_audit()`, **не** требует миграции. История — это чистый read-эндпоинт поверх уже пишущихся строк. (Альтернатива — диффы до/после — отклонена: BREAKING-изменение всех call-site'ов `write_audit` + миграция + scope creep, каноном не требуется.)

**R2 — Закрыть разрыв поиска: +`tenders` и +`payments`.** Добавить в `GET /search` две группы через тот же паттерн `func.py_casefold`+`instr`: `tenders` (матч по `Tender.num` = № заявки) и `payments` (матч по `UpdPayment.upd`, NOT NULL = № УПД). Ответ становится 5-групповым: `{parents, procedures, suppliers, tenders, payments}`; `limit` применяется на группу. Формы новых групп: `tenders → [{id, num, parent_id, parent_code}]` (клик → родительская карточка по `parent_id`), `payments → [{id, upd, supplier}]` (клик → `PaymentCard` по `id` через `targetRoute`). Auth **не меняется** — `require_password_changed`. Соответствие `31` §6.1 / `33` §8 и тексту плейсхолдера.

**R3 — Комментарии: GET (лента) + POST (добавить) + DELETE (удалить).** Новый роутер `routers/comments.py`. `GET /comments?target_kind=&target_id=` — `paginate(50)`, `created_at ASC` (старые→новые, канон — новые внизу). `POST /comments` body `{target_kind, target_id, text}` — сервер заполняет `author_id/author/role` из сессии (см. R4), валидирует `target_kind ∈ {parent,tender,procedure}`, текст non-empty-after-strip + ≤2000 chars, **проверяет существование target → иначе 404**; → 201. `DELETE /comments/{id}` — гейтинг R6; hard-delete → 204. Auth на всех трёх — `require_password_changed`.

**R4 — Автор комментария = server-side снимок, никогда не клиент.** `POST` не принимает `author/author_id/role` из тела — они ставятся из `get_current_user`: `author = user.full_name`, `role = user.department` (снимок отдела, по §2.7 «role (отдел)» — напр. «Закупки»). Снимочные поля существуют умышленно (переживают деактивацию пользователя, `33` §5 «авторство и история сохраняются»). **Не рефакторить в JOIN по `user`** — это сломало бы атрибуцию после деактивации.

**R5 — Порядок и пустое состояние комментариев = по канону.** Лента: старые→новые (новые внизу), как в `zakupki-crm.js` (`addComment` → push → полный ре-рендер). Заголовок блока: `Комментарии · {count}` (count только если >0). Пусто: `.cmt-empty` «Пока нет комментариев. Будьте первым.» Плейсхолдер поля ввода — со штампом роли: «Комментарий по заявке от лица «{role}»…». Аватар текущего — `.cmt-av.me`.

**R6 — Удаление: автор своего ИЛИ Админ; hard-delete + audit.** `DELETE /comments/{id}` разрешён, если `comment.author_id == user.id` **или** `can(user, 'admin', 'view')` (Админ = единственный с блоком `admin`); иначе **403**. 404 если комментария нет. Куратор **не** расширяется до удаления чужих — комментарии глобальны (нет блока/отдела на `comment`), правило «Куратор = полный edit/delete *в своём блоке** (`03` §4) сюда не ложится. Удаление — физическое (hard-delete); факт удаления сохраняется в `audit_log` (R7).

**R7 — POST/DELETE комментариев пишут `audit_log`.** По глобальному правилу «каждый изменяющий запрос пишет запись» (`31` §Общее, `33` §2): `POST` → `write_audit(db, target_kind, target_id, user, "Добавлен комментарий")`; `DELETE` → `write_audit(db, target_kind, target_id, user, "Удалён комментарий")`. Тем самым «добавлен/удалён комментарий» виден в «Истории» того же target (параллельно с лентой комментариев — разные виды).

**R8 — `/history`: принимает любой `entity_kind`, новые→старые, paginate 50, актёр через JOIN.** `GET /history?entity_kind=&entity_id=` → `paginate(50)` над `AuditLog` по обоим фильтрам, `created_at DESC`. Актёр = `User.full_name` через LEFT JOIN по `user_id` (coalesce; `user_id` nullable → переживает деактивацию). Элементы: `{id, action, actor, created_at}`. `entity_kind` **не вайтлистится** (пропускается как есть) — данные уже содержат `dict` и пр. Auth — `require_password_changed`.

**R9 — Нормализовать баг `parent_request`→`parent`.** Поправить `requests.py:743`: писать `'parent'` вместо `'parent_request'` (consistency с остальными call-site'ами). Предварительно убедиться, что ни один потребитель не читает `'parent_request'` (read-эндпоинта до Фазы 10 не было — некому). Без этого «История» родительской карточки теряла бы часть событий.

**R10 — UX поиска: живой дебаунс-дропдаун.** `CommandBar` input → controlled, debounce ≈300 мс, ≥2 символа → `useQuery(['search', q], getSearch, {enabled})` → сгруппированный дропдаун (5 групп) → клик `useNavigate(targetRoute(item))`, где `targetRoute` — из `lib/dashView.ts` (единый источник роутов, не хардкод). Закрытие по select / Escape / click-outside. Бэкенд уже умеет и live (`q`), и по Enter — выбираем live-дропдаун («единое окно», кросс-блочная навигация).

**R11 — Проводка карточек по канону.** `RequestCard` (Режим А, parent): `CommentFeed targetKind="parent"` (истории на родителе нет по канону). `ProcedureCard` (Б1, zakupka): `CommentFeed targetKind="procedure"` + `HistoryFeed entityKind="procedure"` (замена стабов). `SupportCard` (Б2, soprovozhdenie — та же процедура): `CommentFeed` + `HistoryFeed` на том же `proc.id` (добавить заново; канон Б2 требует оба — комментарии/история консистентны между видами закупки и сопровождения одной процедуры). `PaymentCard` (upd_payment): `HistoryFeed entityKind="upd_payment"` (добавить заново; `17` §2/§5 — на карточке платежа есть «История», комментариев нет).

**R12 — Разметка «История» — переиспользуем `.fitem` + `relTime`.** Канон не задаёт layout «Истории» (в концепте только кнопка-«призрак»). Используем компактную строку как в дашборд-ленте (`Dashboard.tsx:143-160`): `<div class="fitem"><span class="ft2">{relTime}</span><div><b>{actor}</b> <span>{action}</span></div></div>`, новые→старые. Пусто: «Журнал действий пуст.» Это осознанное решение Фазы 10 (последовательность с лентой дашборда).

**R13 — Бэкап: `scripts/backup.py` + Alembic pre-migration hook, без планировщика в приложении.** Импортируемая `run_backup(db_path, backup_dir, keep=14)` живёт в **`backend/app/backup.py`** (чтобы `migrations/env.py` мог сделать `from app.backup import run_backup`) — через **online-backup `sqlite3`** (`conn.backup()`): консистентный снимок при активных писателях, **не** raw-копия файла (риск повреждения). Имя `crm_YYYYMMDD_HHMMSS.db`, ротация до 14 новых. `DB_PATH` из `app.config`, каталог по умолчанию `backend/backups/` (gitignore). **`scripts/backup.py`** (по мастер-плану) — тонкий CLI-враппер над `app.backup.run_backup`: `python scripts/backup.py [--db --backup-dir --keep]`. Pre-migration hook: `migrations/env.py` вызывает `run_backup()` перед `run_migrations()` в online-режиме (срабатывает на реальных upgrade/downgrade; autogenerate — нет). Ночной запуск — забота ops (cron/Task Scheduler), в приложение планировщик **не** кладём (≤20 пользователей).

**R14 — Форматы проверяем, не перестраиваем; миграций нет.** `lib/format.ts` уже соответствует спеке — расширяем `format.test.ts` точными литералами (`1 234 567 ₽`, `ДД.ММ.ГГ`, дробные через запятую). Таблицы `comment`/`audit_log` уже в `crm.db` + `initial_schema` → **миграций в Фазе 10 нет**. ⚠️ Если миграция всё же понадобится позже — §3 pre-migration бэкап (R13) сработает автоматически.

---

## 3. Архитектура и файлы

### Backend
| Файл | Действие |
|---|---|
| `backend/app/routers/search.py` | **±**: добавить группы `tenders` (`Tender.num`) и `payments` (`UpdPayment.upd`) через `func.py_casefold`+`instr`; ответ 5 групп |
| `backend/app/routers/comments.py` | **новый**: `APIRouter(prefix="/comments")`; `GET` (list, paginate 50, asc) + `POST` (create, server-side author) + `DELETE /{id}` (author\|Админ); `require_password_changed`; `write_audit` на POST/DELETE |
| `backend/app/routers/history.py` | **новый**: `APIRouter(prefix="/history")`; `GET ?entity_kind=&entity_id=` (paginate 50, desc, LEFT JOIN user→actor); `require_password_changed` |
| `backend/app/schemas/comments.py` | **новый**: `CommentOut` (`id, target_kind, target_id, author_id, author, role, text, created_at`), `CommentCreate` (`target_kind, target_id, text`), `CommentList` (`items, total`) |
| `backend/app/schemas/history.py` | **новый**: `AuditEntryOut` (`id, action, actor, created_at`), `HistoryList` (`items, total`) |
| `backend/app/main.py` | подключить роутеры `comments`, `history` |
| `backend/app/routers/requests.py` | **fix** @743: `'parent_request'` → `'parent'` |
| `backend/app/backup.py` | **новый**: `run_backup(db_path, backup_dir, keep=14)` (sqlite3 online backup, ротация) — импортируется из `env.py` |
| `backend/migrations/env.py` | **+**: `from app.backup import run_backup` → вызов перед `run_migrations()` (online) |
| `scripts/backup.py` | **новый** (CLI по мастер-плану): тонкий враппер над `app.backup.run_backup` + `__main__` |
| `backend/tests/test_search.py` | **±**: +tenders, +payments, кириллица (pytest) |
| `backend/tests/test_comments.py` | **новый**: create (author/role server-side, 422 bad kind/empty text, 404 no target), list (filter/asc/paginate), delete (author 204, non-author 403, admin 204, 404), audit on POST/DELETE |
| `backend/tests/test_history.py` | **новый**: filter by kind+id, desc, actor via JOIN, paginate, произвольный `entity_kind` (incl `dict`), normalized `parent` |
| `backend/tests/test_backup.py` | **новый**: снимок создаётся, ротация до 14, консистентность online-backup |

### Frontend
| Файл | Действие |
|---|---|
| `frontend/src/api/search.ts` | **новый**: `SearchResult` (+`tenders`, `payments`), `getSearch(q, limit?)` |
| `frontend/src/api/comments.ts` | **новый**: `Comment`, `listComments(kind,id,page?)`, `createComment({kind,id,text})`, `deleteComment(id)` |
| `frontend/src/api/history.ts` | **новый**: `AuditEntry`, `listHistory(kind,id,page?)` |
| `frontend/src/components/CommandBar.tsx` | **±**: controlled input, debounce ≈300 мс/≥2 симв, `useQuery(['search',q])`, дропдаун 5 групп, `useNavigate(targetRoute(...))`, close on select/Esc/outside |
| `frontend/src/components/CommentFeed.tsx` | **новый**: props `targetKind targetId`; `useQuery(['comments',k,i])`; `.cmt*` разметка (asc, `.cmt-empty`, role-stamped input); create `useMutation`→invalidate; delete (author\|Админ) + confirm |
| `frontend/src/components/HistoryFeed.tsx` | **новый**: props `entityKind entityId`; `useQuery(['history',k,i])`; `.fitem` + `relTime`, desc, empty «Журнал действий пуст.» |
| `frontend/src/cards/RequestCard.tsx` | заменить стаб `:484-487` → `<CommentFeed targetKind="parent" targetId={req.id} />` |
| `frontend/src/cards/ProcedureCard.tsx` | заменить стабы `:741-744` → `CommentFeed(procedure)`, `:760` → `HistoryFeed(procedure)` |
| `frontend/src/cards/SupportCard.tsx` | **+** `CommentFeed(procedure)` + `HistoryFeed(procedure)` (тот же `proc.id`) |
| `frontend/src/cards/PaymentCard.tsx` | **+** `HistoryFeed(upd_payment)` |
| `frontend/src/lib/format.test.ts` | **±**: точные литералы (`1 234 567 ₽`, `ДД.ММ.ГГ`, дробные запятая) |
| `frontend/src/components/{CommentFeed,HistoryFeed}.test.tsx`, `CommandBar.test.tsx` | **новые** (colocated, vitest) |

**Без миграций БД.** **Без нового CSS** (классы комментариев уже портированы; «История» переиспользует `.fitem`). **Без новых блоков прав** (поиск/комментарии/история — глобальные, как поиск).

---

## 4. Контракты API (сводка)

| Метод | Путь | Auth | Назначение |
|---|---|---|---|
| GET | `/search?q=&limit=` | `require_password_changed` | 5 групп: `parents/procedures/suppliers/tenders/payments` |
| GET | `/comments?target_kind=&target_id=&page=&page_size=` | `require_password_changed` | лента, asc, paginate 50, `{items,total}` |
| POST | `/comments` | `require_password_changed` | body `{target_kind,target_id,text}`; автор server-side; 201; audit |
| DELETE | `/comments/{id}` | автор **или** Админ | hard-delete; 204; 403/404; audit |
| GET | `/history?entity_kind=&entity_id=&page=&page_size=` | `require_password_changed` | desc, paginate 50, `{items,total}`; actor=full_name |

**Коды ошибок** (`31` §Общее): 401 не авторизован · 403 нет прав / must_change_password · 404 не найдено · 422 валидация. **Пагинация** — `?page=&page_size=` (по умолчанию 50), ответ включает `total`. **Деньги/даты** — копейки/ISO на проводе (в Фазе 10 новых денежных полей нет).

---

## 5. Тестирование (TDD)

- **Backend (pytest, in-memory SQLite через `create_all`):** `conftest.py` уже регистрирует `py_casefold` на тестовом соединении — проверить, что новые тесты поиска его получают. Красный → реализация → зелёный → коммит (как в фазах 7–9).
- **Frontend (vitest):** клиенты (mock `apiFetch`), `CommentFeed` (рендер ленты/пусто, create→invalidate, видимость удаления по автору/Админ), `HistoryFeed` (строки/пусто), `CommandBar` (debounce/min-length/дропдаун/навигация), `format` (литералы).
- **Regression-гейт (10.4):** полный `pytest` + `vitest` + `tsc -b` + `vite build` + **ui-checker** (все ключевые экраны @1280/1440 против `Concept design/index.html`) + чек-лист `40-acceptance.md` §6 (8 пунктов). Бэкап `crm.db` перед любой миграцией.

---

## 6. Риски и гочты

1. **Кириллица в поиске** — только `func.py_casefold(...)` (встроенный `lower()` ASCII-only, ломает кириллицу/ё). `tests/conftest.py` должен регистрировать `py_casefold` на in-memory тестовом соединении.
2. **`audit_log` без диффов** — «История» покажет только {кто, что, когда}, никогда «сумма: X→Y». Ожидание зафиксировано (R1).
3. **`apply_archive_filter` — ParentRequest-специфичный** (хардкод `status=='awaiting'`) — **не** переиспользовать для comments/history; только `paginate()`.
4. **`comment.target_id` без FK** — POST валидирует существование target (404); деактивация-вместо-удаления (`33` §5) гарантирует, что target'ы не удаляются → комментарии не «висят» при обычной работе.
5. **`entity_kind` свободный TEXT** — `/history` не вайтлистит; нормализация `parent_request`→`parent` (R9) устраняет известный разрыв.
6. **React-гочты (память `crm-frontend-patterns`)** — `useMutation` `onSuccess` → `qc.invalidateQueries(...)` (НЕ await-refetch-then-reset); StrictMode; `?? true` дефолты; cross-key cache desync (при отладке предпочитать клиентскую навигацию, а не Playwright `goto`).
7. **Целостность снимка автора комментария** — `author_id/author/role` денормализованы умышленно; не сводить к JOIN по `user`.
8. **Бэкап** — online-backup `sqlite3`, не raw-копия файла (конкурентные писатели → повреждение).
9. **1С / вложения / уведомления — НЕ Фаза 10** (`40` §4, `34`); `upd_payment.origin='external'` и `ext_source/ext_id` — заделы, не реализуются.

---

## 7. Scope-границы (что НЕ в Фазе 10)

- Диффы полей «было→стало» в аудите (R1 — отклонено).
- Расширение `target_kind` комментариев на `delivery`/`upd_payment` (CHECK = `parent/tender/procedure`; канон §2.7).
- Отдельная страница «История» аудита (мастер-план — только блоки в карточках).
- Правка комментария (только создание + удаление, R3/R6).
- Внутри-прикладной планировщик бэкапов (R13 — ops/cron).
- 1С, вложения-файлы, уведомления (`40` §4).

---

## 8. План выполнения (10.1 → 10.4, горизонтально, как фазы 7–9)

- **10.1 Backend** (TDD, ⏸ после): `/search` +2 группы (R2) + fix `parent_request` (R9); роутер `comments` GET/POST/DELETE (R3–R7); роутер `history` GET (R8). Тесты: `test_search` ±, `test_comments`, `test_history`. → `pytest` зелёный.
- **10.2 Frontend** (TDD, ⏸ после): `api/{search,comments,history}.ts`; `CommandBar` дропдаун (R10); `CommentFeed` + `HistoryFeed` (R5/R12); проводка 4 карточек (R11). → `vitest` + `tsc` + `build`; `ui-checker`.
- **10.3 Нефункциональное** (⏸ после): `scripts/backup.py` + Alembic hook (R13); `test_backup`; `format.test.ts` (R14).
- **10.4 Финальная регрессия**: весь набор зелёный + `ui-checker` полный проход + `40-acceptance.md` §6 (8 пунктов); бэкап перед миграцией; **merge-гейт в main — завершение проекта**.

Каждая задача — цикл TDD; конец фазы — **⏸ СТОП — ПРОВЕРКА** (команды + ожидаемый вывод + что проверяет человек), исполнитель останавливается и ждёт подтверждения.
