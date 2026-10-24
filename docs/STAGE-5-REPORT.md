# Stage 5 — отчёт разработки

## Состояние и зависимости

Отдельная ветка: `feature/stage-5-crm-operations`. Исходный main bcb5797; Stage 3 968c82d / PR #4, Stage 4 92f2b22 / PR #7 включены только в dev dependency chain. Их интеграция/публикация не разрешена автоматически. Ни workflows, ни production deploy implementation не менялись. Main и production не изменялись.

## Реализовано

- Закрытая owner CRM с русской навигацией, dashboard по реальным SQL, KPI links, recent leads/projects/deadlines/activity, refresh без фиктивных записей.
- Клиенты: contact validation, поиск/тип/статус/архив, create/edit, explicit lead link с запретом чужого reassignment, related leads/deals/orders/projects/history.
- Сделки: Kanban и формы, реальные ENUM/transitions, decimal-safe RUB, optimistic conflict, явное confirm-convert won → один order, atomic idempotency.
- Заказы: самостоятельное создание, состояния/срок/заметки, related projects, создание проекта с выбранным заказом. Совпадение контактов/названий не объединяет данные.
- Проекты: order/customer checks, stages, deterministic progress, назначение действующих сотрудников, команда, reorder, tasks/history, archive. У milestones нет автоматических шаблонов, способных затереть пользовательские этапы.
- Задачи: list/board, приоритет, даты, assignment, project/stage checks, status/completion; справочник сотрудников с suspend/archive/restore. Employee login/RBAC не придуман.
- Owner notifications от записанных событий + deduplicated bounded deadline/lead sync, read/all read; activity с actor/object/action/time без payload/secrets.
- Customer portal: настоящий Stage 4 login, только собственные orders/projects и явный allowlist безопасных полей, milestones/progress. Чужой ID 404, owner API по customer cookie 401, disabled account закрывает доступ.
- Responsive локальные CSS/JS, global CRM search, формы/диалоги, server validation, CSRF/origin, pagination, stale update 409, retry receipts, HTML-response rejection и draft preservation. Старые публичный сайт и CRM сохранены.

## Файлы

Новый backend: private/crm/{core,read,write,routes,portal}.php. Новые UI: public/workspace.php, operations.js/css, portal.php/js. Точки интеграции: public/api.php, studio.php, customer.php; private/customer-auth.php и config.example.php (только false default). Новая schema: database/migrations/006_crm_operations/up.sql и down.sql, explicit scripts/migrate-crm.php. Development packager включает новые services/CLI. Тесты: tests/test_crm_operations.py, test_crm_operations_migrations.py, router allowlist. Документация: этот отчёт, STAGE-5-ARCHITECTURE.md, STAGE-5-UX.md и снимки synthetic fixtures. Также ветка содержит исходные Stage 3/4 файлы, перечисленные в их собственных отчётах.

## Проверено

Полный Python suite: 186 PASS, 0 FAIL/0 SKIP (изолированные PHP 8.4.27, MySQL 5.7.42, Apache/Chromium). Новый operations suite — 12 тестов с несколькими lifecycle/security/browser assertions. Node — 12 PASS. PHP syntax — 25 файлов PASS; JS syntax, compileall, actionlint, release policy, diff --check — PASS. Финальный hosted CI/run IDs фиксируются в GitHub отдельно; локальный PASS не подменяет hosted CI или production delivery.

Проверены старые lead/admin/session behavior, Stage 3/4 migration/auth tests, customer lifecycle без потери unrelated leads, sales transitions без авто-заказа, повтор conversion с тем же/новым ключом, exact decimal amount, project/stage/task/employee relationships, stale version, origin/CSRF, XSS text rendering, SQL-injection search, portal IDOR/disabled account, нормальный/ошибочный browser save. Migration 006 up/up/down/up сохраняет исходные rows; populated rollback, unmanaged collisions, checksum tamper, partial journal fail closed. Browser report и снимки — STAGE-5-UX.md.

## Что требует внешних решений и не включено в production

1. Review Stage 3/4 и Stage 5 отдельно. Draft PR Stage 5 — для разработки/ревью, не разрешение merge в автоматически публикуемый main.
2. Production миграции 004/005/006 не выполнены. До них maintenance + проверенный private DB backup/recovery и явное одобрение. Частичный DDL требует backup recovery, автоматического force/retry нет.
3. Production manifest/allowlist намеренно сохранён. Он ещё НЕ включает новые CRM/customer files. Публикация Stage 5 требует отдельного согласованного обновления manifest и staging-проверки полного пакета; зелёный существующий release CI не решает этот blocker.
4. `crm_operations_enabled` остаётся false по умолчанию. Для активации нужны юридически одобренные документы, privacy configuration, отдельно Stage 4 flags/SMTP/registration approvals. Реальные персональные данные и письма в этом ходе не создавались.
5. Employee records — без login; это ограничение области Stage 5, не незавершённая симуляция доступа.
6. Доски/списки — по 25 records; профиль показывает первые 25 related records и до 100 history events, полные списки доступны через пагинацию. Notifications sync обрабатывает bounded batches (100 leads / 100 tasks / 100 projects), не гарантирует исторический backfill больших backlog; cron не предполагается.
7. Нет automated billing/payment integration, drag-only обязательных действий, customer-visible внутренних tasks/notes или отдельного UI legal-approval bypass. Expert screen reader/axe и production end-to-end CRM не проверялись.

Разработка источников и изолированная проверка не означают готовность production release. Ничего не слито/развёрнуто; database credentials/SSH keys/real config и privacy settings не изменялись.

**STAGE 5 DEVELOPMENT COMPLETE — READY FOR REVIEW.**
