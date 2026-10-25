# Обязательный контракт цены для Stage 8, 9 и 10

Архитектурное дополнение реализовано в текущем Stage 8. Следующие Stage 9/10 не начинались и не считаются одобренными; они обязаны переиспользовать этот модуль, а не вводить второй калькулятор или обход approval.

## Инварианты

1. AI quantity estimates ≠ rates ≠ deterministic price ≠ owner-approved final quotation ≠ sent proposal.
2. Работы выполняет один владелец; сотрудники и многоступенчатое согласование не нужны.
3. Нет обязательного числа → NULL и NEEDS_COST_REVIEW. Явный подтверждённый ноль — известный нулевой расход, не missing data. Нет fictitious price/rate/FX/tax defaults.
4. Все окончательные значения рассчитывает/проверяет PHP. AI packages schema не принимает unit prices, discounts, margin/tax overrides или approval.
5. APPROVED quote bound to exact checksum, immutable calculation/inputs/scope/rate/policy versions, owner ID, decision timestamp/reason. Price editing — новая quotation revision, старый calculation не меняется.
6. Изменение scope/specification/order version, действующей ставки/валюты/validity или policy делает snapshot stale для будущей отправки. Новая редакция + новое одобрение обязательны. Уже отправленное сообщение/договорная цена не переписываются.
7. Финансовые commitments/discounts/deadlines не отправляются автоматически. Proposal generation требует approved fresh quote; send approval дополнительно связывает quote ID/hash и exact text/target versions. Проверка повторяется при approval и непосредственно при apply.
8. Неизвестные actual provider costs не объявляются нулём. Исторические данные не меняют опубликованные цены, ставки или пороги без нового явного решения владельца.

## Реестр затрат

Owner API `pricing/rates`: immutable category revisions, decimal string value, currency, source, source_date, valid_from/valid_until. Labor hour (development/testing owner time), model input/output per 1000 tokens, hosting month, paid-tool/external/other unit, payment fee percent. Sources/validity хранятся вместе с точными значениями, а не заменяются model guesses.

RUB/USD/EUR rates можно хранить с источником. Current project engine/cabinet invoicing работает в RUB. Foreign rate не пересчитывается молча: NEEDS_COST_REVIEW до owner-verified RUB rate/conversion basis. Automated FX не реализован; нельзя складывать разные валюты.

`pricing/policy`: versioned owner-approved contingency, desired gross-price margin, minimum gross-price contribution threshold, overhead allocation from direct cost, effort calibration factor (100% identity default), tax treatment/source. Supported tax treatments: unknown, explicitly none with zero, explicitly approved fixed share of gross price. Это не универсальный VAT/fiscalization engine. Сложный/непроверенный режим → unknown/review, без юридических обещаний.

## Рекомендация и формулы

Cost estimator получает brief/project description, limited authorized discussion/requirements и возвращает packages с development/testing hours, estimated AI input/output tokens, hosting/tool/external/other quantities, risk, uncertainty и basis. Количества nullable; модели не разрешено создавать ставки или final prices. Owner может уточнить только недостающие/ошибочные величины, не собирать весь расчёт заново.

Backend использует signed 64-bit integer arithmetic с проверкой границ, RUB minor units, quantities в тысячных. Currency money precision=2; quantity precision=3. Products округляются half-up до копейки. Owner effort factor применяется к labor quantities; он меняется только новой одобренной политикой.

- Direct cost = сумма строк `quantity × valid registry rate` (AI rates per 1000 tokens).
- Overhead = ceil(direct × overhead_bp / 10000).
- Contingency = ceil((direct + overhead) × contingency_bp / 10000).
- Cost pool = direct + overhead + contingency.
- Recommended price = ceil(cost pool × 10000 / (10000 − fee_bp − tax_bp − desired_margin_bp)), с корректировкой копеек для достижения целевой маржи после округления fee/tax.
- Expected contribution = selling price − fee − tax − cost pool.
- Минимум проверяется как `contribution × 10000 >= price × minimum_bp` без float.

Nonpositive denominator, missing/expired rate, unsupported currency conversion, unknown quantity, insufficient requirements, unapproved tax/policy → NEEDS_COST_REVIEW. Owner price below minimum/negative expected profit нельзя одобрить: нужны новая цена или явно новая policy. Нулевой полностью известный бюджет допускает явное owner approval бесплатного проекта; Stage 7 zero-amount invoice не реализован и не создаётся автоматически.

