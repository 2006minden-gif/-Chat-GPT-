# Stage 4 — отчёт реализации

## Результат

Клиентская регистрация (self/invitation), проверка email, отдельный вход/выход, восстановление пароля, управление состоянием аккаунта владельцем, fail-closed privacy gate реализованы в отдельной зависимой ветке `feature/stage-4-customer-auth`.

Основа: Stage 3 `968c82d` + merge существующего main `22ff5d7` с интегрированным CI/CD. Миграция 004, её SQL и runner не изменялись. Подробная модель, API, ограничения и release prerequisites: [CUSTOMER-AUTH.md](CUSTOMER-AUTH.md).

## Файлы

Новые:

- database/migrations/005_customer_auth/up.sql, down.sql — пять additive таблиц, безопасный empty-only down.
- scripts/migrate-customer.php — отдельная versioned CLI-операция 005, общая блокировка с 004, dependency/checksum/partial-DDL guards.
- private/customer-auth.php, customer-mail.php — API business logic, sessions/tokens/consent, SMTP.
- public/customer.php, customer-api.php, customer.js, customer.css — responsive интерфейсы клиента и API.
- public/customer-owner.js — owner invitation/lifecycle UI.
- tests/test_customer_auth.py, test_customer_migrations.py — HTTP/SMTP/MySQL/browser/concurrency regressions.
- docs/CUSTOMER-AUTH.md, STAGE-4-REPORT.md.

Изменены:

- private/config.example.php — выключенные customer/privacy flags, пустой SMTP template.
- public/index.html — ссылка на клиентский кабинет, без редизайна.
- public/crm.html, crm.js — отдельный owner-only раздел, события login/logout, сохранены CRM routes/contracts.
- scripts/deploy/policy.json, release.py, remote.php, health.py — расширена существующая allowlist, приватная доставка SQL/005 runner, порядок 004→005, health hashes новых assets. Автоприменение обеих миграций в policy выключено.
- scripts/package.py — совместимость существующего вспомогательного packager с private dependencies; архив не создавался и не загружался.
- tests/router.php, test_release_pipeline.py — изолированные маршруты и реальная backup/restore проверка обеих миграций.

.github/workflows не изменены относительно синхронизированного main. Конкурирующей доставки, production SQL или нового внешнего runtime framework нет.

## Выполненные проверки

- Полный `unittest discover -s tests -p 'test_*.py'`: **127 PASS**, 0 FAIL, 0 SKIP, 75.691 секунд.
- Node API-client: **12 PASS**.
- PHP syntax: **16 файлов PASS**, PHP **8.4.27**.
- JavaScript syntax: **5 файлов PASS**.
- Изолированный настоящий **MySQL 5.7.42**, mysqldump 5.7; Apache 2.4.69 и Chromium/Playwright. Не подменяется заявлением о проверке точного production patch 5.7.27.
- actionlint 1.7.7, release policy validation, git diff --check: PASS.
- Gitleaks working tree redacted scan: 0 находок.

127 включают 32 новых customer auth теста, 6 migration 005 тестов и новый full-agent 004+005 backup/restore тест, а также весь прежний набор (88).

Проверены normal/invalid/duplicate/weak-password, email verification/expiry/reuse, invite/expiry/reuse, reset/expiry/reissue, CSRF/origin, rate limits, session rotation/expiry/logout, независимость CRM cookie, disable/re-enable/version conflict, archived customer, повтор согласия при изменении политики, закрытые feature/privacy flags, отсутствующая/partial migration, одновременное consume одного токена двумя отдельными PHP/PDO процессами (ровно один успех), безопасные ответы при ошибке БД, SMTP failure/retry/resend и отсутствие токенов/паролей в PHP access logs.

Браузер: мобильная регистрация→письмо тестового SMTP→подтверждение→вход→выход, отсутствие horizontal overflow, owner invitation UI и очистка клиентского списка при logout, сохранение ввода при HTML вместо API JSON. CSP не ослаблен: тестовые ожидания переделаны на function predicates вместо eval строк. Промежуточная ошибка PHP quoting при добавлении mail-status устранена; финальный полный набор и syntax checks прошли после исправления.

Миграции проверены на сохранение старых records, FK, checksums, общий advisory lock, отказ 005 без applied 004, partial-DDL state, отказ down с любыми auth records. Deployment agent реально создал backup, применил 004 затем 005 в случайной локальной БД, восстановил backup в другую случайную БД и выполнил только файловый rollback, не притворяясь, что DDL отменён.

## Ограничения и выпуск

Не выполнялись production/staging SMTP TLS acceptance и live customer login; реальный email провайдер не настроен. Test SMTP хранит письма только в памяти и не отправляет их клиентам. Синхронный transport имеет две попытки, затем повтор через безопасный resend; delivery в Inbox не гарантируется SMTP acceptance.

Сотруднического login/RBAC в исходной модели нет. Приглашения и lifecycle доступны существующему владельцу, а не произвольному employee_id. Подключение роли manager требует отдельной employee authentication stage. Старые Stage 3 аккаунты без auth metadata не присваиваются автоматически новому заявителю.

Нужны интеграция #4 до Stage 4, независимый review, verified production pipeline/recovery, отдельное одобрение миграционной checksum-политики, настройка SMTP вне Git и юридическое утверждение документов для аккаунтов/приглашений и retention. Не включать customer_auth_enabled/customer_auth_privacy_approved до этого.

Ветка подготовлена для отдельного draft PR; фактическая ссылка/Actions status сообщаются по результату GitHub, локальные тесты не выдаются за hosted CI. Stage 4 не сливался, main не изменялся, production flags/credentials/данные не менялись, миграции production не запускались.

STAGE 4 COMPLETE — AWAITING REVIEW.
