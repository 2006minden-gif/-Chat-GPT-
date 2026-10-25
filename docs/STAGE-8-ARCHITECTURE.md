# Stage 8 — ИИ-центр и расчёт цены

## Цепочка разработки

Ветка `feature/stage-8-ai-automation` создана поверх Stage 7 `f7c2630` (`feature/stage-7-billing-notifications`). На проверке main — `478ca7f`; Stage 6 draft PR #22/base Stage 5 PR #21; Stage 4 PR #7 и Stage 3 PR #4 ещё не считаются merged/activated. Stage 7 branch существует, создание его PR ранее было заблокировано GitHub API. Read-only сведения проверены через git fetch и существующую `automation/evidence`. AGENTS.md в доступном дереве не найден.

Никакой merge, production SQL, deploy, SSH, изменения workflow/manifest/packaging automation здесь не выполняются. PHP 8.4/PDO/MySQL 5.7/vanilla JS/local CSS/CSP сохранены. Не добавлены Python application server, Redis, vector DB, frontend framework или локальные модели.

## Компоненты

| Модуль | Обязанность |
|---|---|
| private/ai/registry.php | Версионируемые trusted definitions: схемы, read scope, действия, роли, пределы |
| core.php / tasks.php | Existing auth gates, scoped gateway, actor-bound idempotency, lifecycle/events |
| context.php | Минимальные авторизованные факты, untrusted text отдельно, redaction/limits/source versions |
| provider.php | Provider interface и исключительно loopback mock transport; live endpoints не придуманы |
| schema.php | Strict output/agent/result/field/evidence validation, без исполнения tool calls |
| engine.php | Durable attempt, budget reservations, bounded inference, CAS state, cancel/source recheck, result publisher |
| approvals.php | Неизменяемые версии результата, exact action/hash/target versions/owner/expiry, apply once |
| rules.php | Поддерживаемые trigger/action types, durable reservations/max runs, manual and periodic prerequisites |
| read.php / public.php / routes.php | Owner control center, customer-scoped data, isolated anonymous visitor sessions |
| private/pricing/* | Cost registry, deterministic calculation, quotation decisions/versioning, approved-price contract |

Dispatcher маршрутизирует явный intent в одного специалиста; неизвестный intent → NEEDS_HUMAN. Не заявляется естественно-языковая маршрутизация без подтверждённого результата модели. Нет рекурсивных делегаций, depth=1, нет произвольных инструментов/SQL/кода/URL. Пример owner intent tasks выбирает task_assistant, а customer intent business_report всё равно отклоняется по роли.

## Реестр агентов

Сохранены все десять требуемых специализаций и добавлен отдельный оценщик затрат из архитектурного дополнения:

| ID | Роль / ограничения |
|---|---|
| dispatcher | ИИ-диспетчер; routing/clarification, не расширяет права |
| consultant | Одобренный каталог + свой scope; без финальной цены, заказа или автоматической заявки |
| lead_analyst | Advisory analysis, requirements/missing info/priority; возможные дубликаты только из exact-contact candidates, без отправки контакта модели и без merge |
| proposal | Черновик по одобренной цене; точная отправка отдельно согласуется владельцем |
| specification | Structured ТЗ → настоящая Stage 6 draft revision, AI provenance, без ready/submit/approval |
| planner | Proposed milestones/tasks; actual todo tasks только по exact owner approval, без assignee/deadline changes |
| task_assistant | Приоритеты/блокеры/черновики, без изменения исполнителей/завершения |
| project_monitor | Объективные overdue/progress facts отдельно от estimated risk; deduplicated internal alerts |
| document_assistant | Доступные structured revisions/previous version, без произвольных файлов/юридической сертификации |
| business_analyst | Actual aggregate CRM/financial facts, без придуманных доходов или FX |
| cost_estimator | Work packages, development/testing/resource quantities, nullable unknowns, uncertainty/risk/basis; никаких ставок/цен из модели |

Все агенты выключены до явного owner enable. Канонические права/схемы нельзя редактировать из браузера. `nd_ai_agents` — overrides enabled/version, registry не дублирует CRM employees/customers/accounts. Сотрудники не требуются: весь approval workflow работает с существующим owner ID=1.

## Lifecycle и эффекты

CREATED → VALIDATING → QUEUED → RUNNING → COMPLETED или AWAITING_APPROVAL. Отдельно APPROVED → APPLYING → APPLIED; REJECTED/FAILED/CANCELLED/NEEDS_HUMAN. Inference completion ≠ approved/applied operation. Events пишутся транзакционно; state transitions проверяются сервером.

Сначала persistent task + attempt + usage reservation + context hash/versions, затем HTTP вне DB transaction, затем validated artifact и разрешённый эффект под повторной проверкой источников. Result ignored после cancellation; remote cancellation не обещается. После неизвестного worker outcome — NEEDS_HUMAN, не скрытый повтор inference.

Разрешены только:

- Advisory artifacts: без изменения фактов CRM.
- Owner-requested specification draft через общий validated Stage 6 effect helper; прежний API wrapper/idempotency сохранён.
- Cost estimate / quotation draft: без финальной цены и внешней отправки.
- Project monitor internal alert только по actual overdue facts, dedupe по project/evidence hash.
- Exact approved send_message или create_tasks. Shared Stage 6 message effect и Stage 5 crm_insert работают внутри той же approval transaction; nested transactions не добавлены.

AI executor не поддерживает invoices/refunds/payments, реквизиты, договорные сроки, deployment, shell/SQL, delete/archive, assignment/status-complete или bulk communications. Даже owner approval не создаёт такого tool capability. Existing human billing остаётся прежним отдельным owner workflow.

## Контекст и результат

Input/output schemas ограничены по полям/типам/объёму. Общий envelope: agent, summary, observations (indices server facts), assumptions, missing_information, suggestions, typed result. Unknown fields/tool_calls/action types/agent IDs/evidence references/oversized or malformed output → failure, не success. Semantic hallucinations не считаются устранёнными структурной схемой: prose остаётся labelled interpretation и требует human review.

Источники: existing project/customer ownership; до 30 stages/tasks, 5 общих сообщений; document structured text + preceding revision; owner aggregate finance через Stage 7 только если billing enabled. Customer consultant получает customer-visible project/stage/approval facts; внутренние описания/задачи/файлы/платёжные секреты ему не выдаются. Raw upload bytes/URLs/email не читаются. Полная CRM/БД провайдеру недоступна.

## База данных

009_ai_automation: 13 additive InnoDB tables — agents, visitors, tasks, events, attempts, context_refs, artifacts, approvals, rules, rule_runs, usage, budgets, provider_state. Unique request keys/attempt correlations/artifact revisions, FK на existing customers/projects/leads/revisions/admin, UTC.

010_project_pricing: 8 additive InnoDB tables — cost_registry_keys, cost_rates, pricing_policies, project_estimates, quotations, pricing_decisions, project_actuals, pricing_scan_state. Это номера DB migration, а не запуск Stage 9/10.

`scripts/migrate-ai.php`, `scripts/migrate-pricing.php` наследуют существующие journal/checksum/dependency/advisory-lock/strict-mode guards. Up не продолжает partial state автоматически. Down разрешён только для пустых новых таблиц; populated финансовая/approval история не удаляется. Перед production — отдельный backup/restore/migration review; SQL здесь выполнялся только в random loopback neuro_test_* databases.

## API и интерфейсы

Owner prefix `/api.php?r=crm/ai/`; customer `/customer-api.php?r=ai/`.

- GET tasks / tasks/ID; POST tasks; POST tasks/ID/run|retry|cancel|edit.
- GET overview/agents/approvals/history/usage/settings; POST agents/ID (enabled/version only).
- POST approvals/ID/decide|apply: exact checksum/version/confirm; owner only.
- GET rules/rules/ID; POST rules[/ID], rules/ID/test|execute, rules/run (explicit one-time confirm).
- Owner-only `pricing/*` routes описаны в PRICING-STAGES-8-10.md.

Public `/ai-public-api.php`: status/session/tasks/tasks/ID/chat/clear. Random HttpOnly/SameSite visitor cookie, DB hash + CSRF, no customer account. Current AI consent timestamp/policy hash/version recorded per request, checkbox не выбран заранее. Public task accepts only consultant question/consent/key, rejects CRM IDs/admin commands. CRM lead не создаётся: UI может перенести summary в обычную форму; её отправка и consent остаются отдельными явными действиями.

`public/ai.php` → existing design owner ИИ-центр / customer assistant. Owner project/lead links; landing launcher remains absent when disabled. Pricing renderer only displays server values; не рассчитывает authoritative totals в JS.

## Provider / scheduling prerequisites

Nodul / compatible live model API documentation из среды недоступна (URLError). Их endpoints/auth/callbacks не придуманы. Единственный исполняемый adapter — explicitly test-only HTTP 127.0.0.1 with loopback app_url and ai_test_mode=true. Configured live type показывает live_unavailable, не осуществляет HTTP. Никакой verified live AI integration не заявляется.

`scripts/ai-worker.php` CLI-only: до 5 queued jobs за запуск, bounded retries/backoff/circuit, optional rules/pricing scan, retention cleanup subcommand. Настоящее расписание не установлено; flags не доказывают работающий cron. Settings всегда scheduler_verified=false. Длинные/asynchronous jobs и Nodul callbacks пока unsupported. Owner может явно запустить bounded task/run либо one-time rules/run без заявления о recurring automation.
