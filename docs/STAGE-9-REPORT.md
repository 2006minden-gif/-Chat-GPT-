# Stage 9 completion — отчёт восстановления зависимости

Дата: 25.10.2026. Ветка `feature/stage-9-completion`, база `e23d86d` (код Stage11 `ba473cb`, плюс Stage12 release assessment). Main/production не обновлялись. Прежние отчёты, где Stage9 отсутствовал, описывают свои исходные SHA; этот документ фиксирует результат восстановления в отдельной ветке.

## Выполнено

- Проверены реальные branches/routes/schema и повторно использованы уже существующие costing/auth/CRM/documents. [Gap report](STAGE-9-GAP-REPORT.md) объясняет, что было найдено и чего не хватало.
- Управляемый public catalog: семь категорий, owner-defined scope/deliverables/pricing/packages/consultation, immutable versions, create/edit/save/publish/unpublish/archive. Нет initial published services/approved prices/seed rates.
- CRM questionnaire editor с generic step/question constructor и JSON schema, conditional typed fields, versioned templates. Frontend получает конфигурацию с сервера, не hardcoded questionnaires.
- Scoped authenticated customer drafts, save/resume/review, consent time/version/hash, private attachments через Stage6. Автоматический structured brief сохраняет actual answers, missing information и не добавляет подтверждённых выдуманных требований.
- Автоматический recommended quote по owner-configured work model и typed quantities через общий Stage8 pricing engine/registry/policy, включая owner review/corrections. Unknown/null→NEEDS_COST_REVIEW, никогда скрытый ноль. Тот же owner approve/edit/recalculate/reject UI доступен без AI feature/provider.
- Optional existing cost_estimator/proposal agent reuse. AI task создаётся лишь при прежних approved flags; AI quantities помечаются estimates/uncertain, не approve. Live inference не подтверждён; реальный provider не подключался. Расчёт по профилю — не выдаётся за выполненный AI-анализ.
- Exact commercial proposal draft → отдельный owner publish → customer acceptance через настоящие Stage6 spec/proposal decisions → отдельный customer order confirm. Используется существующая CRM conversion, не новый order engine.
- Immutable quote/brief/spec/package binding и узкий lifecycle adapter для pricing freshness. Material scope/rate/policy changes по-прежнему инвалидируют цену. Generic Stage6 mutation route не обходит catalog decisions; ownership проверяется до guard.
- Cabinet history/requests/briefs/offers/orders/projects, Stage11 navigation/homepage entry, Stage10 real accepted-offer source, существующий Stage7 invoice flow. Для Stage10 по-прежнему нужны verified rates/approved plan/provider/sandbox в пределах его исходных ограничений.
- CRM activity правильно различает customer actor и owner; cancel pre-order закрывает deal/project без удаления истории. Concurrent confirm создаёт ровно один existing CRM order.

## Файлы и миграции

`private/catalog/{contracts,core,manage,requests,offers,read,routes,bindings}.php`; `public/{catalog,ordering,catalog-owner}.{php,js}` + `catalog-api.php`, `catalog.css`; `database/migrations/013_service_ordering/{up,down}.sql`, `scripts/migrate-catalog.php`; `tests/test_catalog.py`, `test_catalog_migrations.py`.

Небольшие интеграционные изменения: `private/{customer-auth.php,config.example.php,product-navigation.php}`, `private/crm/{core,routes,write}.php`, `private/collab/{routes,approvals,documents}.php`, `private/pricing/{core,engine}.php`, `private/ai/context.php`, `private/production/{core,routes}.php`; `public/{index.php,operations.js,pricing.js,production.js,collaboration.js}`, test router.

013 создаёт8 additive binding tables. 001–012 не изменены. MySQL5.7 tested; exact dependency012/checksum/strict mode/journal/partial recovery/advisory locks/empty-only rollback. Production SQL не выполнялся. Empty down не является разрешением удалять живые данные: непустой down отказывает, code rollback должен сохранять данные и выключать feature flags.

Основные source commits: `7edc2cc` — backend/schema/source bindings; `6b67391` — full UI/pricing/permissions/extended tests; отдельные завершающие commits — invoice regression/spacing и документация. История main/ранних PR сохранена.

## Проверки — выполнено реально

- Полный Python regression: **300 tests PASS**, 296.448 с на предыдущем checkpoint; до него298 PASS, 275.568 с. Итоговый повтор после последних guard/UI интеграционных изменений: **300 tests PASS, 285.206 с**. Последнее правило whitespace-only required отдельно перепроверено в полном catalog/migration наборе22 PASS (43.164 с).
- Итоговый catalog/migration набор **22 tests PASS**, 43.164 с (также48.620 с на предыдущем checkpoint) (предыдущий checkpoint20 PASS, 36.639 с): условные ответы, drafts, consent/CSRF, ownership, service versions, price freshness, generic approval bypass, concurrent confirmation в независимых PHP processes, deterministic no-provider flow, mock AI task orchestration, expiry/cancel, owner unsaved-publish protection, migrations/recovery.
- После добавления отдельной Stage7 cross-module проверки **1 invoice integration test PASS**, 3.133 с. После добавления защиты owner-linked project и нового regression текущая suite содержит300 тестов. Результат GitHub отмечается отдельно по exact head SHA, не выдумывается.
- После CSS spacing отдельно повторён реальный browser journey **1 PASS**, 7.825 с: catalog → customer brief → owner quote approval → owner proposal publish → customer acceptance → confirmed order. В актуальном тесте проверены save/resume после reload, unchecked consent, unexpected HTTP200 HTML без false success, сохранность ответов, mobile390px и pageerror.
- PHP8.4.27 lint **105 файлов PASS**, JS syntax **18 файлов PASS**, Node **12/12 PASS**. Real MySQL5.7.42, Apache2.4.69, Chromium/Playwright; только random loopback neuro_test_* DBs.
- actionlint, existing release policy check, compileall, git diff --check — PASS. Gitleaks текущего дерева: утечек не найдено; не повторный full-history audit.
- AI/provider transport в новом optional-AI тесте — только controlled HTTP mock; подтверждены настоящие queue/task/contract/quotation DB effects, не live inference. Billing integration создаёт/выставляет только synthetic invoice, payment attempts остаются0; настоящих финансовых транзакций нет.

