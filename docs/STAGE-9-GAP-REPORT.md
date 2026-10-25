# Stage 9 recovery — аудит разрывов

Основа: `release/stage-12-gate-report e23d86d` (цепочка Stage3–8/10/11); main `478ca7f`, не обновлялся. Stage12 проверка закончилась RELEASE_BLOCKED: старый release allowlist и migration operator не поддерживают интегрированное приложение. Эти ограничения не обходятся и CI/CD не меняется при восстановлении Stage9.

Проверены remote branches, исходники public/private/database/tests и существующие отчёты. Отдельной Stage9 ветки/исходной полной спецификации не найдено. Последнее приложенное задание обрывается после пункта 5.3; сохранённые разделы 1–4 определяют реализуемый объём. Это не основание выдумывать недостающий текст.

| Область | Уже есть | Реальный разрыв / решение |
|---|---|---|
| Услуги | секция лендинга, конфигурационный AI service list | нет управляемого опубликованного каталога; добавить версионирование/owner publish без фиктивных цен/seed услуг |
| Бриф | контактная форма и project description | нет template builder/conditional steps/drafts; добавить scoped authenticated questionnaire, версии и неизменяемый submitted snapshot |
| Клиент | Stage4 accounts/login/consent/session | повторно использовать, не создавать второй аккаунт или анонимную очередь персональных данных |
| Стоимость | Stage8 pricing/decimal-safe registry/policy/quotations/owner approvals | не дублировать calculator; связывать submitted brief/project с существующим estimator, unknown→NEEDS_COST_REVIEW |
| Предложение | Stage8 proposal agent + Stage6 versioned documents/approvals | добавить exact quote/brief/spec/package binding и отдельное owner publish; reuse existing customer decisions |
| CRM | leads/customers/deals/orders/projects и идемпотентная deal conversion | связать request с этими записями, без параллельной базы заказов |
| Оплата/файлы | Stage6 private uploads + Stage7 invoices | reuse scoped storage/billing; не включать live payments |
| Production | Stage10 prod_stage9_evidence только loopback test adapter | добавить реальное доказательство exact customer acceptance, сохранив mock только для старых тестов |
| Freshness | pricing_fresh строго сравнивает scope/version/status | acceptance/order confirmation сами меняют эти версии; требуется узкий, проверяемый lifecycle binding без отмены material-change/rate checks |
| UI | Stage11 shared navigation с честным unavailable | подключить реальные catalog/request страницы по default-off flags, убрать unavailable только при доступном модуле |

Новые таблицы — только catalog/template/request/brief/offer bindings; authoritative financial/order/auth tables не дублируются. Миграции 001–012 неизменяемы, следующий свободный номер **013_service_ordering**. Stage9 не должен получать старый номер009, занятый AI orchestration.

Ветка восстановления `feature/stage-9-completion`. Все записи/проверки — в изолированных synthetic DBs. Production flags, credentials, privacy texts, deployment mechanism, billing activation остаются без изменений. Отсутствующий provider не изображается работающим: сохраняется request, создаётся честный NEEDS_COST_REVIEW; AI задача ставится только при уже разрешённой конфигурации, без новых ключей и API Codex.
