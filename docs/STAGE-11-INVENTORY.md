# Stage 11 — инвентаризация

Проверено 25.10.2026 по исходникам, Git ancestry и доступной выгрузке GitHub metadata. Отсутствие доступа к production — не подтверждение её состояния. Используемые статусы: IMPLEMENTED / PARTIALLY_IMPLEMENTED / MISSING / BLOCKED (наличие), VERIFIED / NOT_VERIFIED (проверка). VERIFIED относится только к указанному изолированному тесту.

## Цепочка

`main 478ca7f` → CRM foundation 004 → customer auth 005 → operations 006 → collaboration 007 → billing 008 → AI 009 + pricing 010 → production 011 → интеграционная ветка `integrate/stage-11-system`.

Stage 9 MISSING; это блокирует полный каталог → brief → принятое предложение → production. Не заменяется mock-модулем. Тестовый adapter Stage 10 остаётся только loopback fixture. Ручная передача Stage 11 — отдельная процедура по принятому ТЗ и существующей задаче, без коммерческих действий или заявления о готовности Stage 9.

| Stage | Исходная ветка / SHA | PR | Реализация | В main | Миграции | Проверка |
|---|---|---|---|---|---|---|
| 1–2 | main / 478ca7f | ранние интеграции | IMPLEMENTED | да | 001–003 + schema.sql | VERIFIED локальные HTTP/browser; production NOT_VERIFIED |
| 3 | feature/stage-3-crm-data-model / 968c82d | #4 | IMPLEMENTED | нет | 004 | VERIFIED MySQL fixtures |
| 4 | feature/stage-4-customer-auth / 92f2b22 | #7 | IMPLEMENTED | нет | 005 | VERIFIED test transport; live SMTP NOT_VERIFIED |
| 5 | feature/stage-5-crm-operations / a6a7b8c | draft #21 | IMPLEMENTED | нет | 006 | VERIFIED изолированные CRM API/browser |
| 6 | feature/stage-6-client-collaboration / d9ad539 | draft #22 | IMPLEMENTED | нет | 007 | VERIFIED files/documents/messages/approvals |
| 7 | feature/stage-7-billing-notifications / f7c2630 | API создание ранее BLOCKED | PARTIALLY_IMPLEMENTED | нет | 008 | VERIFIED mock payments/test notifications; live NOT_VERIFIED |
| 8 | feature/stage-8-ai-automation / 6e6dd62 | API создание ранее BLOCKED | PARTIALLY_IMPLEMENTED | нет | 009–010 | VERIFIED mock orchestration/pricing; live provider NOT_VERIFIED |
| 9 | не найден | не подтверждён | MISSING | нет | нет | NOT_VERIFIED |
| 10 | feature/stage-10-ai-production / 51412fd | API создание BLOCKED | PARTIALLY_IMPLEMENTED | нет | 011 | VERIFIED draft/mock/static QA; sandbox/runtime NOT_VERIFIED |

Все перечисленные feature SHA являются предками Stage 11. Повторный merge/cherry-pick не нужен: он не добавит отсутствующий Stage 9. Совместимый код уже находится в одной цепочке. main не переписывался. Новых конфликтующих API или параллельной финансовой модели не добавляем. Миграции 001–011 не изменяем.

## Функциональные границы

- `public/index.html`, `script.js`, `api-client.js`: агентский лендинг, раздел услуг, контактная форма, Telegram. Каталог/интерактивные brief/checkout отсутствуют. Форма fail-closed до одобрения privacy. Контакт не превращается автоматически в verified customer account.
- `public/studio.php`, `private/app.php`: владелец, sessions, CSRF, rate limits, версии лидов, идемпотентность. CRM owner-only, роли сотрудников не включаются Stage 11.
- `public/customer.php`, `customer-api.php`, `private/customer-auth.php`: саморегистрация/приглашения, подтверждение email/reset/session/consent. Для production нужны законные документы и одобренный email transport. Тестовые email spool/transport не SMTP.
- `public/workspace.php`, `private/crm/{routes,read,write,core}.php`: клиенты, сделки, конверсия, заказы, проекты, этапы/задачи, история/уведомления; операции scoped, optimistic versions. Foundation employee tables существуют исторически; Stage 11 не вводит employee auth/дашборды.
- `public/collaboration.php`, `collab-download.php`, `private/collab/`: project scoped messages/files/documents/versions/customer approvals. Private storage вне public. Production storage/permissions/quotas NOT_VERIFIED.
- `public/billing.php`, `private/billing/`: invoices/payments/refunds/notifications с test adapter. Live merchant/payment/SMTP не утверждены, не включались. Нет приёма реквизитов карты приложением.
- `public/ai.php`, `private/ai/`: роли/контракты/budgets/tasks/approvals/mock HTTP provider. Ни Codex API, ни настоящий tool executor не подключён. `private/pricing/`: decimal-safe deterministic цены, реестр ставок, approvals/immutable quotations. Неизвестная стоимость требует review.
- `public/production.php`, `private/production/`: approved plans/DAG/artifacts/static QA/revisions/private JSON delivery/expenses. Stage9 evidence live BLOCKED, sandbox отсутствует, runtime NOT_TESTED, worker schedule NOT_VERIFIED, concurrency 1. Нельзя считать готовым автономным созданием приложения.

## Покрытие и обязательные зависимости

`tests/test_prelaunch*`, `test_customer_auth`, `test_*migrations`, `test_crm_operations`, `test_collaboration`, `test_billing`, `test_ai`, `test_pricing`, `test_production`, Apache security и release safety. На входном Stage10 SHA выполнено 266 Python и 12 Node тестов; GitHub run 40175766927 success. Это доказательство на том SHA, не результат будущих Stage11 изменений. Итоговые проверки Stage11 — в STAGE-11-REPORT.md.

Требования PHP: PDO + pdo_mysql, mbstring, fileinfo, JSON, hash, openssl; ZipArchive для существующей проверки ZIP, curl/сетевой транспорт согласно используемому адаптеру; PHP CLI для явных migrations/workers. Apache 2.4 AllowOverride/security rules, private sibling access, HTTPS/secure cookies и private email/file storage нужно проверить отдельно при одобренном выпуске. Лимит диска учитывается существующими квотами, фактический остаток hosting NOT_VERIFIED.

Активация в production отдельная: approvals зависимых PR, backup/restore, последовательность migrations, deployment allowlist новых файлов, flags, privacy/legal, SMTP/payment/provider при необходимости. Никакие новые API-ключи не требуются для ручной передачи или локальных тестов. Блокеры полной готовности: Stage 9, live dependencies, retention/legal decisions, реальный release package и hosting acceptance.
