# Stage 8 — отчёт разработки и архитектурное дополнение цены

Дата: 25.10.2026. Ветка `feature/stage-8-ai-automation`, base — Stage 7 `f7c2630`. Main на проверке — `478ca7f`. Зависимости Stage 3/4/5/6/7 сохранены, не объединялись и не публиковались. Разработка Stage 9/10 не запускалась; обязательный pricing contract для них описан отдельно.

## Выполнено

- Task gateway/dispatcher/registry: все 10 исходных специализаций плюс отдельный Cost Estimator. Purpose/input/output/read/action/role/approval/budget/version definitions, per-agent enable и fixed platform safety constraints.
- Existing owner/customer auth, public visitor isolation, current AI consent, scoped/minimized context, redaction и explicit untrusted text. Unknown/model tool calls, foreign IDs/roles, schema errors и unsupported actions не исполняются.
- Persistent task lifecycle, events/attempts/correlation/context hashes/artifact versions; bounded mock HTTP adapter, timeout/rate-limit/backoff/circuit, quota/estimated cost reservations. Cancelled/changed-source result не применяется; inference и business effect отделены.
- Advisory lead summaries без смены статуса/merge; proposal drafts по owner-approved price; настоящие unsent Stage 6 ТЗ drafts; proposed plans и approved todo tasks; actual project monitoring/deduplicated alerts; document/previous-version review; actual CRM/financial aggregate context.
- Exact owner approval/rejection/edit/apply: target/source versions, immutable artifact/action/price hashes, expiry/owner/time, one transactional effect. Финансы, реквизиты, договорные сроки, shell/SQL/deployment/delete/assignment/complete/bulk tools отсутствуют.
- Owner ИИ-центр, фильтры/история/агенты/правила/расходы с model/period/currency, customer own task interface и публичный responsive assistant. Disclosure/consent default unchecked; lead summary transfer не отправляет заявку/не создаёт account.
- Owner-configurable supported automation rules, max runs/durable event reservations/history/synthetic test, real manual rule execution и optional worker prerequisites. No recurring scheduler claims.

## Cost-based pricing — реализовано сейчас

`private/pricing/*`, отдельная миграция 010:

- Реестр immutable rate versions: труд владельца, model input/output, инфраструктура/инструменты/внешние/прочие затраты/комиссия, source/date/currency/validity.
- AI estimator предлагает packages/quantities/risk/uncertainty; неизвестное — NULL. Owner может уточнить подготовленную оценку, не собирать компоненты заново. Валюты не конвертируются вымышленным курсом.
- Deterministic integer-minor-unit engine: direct cost, overhead, contingency, fees/tax treatment, target/minimum profitability, recommended/final price/contribution. Policy/tax/rates/requirements unknown → NEEDS_COST_REVIEW; explicit zero не считается unknown. Минимум/negative profitability нельзя обойти model/browser fields.
- Versioned quote decisions: одобрить, изменить цену новой редакцией, пересчитать, отклонить. Exact checksum/reason/estimate acceptance/current inputs обязательны. No employee/multi-person dependency.
- Proposal provider не вызывается без fresh approved quotation. Backend renders canonical approved price; owner separately approves exact message. Rate/scope/policy changes блокируют stale send, создают новый расчёт и требуют нового одобрения.
- Completed-project owner-attested actual expenses/effort; сопоставимый estimate/actual delta, actual contribution, historical effort suggestion. Ни опубликованная цена, ни threshold/policy сами не меняются.
- Optional automatic pricing scan uses persistent cursor/scope idempotency. Production default off; отсутствующий provider не превращается в вымышленную цену.

Подробные формулы, бизнес-инварианты и обязательства будущих Stage 9/10: [PRICING-STAGES-8-10.md](PRICING-STAGES-8-10.md).

## Файлы и миграции

- `private/ai/{registry,core,context,schema,provider,tasks,approvals,engine,rules,read,public,routes}.php`.
- `private/pricing/{core,engine,routes,automation}.php`.
- `public/{ai.php,ai.js,ai.css,ai-widget.js,ai-public-api.php,pricing.js}`; optional navigation/widget integration в index.html/operations.js/portal.php.
- Small shared-effect extraction в existing Stage 6 documents/messages; прежние API wrappers и validation/idempotency сохранены. Existing CRM/customer route delegation, default-off sample config, local test router.
- `scripts/{migrate-ai.php,migrate-pricing.php,ai-worker.php}`.
- `database/migrations/009_ai_automation` (13 tables), `010_project_pricing` (8 tables). Versioned additive up, empty-only guarded down, checksum/dependency/journal/strict-mode/advisory-lock checks.
- `tests/{test_ai.py,test_ai_migrations.py,test_pricing.py}` + docs/synthetic UI evidence.

Нет изменений production data/schema/config/privacy flags, working credentials, workflows, deployment scripts или packaging automation.

## Проверки — только реально выполненное

Полные прогоны: **250 Python tests PASS**, включая 25 новых Stage 8/pricing/migration/browser scenarios и прежние 225 tests. **12 existing Node tests PASS**. PHP 8.4 lint — **70 файлов PASS**, JavaScript syntax, compileall, diff check и workflow actionlint/release validation PASS. Redacted Gitleaks scan — 0 находок. Финальный source verification выполняется перед push; hosted CI проверяется отдельно по SHA, local PASS не считается remote status.

Среда: isolated PHP 8.4.27, MySQL 5.7.42, Apache 2.4.69 (existing security suite), Chromium/Playwright, loopback provider fixtures. Только random `neuro_test_*` databases; ни одного подключения к SpaceWeb/production DB. Runtime checks не основаны только на чтении исходников.