Контингентный резерв — консервативная часть ожидаемых затрат, не фактически потраченные деньги и не бухгалтерская прибыль. В интерфейсе видны все компоненты/количества/rate source/version/validity, полный calculation и uncertainty warnings. При утверждении оценок/рисков требуется отдельное подтверждение, не preselected checkbox.

## Версии и действия

- Cost estimate versions: immutable packages, provenance ai/owner, artifact link, scope hash. Owner package corrections создают новую estimate + quote.
- Quote versions: immutable calculation/checksum, estimate/policy/rates, replaces_id; lifecycle DRAFT / NEEDS_COST_REVIEW / APPROVED / REJECTED.
- **Одобрить:** authenticated owner, exact checksum, current scope/rates/policy, acceptable profitability, reason, explicit acceptance of estimates.
- **Изменить цену:** новая revision с owner_requested_price и повторным серверным расчётом налогов/комиссии/доходности, не bypass minimum.
- **Запросить пересчёт:** новый calculation по текущим rates/policy; scope change требует нового AI estimate (доступна ссылка с project context).
- **Отклонить:** отдельное owner decision, исходные данные сохраняются.

Automatic mode `ai_pricing_auto_enabled=false` default. После явного approval/config/scheduler worker сканирует проекты по persistent cursor, до 20 за раз, создаёт idempotent cost-estimator task по scope hash. Same scope не создаёт второй job. Material rate/policy change создаёт новую неутверждённую quotation revision, retaining prior owner override as explicit input where present. Никакой final approval/публикации/изменения order total автоматически нет. Unconfigured provider/agent/quotas не дают вымышленной рекомендации; pending/NEEDS_HUMAN/NEEDS_COST_REVIEW остаются видимыми.

## Post-project actuals

После completed project owner подтверждает total actual cash expenses **включая налоги и комиссии**, development/testing hours и источник. Это новые dated snapshots, а не переписывание estimate/price. Contribution after actual = approved selling price − actual total; повторного вычитания fee/tax нет. Cost delta сравнивается с estimate cost pool + expected fee + expected tax на сопоставимой основе.

Insights используют последние owner-confirmed actual snapshots (до 100 quotations), показывают sample size/cost delta и suggested effort factor. Это не statistically calibrated prediction. Поправка не применяется: owner должен явно принять новую pricing policy и указать basis. Старые опубликованные цены и minimum profitability threshold не меняются.

## Контракты для будущих этапов

Stage 9: quote-to-order/proposal integrations должны принимать только trusted quotation ID/checksum, проверять current approval/scope, не копировать browser/model price. Existing Stage 7 human billing остаётся отдельным workflow; автоматический invoice/refund через AI запрещён. Нельзя смешивать согласованный offer и фактическое capture/settlement.

Stage 10: расширенные автоматизации/обучение на исторических результатах обязаны читать actuals с owner provenance, предлагать новый estimation rule, не менять policy/rates/thresholds или published prices сами. Любой новый effect должен пройти тот же permission/approval boundary; эта документация не разрешает выполнение Stage 9/10, migrations или production activation.

## Owner-only API

`/api.php?r=crm/ai/pricing/`:

| Route | Назначение |
|---|---|
| GET rates / POST rates | История/добавление valid immutable rate revision |
| POST policy | Новая явно проверенная owner policy |
| POST projects/ID/estimate | Уточнённые owner packages → versioned estimate/quote |
| GET quotes / quotes/ID | История/полный расчёт, freshness, actuals |
| POST quotes/ID/edit / recalculate | Новые revisions, checksum bound |
| POST quotes/ID/approve / reject | Owner exact decision, confirm/reason |
| POST quotes/ID/actuals | Completed project, owner-attested actual expenses/effort |
| GET insights | Historical suggestions, applied=false |

CSRF/origin/rate/idempotency — существующий gateway. Customer/public не имеют доступа к registry, margins или pricing decisions. Customer final proposal видит только после отдельного exact owner approval/send. Repositories не содержат фактических ставок, секретов или merchant tax settings.
