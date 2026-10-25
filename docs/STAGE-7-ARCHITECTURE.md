# Stage 7 — финансы и уведомления

## Состояние и зависимости

Ветка `feature/stage-7-billing-notifications` основана на Stage 6 `d9ad539` / draft PR #22, base Stage 5 `a6a7b8c` / draft PR #21; в цепочке Stage 4 `92f2b22` / PR #7 и Stage 3 `968c82d` / PR #4. При проверке main — `478ca7f`; эти этапы не считаются интегрированными или опубликованными. Источник сведений о PR — существующая ветка `automation/evidence`, дополнительно git fetch именованных веток. Источник не менялся. Повторная попытка GitHub API вернула Forbidden.

Сохраняются PHP 8.4/PDO/MySQL 5.7, vanilla JavaScript, local CSS/CSP. Нет нового сервера, фреймворка, БД, пользователей или альтернативного deployment workflow. Новые страницы используют существующие owner/customer sessions и CSRF. `billing_enabled=false` по умолчанию; необходимы прежние CRM/privacy/auth gates и применённая миграция 008. Stage 6 не заменён.

## Модель

Миграция `database/migrations/008_billing_notifications` добавляет 10 InnoDB таблиц:

| Таблица | Назначение / ограничения |
|---|---|
| nd_billing_sequences | Счётчик года под FOR UPDATE; номер выдаётся внутри транзакции |
| nd_invoices | FK customer + composite order/customer; unique number; draft/issued/cancelled, immutable issued snapshot + SHA256; optional replaces_id |
| nd_invoice_lines | FK invoice; unique position; integer quantity_milli, unit_minor, total_minor |
| nd_payment_attempts | FK invoice; unique request_key/provider_id; merchant hash; persisted creating/pending/succeeded/canceled; next_check |
| nd_payment_transactions | Unique attempt and provider transaction; только подтверждённое списание |
| nd_payment_events | Unique normalized authoritative payment-state key; не сохраняет произвольный payload callback |
| nd_refunds | FK attempt; unique idempotency/provider IDs; creating/pending/succeeded/canceled; резерв до подтверждения/отмены |
| nd_invoice_adjustments | Неизменяемое уменьшение долга с reason и unique request key |
| nd_notification_outbox | Unique event/recipient/channel; template version, status, bounded retries/backoff, lease token/time, safe error category |
| nd_notification_preferences | Existing customer account FK; optional_email=false default |

История — прежняя `nd_activity_history`; owner inbox — прежняя `nd_crm_notifications`; request deduplication — прежняя `nd_crm_requests`. Новые outbox records необходимы для индивидуальной доставки клиентам/каналам, не заменяют business identities или project history.

## Денежные правила

- Только RUB с precision=2, как в Stage 5. Нет FX или суммирования разных валют.
- Авторитетные суммы — целые копейки, quantity — целые тысячные. Вход только десятичные строки, без float/exponent/знака/запятой. PHP требует 64-bit runtime.
- Одна позиция: `floor((quantity_milli * unit_minor + 500)/1000)`, half-up до копейки; количество 0.001–1000.000. Общий счёт до 9 999 999 999 копеек. Все произведения укладываются в signed 64-bit; суммирование максимум 50 позиций проверяется.
- Цены и налоги не вычисляются из догадок. Скидки/налоговые ставки не реализованы; owner-approved tax wording и реквизиты входят в snapshot. До юридической проверки issue блокируется.
- После issue строки, сумма, due date и merchant/customer/order snapshot не меняются. Статус оплаты — производный, а не редактируемое поле.
- `net_received = settled_payments - confirmed_refunds`; `target = invoice_total - adjustments`; `outstanding = max(0, target - net_received)`. Paid/refunded/partial/overdue выводятся из lifecycle и ledger. Возврат не списывает обязательства автоматически и не разрешает повторное списание по тому же счёту.
- Корректировка только уменьшает текущий долг, не больше долга, с причиной/подтверждением/version. Платёж в процессе блокирует корректировку/отмену. Увеличение цены — согласование суммы заказа и отдельный счёт. Замена — новый draft с replaces_id только для отменённого счёта того же заказа.
- Сумма выставленных счетов за вычетом корректировок не превышает согласованную сумму заказа. Возврат не создаёт разрешение повторно выставить ту же сумму без изменения business terms.
- Cancel запрещён при любых записанных оплатах или creating/pending attempts. Отмена заказа/проекта никогда не инициирует возврат.
- `refundable = captured - succeeded/pending/creating refunds`. Отменённый/failed-by-provider возврат освобождает резерв, API timeout — нет. Provider fees отдельно, не предполагаются нулевыми и не моделируются как бухгалтерская выручка.

