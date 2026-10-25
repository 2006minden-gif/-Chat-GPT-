# Stage 7 — отчёт разработки

Дата: 25.10.2026. Ветка `feature/stage-7-billing-notifications`, base — `feature/stage-6-client-collaboration` (`d9ad539`, draft PR #22). Main при проверке — `478ca7f`. Stage 3/4/5/6 не объединялись и не публиковались этой задачей.

## Реализовано

1. Счета: customer/order relationship, позиции/количество/цена, decimal-safe integer расчёты, guarded draft/save/issue/cancel/send, уникальная последовательность номеров, immutable snapshot/hash, реальные HTML download/print, отдельные credit adjustments/replacement links, запрет over-invoicing.
2. Provider interface и отключённый YooKassa sandbox candidate: hosted flow, durable creating attempts/idempotency, retry/reconcile после неизвестного результата, строгая проверка HTTP/JSON/merchant/amount/currency/metadata/test, allowlisted redirects, отсутствие card collection и live adapter.
3. Webhook hint → merchant-authenticated GET → atomic once-only transaction. Customer redirect не подтверждает оплату. Bounded body в том числе без Content-Length, unknown/mismatched events отклоняются.
4. Возвраты: owner confirmation/CSRF, reserved refundable balance, отдельно pending/confirmed/canceled, idempotent retries, current locking reads после финансового mutex. Финансовая история не удаляется.
5. Durable outbox + прежний CRM owner inbox/activity history, русские multipart templates через existing SMTP transport, delivery lease/retry/backoff/failure state, optional preferences без маркетинга. In-app события создаются вместе с бизнес-транзакцией.
6. Customer financial cabinet и existing portal links; серверная изоляция счетов/payments/refunds/documents/notifications. Owner finance section, filters, actual RUB cash metrics, monthly chart, formula-safe private CSV.
7. CLI-only migration/worker, по умолчанию выключенные feature/email/provider approval flags. Production integration намеренно не менялась.

Файлы: `private/billing/{core,invoices,provider,payments,notifications,hooks,read,routes}.php`; `public/{billing.php,billing.js,billing.css,invoice-document.php,payment-webhook.php}`; additive hooks/navigation в existing `private/crm`, `private/collab`, `private/customer-auth.php`, `private/customer-mail.php`, `public/operations.js`, `public/portal.php`; sample config; test router; два test modules; docs и synthetic screenshots.

## База данных и восстановление

`database/migrations/008_billing_notifications/{up,down}.sql`, runner `scripts/migrate-billing.php`: 10 новых InnoDB tables, dependency/checksum/advisory lock, strict SQL mode, journaled partial failure. Никаких изменений/дублирования Stage 3–6 tables и production data.

Проверены up/up/down/up на пустой новой схеме с сохранением прежних admin/lead/customer/order records, unmanaged collision, partial empty recovery, checksum mismatch, отказ rollback при financial data и запрет отката 007 при наличии 008. MySQL DDL не транзакционен: partial up не продолжается автоматически; сначала безопасный empty-only recovery или отдельный reviewed forward repair. Нет force/destroy production режима.

## Выполненные проверки

**Финальный полный suite: 225 Python tests PASS, 0 FAIL / 0 SKIP**, включая 17 Stage 7 tests (14 функциональных/HTTP/security/browser + 3 migration). **12 Node tests PASS**. PHP 8.4 lint — 49 файлов PASS; JS syntax, compileall, actionlint, release policy и diff check PASS. Redacted Gitleaks scan — 0 находок.

Среда: PHP 8.4.27, MySQL 5.7.42, Apache 2.4.69 для существующих security tests, Chromium, локальные SMTP/provider fixtures. Testing DB names random neuro_test_*, loopback-only. Реальный внешний sandbox и SMTP не использовались. Отдельные PHP-процессы проверили unique invoice numbering, once-only settlement и конкурирующий refund reservation. Тест выявил RR stale-read race; исправление — current locking reads после order/invoice mutex, не ослабление assertions.

Браузерные результаты и synthetic изображения: [STAGE-7-UX.md](STAGE-7-UX.md). Детали API/модели: [STAGE-7-ARCHITECTURE.md](STAGE-7-ARCHITECTURE.md), provider/security: [STAGE-7-PAYMENTS.md](STAGE-7-PAYMENTS.md), queue/SMTP: [STAGE-7-NOTIFICATIONS.md](STAGE-7-NOTIFICATIONS.md).

## Что не подтверждено / ограничения

- **Ни внешний sandbox acceptance, ни live payments не проверены.** Попытка чтения текущей официальной YooKassa документации из среды недоступна. Merchant/provider eligibility, актуальный API/webhook/fiscalization contract и hosts требуют внешней проверки до test activation. Sandbox adapter — candidate, не подключённый эквайринг.
- Live mode всегда закрыт; test prefix/flag/body validation не заменяют реальный отдельный sandbox account. Нет сохранённых карточных реквизитов, фискальных чеков, электронной подписи, tax reporting/PCI/GDPR/54-ФЗ claims.
- Нет внешнего SMTP, проверки inbox/SPF/DKIM/DMARC или установленного scheduler. In-app delivery работает в isolated tests; автоматические timed reminders/email/reconciliation требуют явно настроенного CLI worker. Необязательный email default false, essential отдельно. SMTP uncertain acceptance допускает повтор с тем же Message-ID; exactly-once external email не обещается.
- Поддерживается только RUB. Partial payment UX, discounts, tax rates, fees/accounting revenue/FX не добавлены без согласованных business/legal policies. Financial corrections — credit-only; standalone invoices не поддерживаются.
- Reports capped 5000 candidate invoices, service grouping = existing order title. Это управленческие cash metrics, не бухгалтерская отчётность. Invoice-date filter не означает settlement-date filter.
- Нет production load/latency/real provider outage acceptance или экспертного accessibility audit. Не все mutation branches повторены через browser — покрыты HTTP/DB tests.
- **Production release manifest и manual packaging script не включают все Stage 7 private services/worker/migration assets.** Они намеренно не менялись по запрету изменений deployment automation. До отдельного reviewed packaging update публиковать Stage 7 нельзя; текущий production release не подтверждает поставку этого этапа.

## Требования к активации

1. Review/integration прежних stages и Stage 7, без auto-merge. Отдельно согласовать полный release allowlist/manual packaging, миграции и deployment.
2. Maintenance, проверенные DB/private backups/restore, isolated/staging application of approved migrations 004–008; production runner сейчас не запускался.
3. 64-bit PHP/PDO MySQL/mbstring/OpenSSL, HTTPS streams/CA/DNS/egress, server limits; private config вне document root. Предыдущие Fileinfo/ZipArchive/storage prerequisites Stage 6 сохраняются.
4. Одобренные merchant legal details, tax/payment/refund/retention terms, privacy/notification purposes. Заполнить sample settings только в private config, без секретов в Git/chat.
5. Проверенный внешний sandbox после review current provider docs; отдельные test credentials/approval flags. Для live нужна отдельная реализация/одобрение/разрешённый end-to-end test.
6. При необходимости одобрить sender/SMTP/owner email и настроить CLI schedule. Учитывать initial backlog reminders; не включать старые disabled emails массово без решения владельца.

Deployment: **не выполнялся**. GitHub Actions, release implementation, SSH, production config/data/schema/privacy flags не менялись. Рабочие credentials в репозиторий не добавлялись.

## GitHub review

Ветка готова для draft PR с base `feature/stage-6-client-collaboration`, не main. Создание PR и hosted CI проверяются отдельно после push; local PASS не выдаётся за remote CI.
