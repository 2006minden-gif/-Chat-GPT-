# Stage 7 — платёжная интеграция и ограничения

## Реализовано, но не активировано

`BillingProvider` определяет createPayment/getPaymentStatus/verifyWebhook/normalizeProviderEvent/requestRefund/getRefundStatus. Адаптер `YooKassaSandbox` использует фиксированный `https://api.yookassa.ru/v3/` без redirects, Basic merchant credentials из private/config.php, TLS peer verification, bounded response/timeouts, строгий HTTP/content-type/JSON validation и persisted Idempotence-Key. Карточные поля не принимаются и не хранятся.

**Live adapter отсутствует.** Разрешены только `mode=sandbox`, `sandbox_approved=true`, enabled=true, отдельный shop_id и ключ с test_ prefix. Все ответы payments обязаны иметь test=true; settled status требует paid=true/captured_at. Обычный live key отклоняется до первого API call. Эти проверки не заменяют надлежащую выдачу тестовых ключей.

Provider redirect разрешён только на HTTPS hosts yookassa.ru/yoomoney.ru/checkout.payments.yandex.ru, без userinfo/port/fragment/control/backslash. Возврат браузера открывает detail; не записывает деньги и не доверяет query/hash success parameters. Пользователь видит pending до authoritative verification.

YooKassa callback не трактуется как подписанное доказательство. Payload — только hint. Endpoint ищет уже известный provider ID, запрашивает объект через merchant-authenticated API и проверяет provider ID, merchant hash, amount, RUB, test flag, metadata bound to persisted attempt key. Refund GET дополнительно проверяет payment_id и точную сумму известного резервирования; связь с проверенным sandbox payment обязательна. Неизвестные IDs отвергаются; callback не вызывает создание платежа. Не придуман универсальный HMAC для провайдера без такого протокола.

Нужно повторно сверить актуальные требования callback IP/network validation, разрешённые redirect hosts, idempotency retention, payment/refund transitions и API контракт с официальной документацией до внешнего sandbox acceptance. Текущий доступ к официальным страницам в среде вернул URLError; не заявляется, что текущая merchant eligibility / фискализация проверены.

Ссылки для обязательной внешней проверки:

- https://yookassa.ru/developers/api
- https://yookassa.ru/developers/using-api/webhooks
- https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing

Выбор YooKassa здесь — отключённый sandbox implementation candidate, не решение о подключении мерчанта. Регистрационная форма бизнеса, страна, юрисдикция, налоги, валюта, документы/оферта, возвраты/retention, необходимость фискализации владельцем не подтверждены. Stripe / T-Bank не подключены и их eligibility не предполагается.

## Реально выполненные тесты

Разработка использует **mocked HTTP transport**, который реализует только provider fixtures. `billing_test_transport` допустим исключительно при billing_test_mode=true, loopback app_url и HTTP 127.0.0.1 transport. Значения fixture credentials синтетические, не рабочие. Это не внешний YooKassa sandbox и не имитация доступной production оплаты.

Проверены pending → authoritative succeeded, forged success hint against pending, duplicate/concurrent effects, reconciliation after missed callback, creating retry, amount/currency/merchant metadata/test mismatch, unsafe redirect, refund reservation/completion/cancellation, amount bounds, true parallel PHP workers. Клиентский return не считается доказательством. Реальный внешний sandbox, запросы к production API, денежные списания и возвраты **не выполнялись**.

## Обязательные действия перед подключением

1. Одобрить merchant/provider eligibility, договор, необходимые реквизиты/налоговый режим/фискализацию/retention и privacy/transactional notifications. Никаких выдуманных ставок или legal compliance claims.
2. Проверить актуальный API contract и режим отдельного sandbox account. Передать секреты через защищённую серверную конфигурацию вне Git/chat.
3. Выполнить внешний sandbox acceptance с разрешённым callback URL и настоящими test credentials; проверить не только API status, но webhook/reconciliation/refund timeout/replay, отсутствие реальных списаний.
4. Подготовить отдельно проверенную release/migration/storage/mail конфигурацию. Этот этап не изменяет manifests/workflows/SpaceWeb.
5. Для live потребуется отдельный одобренный адаптер/релиз и разрешённый end-to-end тест. Переключение mode на live здесь ничего не активирует.

Дополнительные server prerequisites: 64-bit PHP 8.4, PDO MySQL, mbstring, OpenSSL HTTPS streams, allow_url_fopen для server-to-server HTTPS, trusted CA store/DNS/egress to provider. Provider API timeouts оставляют reconcilable records, а не финансовый success/failure из догадок.