## Конкурентность и восстановление

Порядок блокировок: order → invoice → payment/refund; issue дополнительно блокирует sequence. Idempotency result хранится атомарно вместе с локальным изменением. После ожидания mutex финансовые проверки используют свежие locking reads, включая refund reservations; обычный RR snapshot здесь опасен и покрыт тестом двух PHP-процессов. Обычные balance reads используют один SQL statement для согласованных агрегатов.

Сначала коммитится creating attempt/refund, затем вызывается внешний API с тем же persisted idempotency key. Неопределённый ответ оставляет creating/pending и safe error category; повторная проверка использует тот же POST/key или GET известного ID. Новый клик во время незавершённого платежа возвращает существующий attempt. Внешний HTTP никогда не выполняется под финансовой транзакцией/row locks.

Для одного settled attempt существует максимум одна transaction. После order mutex повторный callback перечитывает state под FOR UPDATE. Статусы terminal не откатываются. Refund IDs уникальны. Несоответствие магазина/суммы/валюты/metadata/статуса не меняет ledger; owner видит безопасный сбой проверки.

## API

Owner prefix: `/api.php?r=crm/billing/`; customer prefix: `/customer-api.php?r=billing/`. GET records проверяются сервером по session-derived customer_id; draft/неотправленные документы скрыты от клиента одинаковым 404. Изменения — POST JSON + existing CSRF/origin + actor rate limit. Для мутаций используются 64-hex request keys, для document changes — version и confirm=true.

| Метод / route | Доступ / результат |
|---|---|
| GET invoices | Authorized paginated list; filters from/to/customer_id/order_id/status/service/currency |
| GET invoices/ID | Scoped detail, lines, ledger-derived balance, payment/refund/adjustment history |
| POST invoices | Owner draft; existing customer/order required, standalone invoices unsupported |
| POST invoices/ID/save | Owner draft only, version |
| POST invoices/ID/issue | Owner, approved merchant, number + immutable snapshot + event transaction |
| POST invoices/ID/cancel | Owner, guarded lifecycle/version |
| POST invoices/ID/send | Owner, availability in cabinet + deduplicated notice; не обещание email delivery |
| POST invoices/ID/adjust | Owner credit adjustment, amount string, reason, version, confirm |
| POST invoices/ID/pay | Customer-owned invoice; sandbox only, confirm, idempotent reservation |
| POST payments/ID/reconcile | Owner or owning customer; authoritative provider GET / same creating key |
| POST payments/ID/refund | Owner, amount/reason/confirm, durable reservation |
| POST refunds/ID/reconcile | Owner; confirmed refund outcome |
| GET payments / refunds | Owner paginated safe transaction lists |
| GET report / export | Owner only; actual persisted RUB totals / formula-safe CSV |
| GET settings | Safe flags only; no credentials, no API to activate live billing |
| GET notifications | Owner delivery failures + in-app; customer own in-app only |
| POST notifications/ID/read | Scoped recipient update only |
| GET / POST preferences | Existing account optional email preference; no marketing assumption |

`/invoice-document.php?mode=owner|customer&id=ID[&download=1]` — protected real HTML, SHA-verified snapshot, escaped Russian layout, .html extension, no-store; printable with Ctrl+P. Document totals/parties immutable, current settlement summary labelled separately. Not a fiscal receipt, PDF or electronic signature.

`/payment-webhook.php` — POST, 8 KiB max, rate limited, known provider ID required, no session/CSRF (provider callback). Separate provider-specific verification is described in STAGE-7-PAYMENTS.md.

## Reports and UI

Owner: Финансы → Счета / Платежи / Возвраты / Задолженности / Финансовые отчёты / Настройки оплаты / Уведомления. Customer: Оплата и счета / Уведомления / Настройки уведомлений. Existing order links retained. Backend owns all totals. Browser floats are used only for editing/display of quantities, never financial authority.

Filters apply to invoice issue date, existing customer/order, order title as service name, derived status, RUB. No separate service taxonomy was invented. Monthly chart uses settlement months within selected invoices; service grouping is by order title. These are cash metrics, not tax/accounting revenue. Returns/refunds remain separate. Reports/lists cap at 5000 candidate invoices and require narrower filters beyond this; no silently truncated report. Lists paginate after derived status filtering.

CSV protects cells beginning with whitespace/formula prefixes. Customer cannot export owner reports. Draft forms retain data on network/HTML/validation failure; successful responses clear only submitted form state, preserving later edits. Financial operations require native confirmation and verified server result.
