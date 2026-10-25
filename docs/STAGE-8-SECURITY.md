# Stage 8 — безопасность и эксплуатационные границы

## Права и согласования

Owner — existing nd_session/current_session, customer — existing Stage 4 session/current consent. Server-side project/customer scope проверяется и при создании task, и при построении контекста, и перед бизнес-эффектом. Public visitor имеет отдельный random cookie/hashed ID/CSRF и только consultant capability; owner/customer task IDs ему недоступны. Нет customer accounts, созданных помощником.

CSRF/origin, prepared statements, strict types/size limits и existing Russian safe errors сохраняются. Все новые public PHP endpoints подавляют display_errors; технические сбои через существующий metadata-only server_error с request ID, без SQL/credentials/prompt text.

Trusted backend, не модель, выбирает targets/tools. Agent permissions фиксированы в registry; owner toggle/rule не может включить финансовый/административный tool. Неизвестный output field/action/agent/tool_calls/target/evidence reference отклоняется до эффекта. Arbitrary PHP/JS/SQL/shell/URLs в rule configuration не поддерживаются.

Approval связан с task, artifact revision/hash, exact action+targets, current source versions, owner ID, decision timestamp/expiry. Price quotation ID/hash дополнительно связан с commercial proposal; rates/scope/policy свежесть повторно проверяется при review/apply. Task/approval row locks + same DB transaction дают один эффект, включая параллельные PHP processes. Price editing или artifact editing создаёт новую редакцию; старое согласование не авторизует новую.

## Контекст и недоверенные данные

Минимальные fields по purpose, customer isolation, ограниченные excerpts, отдельные facts/untrusted/assumptions. Пароли/DB/API/session credentials не выбираются из private config или auth tables в AI context. Contacts исключаются; email/phone/secret patterns redacted в текстовых excerpts. Redaction не является полной DLP или гарантией удаления произвольной персональной информации: free text может её содержать. Поэтому live processing требует отдельного legal/provider approval, minimization review и соответствующих документов.

Prompt injection не получает execution authority: модель не имеет database/filesystem/admin tools, только bounded context. Uploaded binary files, URL retrieval, external email и arbitrary paths не читаются. Structured output не гарантирует семантическую правдивость: prose помечено как inference/draft, фактические показатели серверные; meaningful external commitments требуют exact owner review. No legal/compliance certification.

Approved public service catalog — отдельно owner configured/approved, без выдуманных цен. Empty/unapproved catalog закрывает consultation. Customer/public AI request требует явного current policy consent, не preselected checkbox; status/time/version/hash записываются. Public lead transfer — только пользователь переносит summary в обычную форму; старая форма ещё требует самостоятельного подтверждения и отправки. No marketing/training/fine-tuning consent assumed.

## Provider / SSRF

Live Nodul/model integration не реализована: текущие официальные страницы не прочитаны из этой среды, verified endpoints/auth/callback contract отсутствуют. Нет неподписанного invented webhook.

Единственный runnable adapter — HTTP mock, допустимый только при ai_test_mode=true, loopback app_url, endpoint HTTP 127.0.0.1 без userinfo/query/fragment/path. Любой другой provider type/endpoint не выполняет HTTP. Это fixture transport, не production AI service. Server validates HTTP/status/content-type/JSON/response length/timeout and typed usage. Secrets не передаются browser/model/context/logs.

## Budget / worker

Task creation actor/day cap и independent global day/month, actor and agent budgets. Reservation under sorted row locks, token/context/output bounds, integer estimated micro-cost/currency, max per-task estimate. Unknown configured estimate/currency → no provider call. Actual reported usage/cost хранится отдельно, NULL сохраняется как unknown, валюты группируются, не суммируются. Консервативные reservations не возвращаются после timeout/unknown outcome. Это local execution safeguards; отсутствующий live adapter не доказывает реальный hard spending cap у внешнего провайдера.

Один inference в DB-scoped advisory lock, depth=1, max 3 attempts, bounded timeout ≤15 sec, backoff, rate-limit delay/circuit breaker. Unknown worker outcome → NEEDS_HUMAN без скрытого повторного эффекта. Client cancel не обещает остановить уже оплачиваемый remote call: полученный поздний результат не применяется. Failed permanent tasks не пересоздаются автоматически.

`scripts/ai-worker.php` не установлен в cron. Периодические rules default off; explicit owner one-time rules/run не равен recurring schedule. Pricing auto mode тоже отдельно default off. CLI batch до 5 jobs/20 pricing projects, durable cursor и idempotency. Состояние reserved rule event после crash требует recovery/owner review; failed event не пересоздаётся бесконечно.

## Retention / data

Task payload TTL=30 days; visitor session=1 day. Owner-approved operational schedule должен запускать `php scripts/ai-worker.php cleanup`: bounded batch очищает input/artifact/context payload, expired proposals больше неприменимы; audit hashes/metadata остаются. Public clear очищает только собственный conversation payload, не чужие записи и не audit trail.

Созданные Stage 6 business drafts/messages и pricing snapshots имеют собственную business retention: AI cleanup не удаляет их. Согласованные документы/ставки/финансовые данные не hard-delete. Production retention policy и backup/restore должны быть одобрены владельцем; cron/cleanup на SpaceWeb не настраивались. Не заявляется соответствие GDPR, 54-ФЗ или иной правовой норме.

## Production blockers

Все feature/provider/pricing auto flags default off. Нужны отдельные review/integration Stage 3–8, approved legal/cost/provider configuration, 009/010 migrations в maintenance с backup/restore, полное обновление release allowlist/manual package для новых assets/private modules/scripts. Deployment automation этой задачей не менялась; существующий checked release не доказывает готовность упаковки Stage 8. Current landing references optional AI assets; публиковать такой partial package нельзя.

PHP prerequisites: 64-bit PHP 8.4, PDO MySQL, mbstring, existing HTTPS/session/CSP setup; real provider transport/extensions/CA/egress должны определяться только после documented adapter review. MySQL 5.7 проверяется isolated runtime. Нет production migration, payment, refund, deadline change, deployment, hosting credential action или внешних сообщений.
