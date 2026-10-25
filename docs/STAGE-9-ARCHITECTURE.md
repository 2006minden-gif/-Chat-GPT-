# Stage 9 recovery — каталог, брифы и заказ

## Зависимости и границы

Ветка `feature/stage-9-completion` построена поверх Stage11/Stage12 assessment (`e23d86d`, app baseline `ba473cb`). Это восстановление пропущенной зависимости, не пересборка сайта и не deployment в main. Аудит существующего кода: [STAGE-9-GAP-REPORT.md](STAGE-9-GAP-REPORT.md). Исходный приложенный текст обрывается в разделе5; отсутствующие правила не выдумываются.

Повторно используются Stage4 accounts/session/consent, Stage5 CRM effects/conversion, Stage6 storage/documents/customer decisions, Stage7 invoice/payment pages, Stage8 pricing/AI queue, Stage10 production sources и Stage11 shared navigation. Нового калькулятора, order/account database, AI provider/dispatcher, Codex API или deployment mechanism нет.

## Схема 013_service_ordering

001–012 не изменены. 009 уже занят AI automation; recovery использует следующий свободный номер013, а не переписывает историю.

Восемь аддитивных таблиц:

- `nd_catalog_templates` / `nd_catalog_template_versions`: mutable registry + immutable body/checksum/публикация версии.
- `nd_catalog_services` / `nd_catalog_service_versions`: стабильный slug, текущая draft head и отдельная опубликованная revision; snapshot включает ссылку на точную редакцию анкеты.
- `nd_catalog_requests`: scoped customer/account, draft answers/files/consent, версии и ссылки на существующие project/lead/deal/order.
- `nd_catalog_briefs`: неизменяемые submitted revisions, буквальные ответы, структурированный brief/checksum, exact spec revision, consent time/version/hash.
- `nd_catalog_offers`: exact brief/quote/spec/proposal/package/version snapshots, owner publish и customer acceptance, expiry/approved deadline.
- `nd_catalog_scope_transitions`: неизменяемые доказательства трёх разрешённых lifecycle-переходов pricing scope.

MySQL5.7/InnoDB/utf8mb4, FK типов существующих таблиц (admin TINYINT, lead INT, остальные BIGINT), unique service/template revision, один project/lead/deal/order на request и одна CRM conversion на deal. Нет JSON_TABLE/CTE/MySQL8-only CHECK. Mutable rows — version checks и locks; published content/price/calculations не переписываются.

CLI `scripts/migrate-catalog.php status|up|down`: exact checksum dependency012, advisory lock, strict SQL, journal/progress, отказ unmanaged/partial tables, empty-only reverse rollback. Down не удаляет заполненные таблицы и не запускается автоматически. Миграция ничего не публикует, не создаёт услуг/цен/юридических текстов, не касается production.

## Каталог и анкеты

Семь категорий: сайт, лендинг, webapp, AI agent, CRM, automation, integration. Данные услуги задаёт владелец: название/описание, scope/deliverables, estimate/fixed pricing, 1–8 packages, Telegram consultation URL, точная опубликованная template version. Пакеты содержат внутреннюю оценочную модель; public projection исключает work packages/quantity rules/owner costs.

Опубликованный snapshot не меняется при сохранении нового draft. Publish требует version/checksum/owner confirm. Unpublish/archive закрывают новые действия; исторические собственные briefs/offers остаются читаемыми. Несохранённый JSON не может быть опубликован нажатием кнопки старой редакции. Шаблоны задаются в CRM (JSON schema editor + generic step/question constructor), не hardcoded questionnaires в JS.

Анкета: 1–8 steps, до30 вопросов, text/textarea/number/choice/multi/bool, semantic section, required/bounds/options. `when:{field,equals}` ссылается только на предыдущий вопрос и типизированное значение: нет JS expressions/eval/циклов. Hidden answers очищаются/отвергаются сервером; неизвестные поля и недопустимые значения отвергаются. Boolean в UI не считается ответом «Нет» до явного выбора.

Saved draft — только authenticated customer и отдельное unchecked consent. Ответы до20KiB и суммарный человекочитаемый brief до8500 символов; up to20 submitted revisions. Multi-step review перед submit, explicit server save/resume, безопасное предупреждение при уходе с несохранёнными правками. HTML/non-JSON не выдаётся за успех и не очищает поле.

Attachments используют существующий private Stage6 upload/download, project ownership, MIME/extension/quota/size checks и idempotency. Нет собственного распаковщика/исполнения вложений. Чужой project/file ID отклоняется, даже когда оба проекта принадлежат одному клиенту. Пароли/ключи/платёжные реквизиты не должны попадать в брифы/вложения.

## Общий business flow