Прогоны: existing `python -m unittest discover -s tests -p 'test_*.py' -q`, targeted `-p 'test_catalog*.py'`, browser/invoice `-k test_12` / `-k test_18`, `node --test tests/api-client.test.cjs`, PHP/JS syntax и release policy tools. Loopback DSN `mysql:host=127.0.0.1;port=33078`, PHP/APACHE executables из изолированного test runtime. Production credentials не использовались.

Неуспешные промежуточные проверки не скрываются: browser обнаружил недоступное точное label select, исправлены aria-label и лишняя перерисовка; затем overly broad locator ожидал один из двух подтверждённых статусов — уточнён только selector. В новом invoice test первый payload не содержал обязательную дату счёта, fixture исправлен по фактическому API. Также закрыты owner-prelinked order (никакого второго заказа), omission unknown owner time в AI результате (остаётся NEEDS_COST_REVIEW), а связанные Stage6 документы показывают переход в catalog workflow вместо generic decision buttons. После исправлений проверки исполнены повторно. Никакие security guards не снимались для зелёного теста.

## End-to-end статус

| Путь | Результат |
|---|---|
| Public configured catalog → authenticated conditional brief | VERIFIED локально PHP/HTTP/browser |
| CRM lead/customer/deal/project linkage | VERIFIED, existing customer IDs, без автоматического merge отдельных запросов |
| Recommended cost/price → owner exact approval | VERIFIED synthetic configured profiles/rates, deterministic shared engine |
| Optional AI estimation/proposal | mock orchestration VERIFIED; live provider NOT_VERIFIED |
| Owner publish → customer exact acceptance → confirmed order | VERIFIED API/browser/concurrent processes |
| Order → existing issued invoice/customer isolation | VERIFIED isolated synthetic invoice, no payment attempt |
| Confirmed catalog order → Stage10 plan source | VERIFIED real catalog_customer_acceptance adapter, без loopback acceptance fixture |
| Runtime execution/customer-code deployment | NOT_VERIFIED/BLOCKED, sandbox отсутствует |
| NeuroDelo production deployment | RELEASE_BLOCKED, не выполнялся |

## Ограничения и безопасность

Все новые flags false по умолчанию: catalog_enabled/catalog_requests_enabled/catalog_privacy_approved. Пользователь не должен передавать секреты/платёжные реквизиты в свободном тексте. Existing policy/consent checks не ослаблены; реальная privacy/commercial/retention правовая проверка остаётся owner decision, не заявляется автоматически пройденной. Scope/budget пожелания не превращаются в обещания срока или цены.

CRM editor — advanced JSON schema/config editor с generic helper controls, не визуальный drag-and-drop конструктор. Количественные rules — прямые typed mappings, не произвольные формулы. Unknown provider не заменяется выдуманным AI-результатом. Модели затрат, реальные ставки, scope и условия публикует/одобряет владелец; отправка и принятие версионные. Срок offer в UTC задаёт владелец, максимум90 дней; изменение service/template закрывает новые submission/acceptance для устаревшей публикации, старые записи сохраняются. История ограничена страницами/20 brief revisions, автоматического удаления и юридической retention policy нет.

No production tests/customer writes, live emails/payments/AI, new secret services, employee accounts, Codex API, deployment automation changes. Existing Stage12 release blocker сохраняется: старый пакет/remote allowlist не включает новые runtime modules и unattended operator не поддерживает013. Автоматическая авторизация владельца на обычные релизы действует, но FAIL mandatory gates не обходится. Не сливать эту ветку в автоматически публикуемый main с неполным пакетом.

## Материалы

[Архитектура/API](STAGE-9-ARCHITECTURE.md) · [Проверка владельцем](STAGE-9-OWNER-CHECKLIST-RU.md) · [Примеры конфигурации](stage-9-examples/) · [Customer mobile](stage-9-ux/customer-confirmed-mobile.png) · [Owner proposal](stage-9-ux/owner-offer.png).

Следующая безопасная работа — review/интеграция восстановленной зависимости в Stage11 test branch и отдельное исправление текущего release mechanism по Stage12 gates. Не новый deployment framework, не автоматическое применение SQL в этом задании. Дополнительный per-release confirmation не запрашивался.

## GitHub review

Ветка опубликована в origin. Создание draft PR через GitHub API вернуло `Forbidden`; git read/push работают, защита и deployment настройки не менялись для обхода ограничения. Подготовлено [сравнение Stage11 integration → Stage9 completion](https://github.com/2006minden-gif/-Chat-GPT-/compare/integrate/stage-11-system...feature/stage-9-completion?expand=1): можно выбрать **Create draft pull request**, base `integrate/stage-11-system`. Diff включает Stage12 documentation-only assessment из родительской истории, без изменений automation. Это открытие review, не per-release confirmation и не разрешение обхода технических gates. Main merge/deploy не выполнялись.
