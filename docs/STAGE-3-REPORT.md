# Stage 3 — отчёт об основе CRM

Дата: 24.10.2026. Ветка `feature/stage-3-crm-data-model`, базовый main `977170a` (Stage 2.2 уже слит PR #3). Коммиты: `8124eeb` — кодировка тестового PDO; `1a664c4` — модель, обратимая версия 004, CLI, документация и тесты. Данный отчёт добавлен отдельным коммитом. Main не изменён, история не переписывалась.

## Результат

Реализованы 12 пустых новых таблиц для всех запрошенных сущностей и связей; существующий nd_leads остаётся источником лидов. Клиенты отделены от учётных записей; сделки/заказы/проекты имеют обязательного клиента и необязательный источник; задачи могут быть внутренними или относиться к проекту/этапу; команда — M:N. История имеет FK actor/context, в том числе на прежнего владельца. Составные FK запрещают заказ/сделку/проект чужого клиента и этап чужого проекта. Индексы, уникальность, архивирование, статусы, версии и UTC документированы.

**Старые таблицы, их определения и данные не изменяются миграцией.** Нет backfill, автоматического объединения лидов, создания сотрудников/клиентов, регистрации, нового API/интерфейса, новых сессий или перезаписи пароля. Настоящий config.php/политика/ключи не добавлены. Сбор реальных персональных данных не включался.

[Полная архитектура, ER-диаграмма и lifecycle](CRM-ARCHITECTURE.md).

## Файлы

- database/migrations/004_crm_foundation/up.sql — добавочные таблицы, FK, ENUM, уникальные и составные индексы.
- database/migrations/004_crm_foundation/down.sql — обратный порядок удаления; **не выполнять напрямую**.
- scripts/migrate.php — CLI-only оператор версии 004, status/up/down, baseline и strict/InnoDB preflight, SHA256, журнал nd_schema_migrations, advisory lock и запрет работы старой версии при более поздней миграции.
- tests/test_crm_migrations.py — 10 migration-сценариев.
- tests/test_prelaunch_foundation.py — все 14 прежних сценариев после up 004.
- tests/test_prelaunch.py — единственное изменение существующего helper: явный charset=utf8mb4.
- docs/CRM-ARCHITECTURE.md, README.md и данный отчёт — устройство, ограничения, запуск/восстановление.

Базовый database/schema.sql и 001–003 сохранены. На чистой БД сначала используется базовая схема; 001–003 повторно к ней не применяются. Для Stage 3 после baseline нужен отдельный up 004. Версия 004 не включается в веб-setup и workflow автоматически.

## Обратимость и безопасность

Down разрешён лишь если **все** новые таблицы пусты. Непустая история также запрещает откат. Write locks на новые таблицы закрывают интервал между проверкой и DROP; родители nd_admin/nd_leads временно read-locked. Force-режима нет. Старые лиды, пароль, сессии и лимиты не удаляются. Журнал остаётся инфраструктурой, запись 004 удаляется.

DDL MySQL 5.7 имеет implicit commits: при ошибке остаются частичные изменения. Оператор сохраняет applying/rolling_back и контрольные суммы, не выполняет слепой повтор up. Пустое частичное состояние может откатить тот же оператор/версия; непустое требует отдельного плана восстановления. Сырые PDO/config-исключения и SQL не печатаются; HTTP-запуск CLI возвращает 404. Права/maintenance window и backup/restore описаны в архитектуре. Любое production-применение требует отдельного разрешения.

Важное разграничение: ENUM/FK/UNIQUE исполняет БД. Граф переходов, даты, валюты, ровно один actor и согласованность нескольких контекстов истории, активный аккаунт с проверенным способом входа, роли/разрешения и append-only доступ истории — контракт будущих сервисов, **не уже работающие функции**. Прямой DBA-доступ не ограничен будущей бизнес-логикой. Клиентские аккаунты как таблица ещё не являются доступным клиентским кабинетом.

## Выполненные проверки

| Проверка | Среда | Итог |
|---|---|---|
| 004 up/down/reapply, коллизии, checksum, partial DDL/recovery, прерванный down, locks, поздняя версия, FK/UNIQUE/ENUM/unsigned, сохранность старых строк, прежний API после up | MySQL **5.7.42** | 10 PASS |
| Те же migration-тесты | MariaDB **11.8.6** | 10 PASS |
| Полный прежний suite, включая 001–003 на legacy fixture, PHP/API/Chromium | MySQL 5.7.42, baseline | 14 PASS |
| Полный прежний suite **после up 004** | MySQL 5.7.42 | 14 PASS |
| API-client unit | Node | 12 PASS |
| Workflow safety | Локальные SSH/rsync заглушки | 6 PASS |
| Защита Apache | Apache 2.4.69 | 2 PASS |
| PHP syntax | PHP 8.4.27 | 10 файлов PASS |
| JS syntax | Node | 3 файла PASS |
| actionlint 1.7.7 без ShellCheck/Pyflakes; bash -n в safety-suite; git diff --check | Локально | PASS |

Итого финальная матрица: **68 тестовых запусков PASS, 0 FAIL** (одни сценарии миграции повторяются на двух СУБД; прежние сценарии повторены до/после миграции). Новые migration-тесты используют полные снимки старого admin/lead с кириллицей, а не только количество строк.

В ходе проверки были исправлены два найденных препятствия: восстановительный DROP отсутствующей таблицы под LOCK TABLES в MySQL 5.7; отсутствие charset в прежнем тестовом helper (давал '?' при чтении кириллицы на MySQL с latin1 соединением, тогда как PDO приложения уже задавал utf8mb4). Первые прогоны имели ошибки; перечисленные итоговые результаты получены после исправлений реальным повторным запуском. Никакой перекодировки production-данных не выполнялось.

Изолированные runtime установлены только в /tmp, MySQL слушает loopback. Каждый suite создавал/удалял только случайную neuro_test_* БД и временную копию с синтетическим config/политикой. **MySQL 5.7.27 SpaceWeb непосредственно не проверен**: выполнена реальная проверка ветки 5.7 на 5.7.42, синтаксис использует возможности 5.7. Production/SSH не подключались.

Команды (dev-модули requests/Playwright через PYTHONPATH=/tmp/neuro-runtime/python, PHP_BIN=/tmp/neuro-runtime/php):

```sh
NEURO_TEST_DSN='mysql:host=127.0.0.1;port=33078'  python -m unittest discover -s tests -p test_crm_migrations.py -v
NEURO_TEST_DSN='mysql:host=127.0.0.1;port=33077'  python -m unittest discover -s tests -p test_crm_migrations.py -v
NEURO_TEST_DSN='mysql:host=127.0.0.1;port=33078'  python -m unittest discover -s tests -p test_prelaunch.py -v
NEURO_TEST_DSN='mysql:host=127.0.0.1;port=33078'  python -m unittest discover -s tests -p test_prelaunch_foundation.py -v
```

## GitHub, одобрение и выпуск

Ветка опубликована. gh pr create (base=main, head=feature/stage-3-crm-data-model) вернул GraphQL Forbidden, exit 1. **PR этой попыткой не создан.** Actions API также Forbidden: GitHub CI UNVERIFIED. Успех локальной матрицы не объявляется успехом GitHub Actions. Workflow не изменён и не запускался, авто-публикация остаётся отключённой в исходниках.

[Создать подготовленный PR с заполненными полями](https://github.com/2006minden-gif/-Chat-GPT-/compare/main...feature/stage-3-crm-data-model?expand=1&title=Stage+3%3A+CRM+data+model+and+reversible+MySQL+5.7+migration&body=CRM+data+foundation+only%3B+no+customer-facing+features.%0A%0AArchitecture%3A+https%3A%2F%2Fgithub.com%2F2006minden-gif%2F-Chat-GPT-%2Fblob%2Ffeature%2Fstage-3-crm-data-model%2Fdocs%2FCRM-ARCHITECTURE.md%0AReport%3A+https%3A%2F%2Fgithub.com%2F2006minden-gif%2F-Chat-GPT-%2Fblob%2Ffeature%2Fstage-3-crm-data-model%2Fdocs%2FSTAGE-3-REPORT.md%0A%0A68+local+checks+passed+across+the+documented+matrix.+Do+not+merge%2C+migrate+production+or+deploy+without+approval.)

Осталось открыть ссылку, проверить base=main и ветку Stage 3, нажать Create pull request (либо открыть существующий, если GitHub предложит). Слияние/auto-merge/применение SQL не выполнялись. Требуется одобрить модель и ограничения lifecycle, затем отдельно интеграцию и production-миграцию с backup/restore и проверкой прав. Новые database/scripts/docs должны находиться вне public_html; существующий rsync не доставляет их автоматически. ZIP/упаковщик не менялись; старые архивы не содержат CLI/документацию Stage 3 и не являются готовым пакетом этого этапа.

До новых интерфейсов обязательны серверные RBAC/object ownership/CSRF/сессии/проверки переходов и юридическое разрешение сбора данных. Это следующий отдельный этап, он не начат. Никакие записи/схемы/файлы SpaceWeb не менялись. Работа остановлена для review.

STAGE 3 COMPLETE — AWAITING APPROVAL.