1. Public читает только owner-published service data; консультация по configured Telegram. Order entry показан только при действующих auth/privacy/collaboration flags.
2. Existing verified customer создаёт DRAFT. Создаётся planned CRM project для pricing/files; заказа ещё нет. Отдельный consent version/hash/time сохраняется до приёма ответов.
3. Save — optimistic version + idempotency. Submit валидирует всю анкету/файлы/политику, формирует literal sections goal/functionality/integrations/design/deliverables/budget/deadline/other, missing information и пустой список неподтверждённых assumptions. Бюджет/желаемый срок не становятся обещанием.
4. Первая отправка создаёт одну nd_leads, nd_lead_customers relation и существующую deal; CRM customer/account не дублируются. Следующая редакция сохраняет эти IDs и историю. Создаётся Stage6 draft specification; scope и acceptance — из owner-configured service и actual brief.
5. Автоматически вызывается общий pricing engine на package model/typed quantity rules. Время проверки и исправлений владельцем добавляется явно как labor work packages. Null остаётся unknown и даёт NEEDS_COST_REVIEW. На вопросах нет свободного формульного языка, валютный курс/налоги/ставки не выдумываются.
6. Если уже включены AI + approved data processing + ai_pricing_auto_enabled, ставится существующий cost_estimator task с immutable brief key. Provider credentials не нужны для deterministic path. AI output лишь оценка (uncertain=true), не approve. В контекст передаётся redacted bounded brief как untrusted data; модель не получает config/secrets. Без provider разрешён profile-based estimate, без достаточных исходных данных — review. Неуспех estimator после commit не отменяет сохранённый request, технический metadata лог приватный.
7. Owner открывает существующий pricing component (rates/decimal arithmetic/contingency/tax/overhead/minimum margin) в catalog CRM. Тот же `pricing_dispatch`, без AI gate для детерминированной математики. Owner может approve/edit/recalculate/reject, каждая цена immutable. При наличии артефакта existing proposal agent его можно включить в draft только для matching project/approved quote.
8. Owner prepares draft commercial proposal с exact brief/price/spec/package/terms/expiry и опциональным одобренным сроком. Stage6 description служит proposal document; новая разновидность документов/новый approval engine не создаются. Customer не видит DRAFT offers.
9. Owner publish проверяет exact checksum, latest approved fresh quote, текущую service/template и spec; переводит точные Stage6 spec/proposal в sent и создаёт существующие customer approval requests. Никакой auto-send до owner publish.
10. Customer accepts exact offer + ТЗ; reused `cc_decide_effect` сохраняет обе настоящие Stage6 decisions. Это ACCEPTED, ещё не заказ. Отдельный confirm использует существующий CRM convert effect, creates one order, подтверждает его и связывает planned project. Независимые concurrent PHP processes проверяют один order effect.
11. Статусы/цены/сроки перепроверяются, history фиксирует действительного customer actor. Новая редакция до confirm supersedes прежний offer и требует re-estimate/reapproval. Cancel до order закрывает project и deal, сохраняет историю. Подтверждённый/уже созданный владельцем order отменяется через существующий owner CRM workflow; финансовые записи не удаляются.
12. Stage7 billing доступен по существующей странице при включённом модуле, без автоматической оплаты/возврата. Stage10 получает real catalog customer acceptance evidence; sandbox/AI execution остаются отдельными ограничениями, не считаются готовыми этим этапом.

## Price freshness без ложных инвалидизаций

Existing pricing_scope включает project/order versions и spec statuses. Нормальное publish → acceptance → confirmation меняет их после одобрения цены. Общую проверку не отключаем.

Server транзакционно сохраняет ровно три перехода: PUBLISHED, ACCEPTED, CONFIRMED, from exact original quotation scope hash → actual post-transition hash. `pricing_fresh` допускает только exact mapped hash для того же offer/brief/approved quote и актуальной request revision. Проверки latest rates/policy продолжают работать. Изменение description/version/нового spec/rate/policy не совпадает с binding и требует re-estimation. Старый quote JSON не редактируется. Это узкий lifecycle adapter, а не игнорирование версий.

Bound Stage6 documents/decisions нельзя менять generic cc mutation endpoint в обход catalog exact workflow. Guard сначала проверяет object ownership, поэтому чужой ID остаётся404. Общие Stage6 документы вне catalog работают как раньше.

## API

Public GET `/catalog-api.php?r=services[&page=N]`, `services/{id}` — только read-only published projection. POST возвращает405.

Owner `/api.php?r=crm/catalog/`; customer `/customer-api.php?r=catalog/`. Существующие session/CSRF/origin/privacy/active-account checks, rate limits и bounded20 rows pages. Все изменения POST с request_key; версии обязательны там, где mutable state меняется.

- GET `services`, `templates`, `{kind}/{id}` — owner version history.
- POST `{services|templates}[/id]/{save|publish|unpublish|archive}` — owner only; save body + template_version_id/slug, mutations version/confirm/checksum.
- GET `requests`, `requests/{id}` — owner или owning customer; customer projection не включает registry/calculation/internal AI tasks.
- POST `requests` — customer draft + service_version_id/package_key/consent/policy_version.
- POST `requests/{id}/{save|submit|revise|cancel|confirm}` — typed answers/file_ids and version; explicit consent for save/submit, confirm for state decisions.
- POST `requests/{id}/{estimate|offer}` — owner model/re-estimate or draft proposal (terms/expiry/optional deadline/artifact).
- POST `offers/{id}/publish` owner; `offers/{id}/accept` customer — exact checksum/version/confirm.
- Owner `pricing/*` delegates **existing** shared pricing routes. Customer denied403.

## UI, limits и release

`catalog.php/js/css` — public; `ordering.php/js` — customer; `catalog-owner.php/js` — CRM/templates/briefs/proposals. Shared pricing.js reused, AI link hidden when disabled. Stage11 navigation and homepage link are feature-gated; Stage10 availability reflects real adapter.

Default flags false: `catalog_enabled`, `catalog_requests_enabled`, `catalog_privacy_approved`. Neither policies, rates, service publication, live payment, AI provider, scheduler nor production flags were activated. All fixtures synthetic. Retention/business/legal review, live email/provider/payment/sandbox остаются отдельными prerequisites.

Deployment architecture/allowlists/operators неизменены по scope. Старый artifact не включает эти public/private modules и не умеет unattended013. Автоматическое разрешение владельца действует, но mandatory release gates FAIL до отдельного исправления существующего механизма. Успешный CI не означает deployment этого кода.
