# Stage 11 — сквозные сценарии

VERIFIED здесь означает локальное PHP/MySQL HTTP/browser выполнение с синтетическими данными. Test transport — отдельный признак, не live интеграция. Общий customer journey пока BLOCKED: Stage9 отсутствует. Нельзя сложить отдельные PASS и назвать полный путь пройденным.

| Сценарий | Источники тестов | Результат/граница |
|---|---|---|
| A: каталог → brief → lead | `test_prelaunch`, `api-client.test.cjs` | форма/consent/DB persistence/idempotency/non-JSON VERIFIED; каталог/interactive brief MISSING, полный A BLOCKED |
| B: registration/verify/login/logout/reset/isolation | `test_customer_auth`, `test_customer_migrations` | VERIFIED с локальным email transport, live email NOT_VERIFIED |
| C: CRM customer/deal/order | `test_crm_operations`, `test_ai`, `test_pricing` | реальные CRM CRUD/transitions/convert/idempotency VERIFIED; structured brief/offer acceptance Stage9 MISSING, полный C BLOCKED |
| D: deterministic estimate/owner exact price | `test_pricing`, browser `test_ai` | VERIFIED synthetic rates/decimal math/unknown review/immutable version; живое коммерческое предложение не отправлялось |
| E: order/project/stages/tasks/dashboard | `test_crm_operations`, `test_production` | VERIFIED через реальные PDO/API; production writes не выполнялись |
| F: messages/files/document/revise/approve | `test_collaboration` | VERIFIED scoped HTTP/browser/private files/history; hosting storage NOT_VERIFIED |
| G: invoice/payment/refund | `test_billing` | local HTTP provider mock + real application DB state VERIFIED, live payment NOT_VERIFIED/не активирован |
| H: AI orchestration | `test_ai`, `test_production` | mock-only inference, реальные contracts/tasks/history/approval/budgets VERIFIED; live AI NOT_VERIFIED |
| I: ручная передача | `test_system_integration` | real clipboard/import/check/approve/Stage6 delivery без AI credentials VERIFIED для статических документов; код BLOCKED/NOT_TESTED без sandbox |

## Ручной путь подробно

`/handoff.php#new` → существующие project/task IDs + принятая Stage6 spec revision → owner confirm → copyable redacted assignment → ручной перенос во внешнюю среду владельцем → JSON-импорт текущей версии → серверная проверка → точное одобрение → отдельная передача через Stage6. Никакой автоматический Codex вызов не выполняется и в тестах не изображается.

Автотест проверяет clipboard и импорт подготовленного синтетического JSON, а не реальную работу владельца в Codex. Это честная граница: внешний ручной шаг остаётся owner acceptance. `files` содержит `{path,content,kind}`, `requirements` — `{id,file,method,expected}` для всех строк критериев принятого ТЗ R1..Rn. `installation.md` и `limitations.md` обязательны для PASS. Файлы кода можно импортировать только как неисполненные данные, QA заблокирует техническую передачу без реальной среды.

Кнопки: «Подготовить задание», «Скопировать задание», «Загрузить результат», «Отправить на проверку», «Утвердить результат», «Запросить доработку», «Передать клиенту». Доступны только в соответствующем состоянии. Отдельный file input читает локальный JSON, серверный импорт подтверждается собственной кнопкой. Ошибка/HTML вместо JSON сохраняют поле; пока запрос выполняется, повторный submit блокируется. Статусы и file checksums реальные, прогресс не выдумывается.

Недоступный/недействительный источник, archived/cancelled task/project/order, чужой customer, CSRF, stale version/hash, неполный/опасный файл, duplicate transmission проверяются API. Новая редакция не перезаписывает старый результат и заново требует проверки/решения. 20 редакций на задание — ограничение, новый цикл требует нового задания. Статусы заказов/счета/цены этот маршрут автоматически не меняет.