Проверены:

- Actual HTTP gateway/agent routing, genuine Stage 6 draft creation, scoped consultant/lead/document/business contexts.
- Cross-customer/visitor denial, current consent, no account/lead auto-create; malformed/model-refusal/tool-call/foreign agent/evidence output rejection; contact/secret-pattern minimization.
- Approval before/after source change, exact one-time apply in parallel PHP processes, rejection/expiry/artifact edit preserving old revision, late cancellation result discard.
- Timeout/retry limits, provider configuration/endpoint refusal (no SSRF/live HTTP), budget exhaustion/circuit, interrupted worker recovery, retained audit after cleanup.
- Actual overdue facts → deduped owner alert, bounded configured/manual rule and idempotent task creation.
- Отдельный финальный regression: archived project сохраняет доступ к прежнему расчёту, но такой снимок stale для новых действий; 7 pricing tests PASS.
- Exact pricing figures, explicit zero vs unknown, rate/policy/scope versioning, below-minimum/negative contribution rejection, foreign currency fail-closed, tax/fee/margin rounding, approved-price proposal binding, owner-only actuals/historical suggestion.
- Owner desktop quote approval/proposal apply/control center; public mobile disclosure/consent/chat/summary handoff; no pageerror/horizontal overflow in tested views.
- Migration roundtrips preserve old records; partial/unmanaged/checksum/nonempty/newer-dependency guards.

Снимки: [STAGE-8-UX.md](STAGE-8-UX.md). Архитектура/API: [STAGE-8-ARCHITECTURE.md](STAGE-8-ARCHITECTURE.md). Safety/operations: [STAGE-8-SECURITY.md](STAGE-8-SECURITY.md).

## Не подтверждено / ограничения

1. **Verified live AI integrations: NONE.** Nodul/model API official documentation из среды недоступна. Не выдуманы endpoints/auth/callbacks; live adapters отсутствуют, not configured/disabled/live_unavailable не означают success. Все inference tests — controlled mock transport, не живой ИИ.
2. Не предоставлены live provider/merchant cost sources/secret references/model contracts, legal AI processing/provider terms и реальные ставки/налоговая трактовка владельца. Fixtures не являются рекомендуемыми рыночными или налоговыми значениями.
3. Не установлен scheduler/SpaceWeb cron; settings scheduler_verified=false. Recurring rules, automatic project pricing и cleanup на production не проверялись. Explicit one-time worker/run — не proof of automatic recurring operation.
4. Redaction и strict schemas не гарантируют семантическую истинность/NLP/DLP completeness. Meaningful proposals требуют exact human review; никаких legal/PCI/GDPR/54-ФЗ claims. Нет external file parsing, vector search/training или async agent-platform callbacks.
5. Current pricing engine рассчитан на RUB и явно поддержанные tax/overhead policies; foreign rates сохраняются, но не конвертируются без подтверждённой RUB basis. Это cost recommendation/management contribution, не бухгалтерский или фискальный engine. Existing human Stage 7 billing не переписан и order totals не меняются автоматически.
6. Existing source limits: context up to 30 tasks/stages/5 messages, rules/events/UI bounded pages, retention cleanup batch=100. Нет большого production load/cross-browser/expert accessibility audit. Guarded migration rollback только для пустых новых tables; populated data требует approved forward repair/restore.
7. **Release allowlist/manual packaging пока не включают все новые private modules/scripts/assets.** Их изменение запрещено задачей и не выполнялось. Перед production необходим отдельный полный packaging/release review; текущий CI checked release не является Stage 8 deployment package.

## Owner / production prerequisites

- Review/integration dependency chain Stage 3–8, затем отдельное разрешение deploy/migrations/activation. Никаких автоматических merge.
- Approved backup/restore/maintenance/migrations 004–010 и полноценный package со всеми зависимостями; production SQL здесь не выполнялся.
- Legal/privacy AI processing/provider review; актуальная официальная API документация и documented live adapter/real external acceptance. Секреты только в защищённой server config, не Git/chat/browser.
- Owner-approved cost sources/currencies/validity, tax/allocation/margin/minimum policy. При неизвестном — NEEDS_COST_REVIEW. Provider cost estimates и actual-reported costs не выдаются за реальные счета.
- Explicit ai/agent/public/pricing/periodic flags после проверки. Single-owner approval достаточен. Настроить и проверить worker/cleanup schedule отдельно; отсутствие cron не маскируется.
- Stage 9/10 обязаны соблюдать pricing contract; их разработка/публикация не разрешены этим отчётом.

Deployment: **не выполнялся**. Реальные AI calls, цены, invoice/refund/payment approvals и production financial changes не активировались.

## GitHub review

Ветка опубликована. REST POST создания draft PR вернул `Forbidden`; Git push работает. GitHub settings/credentials/automation не менялись для обхода ограничения.

Единственное необходимое действие владельца для PR: открыть [сравнение Stage 7 → Stage 8](https://github.com/2006minden-gif/-Chat-GPT-/compare/feature/stage-7-billing-notifications...feature/stage-8-ai-automation?expand=1) и выбрать **Create draft pull request**. Base — `feature/stage-7-billing-notifications`, compare — `feature/stage-8-ai-automation`; не merge/deploy.

Hosted push CI проверяется отдельно по финальному SHA. Existing workflow запускает pull_request CI только для main; PR с feature base не должен выдаваться за такой запуск. Workflow не менялся.
