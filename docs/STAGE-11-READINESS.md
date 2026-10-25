# Stage 11 — готовность к запуску

**Общий статус: NOT_READY.** Это не отменяет готовности безопасных исходников Stage11 к review владельца. Локальный тест не подтверждает production deployment.

| Категория | Статус | Условие |
|---|---|---|
| Website/contact form | VERIFIED изолированно | production privacy approval и корректный config обязательны |
| Core CRM/projects/tasks | IMPLEMENTED / VERIFIED изолированно | отдельная интеграция Stage3–6 PR и выпуск |
| Customer auth/permissions | IMPLEMENTED / VERIFIED test email | live SMTP, policy/retention review и acceptance |
| Documents/messages/files | IMPLEMENTED / VERIFIED изолированно | hosting private FS/quota/access проверить перед выпуском |
| Catalog/brief/offer acceptance | MISSING / BLOCKED | Stage9 не существует в доступной цепочке |
| Pricing | IMPLEMENTED / VERIFIED synthetic rates | реальные ставки/налоги/накладные/минимальная прибыльность утверждает владелец |
| Billing/notifications | PARTIALLY_IMPLEMENTED | mock verified, реальные merchant/SMTP не активированы |
| AI orchestration | PARTIALLY_IMPLEMENTED | mock verified, provider optional, live NOT_VERIFIED |
| Production Stage10 | PARTIALLY_IMPLEMENTED / BLOCKED | Stage9 evidence, sandbox/worker отсутствуют |
| Manual handoff | IMPLEMENTED / VERIFIED локально | без Codex API; ручной внешний шаг проверяет владелец, технически непроверенный код не передаётся как готовый |
| SQL | VERIFIED MySQL5.7 изолированно | additive012, checksum/order/empty rollback; production SQL не запускался |
| Security/privacy | VERIFIED regression boundaries | production operational audit/правовые документы/retention NOT_VERIFIED |
| Performance | локально измерено | реальные hosting/нагрузка NOT_VERIFIED |
| Deployment/rollback | BLOCKED | отдельные approval/backup restore/complete package; CI/CD не менялся |

## Блокеры и порядок действий

1. Review цепочки Stage3/4/5/6/7/8/10/11 без автоматического merge незавершённых PR. Stage11 ветка уже содержит их совместимую историю; это не интеграция в production main.
2. Определить продуктовый объём: полный customer journey требует Stage9. Ручной маршрут по существующей задаче и принятому ТЗ не заменяет каталог, brief, accepted offer или commercial approval.
3. Утвердить privacy/legal тексты, consent versions, retention/deletion и разрешённый перенос данных во внешнюю среду. Не включать flags ради обхода этого условия.
4. Для соответствующих live-функций отдельно проверить SMTP/merchant/provider/sandbox/scheduler. Для ручного copy/import Codex API и новые AI keys НЕ нужны.
5. Отдельно проверить deployment allowlist новых public/private файлов и `product-navigation.php`, подготовить exact SHA bundle, backup и проверенное восстановление, последовательность миграций до012 и совместимый code rollback. Текущее CI build старого allowlist не означает полный Stage11 release.
6. Только после явного разрешения выполнить staging/hosting acceptance: HTTPS/Apache/PHP extensions, private sibling access, protected storage, реальные logs/health, DB/connectivity, owner login, setup removal/backup URL restrictions. Stage11 production не подключает и не меняет.
7. Владелец выполняет `STAGE-11-OWNER-CHECKLIST-RU.md`. Без этих подтверждений статус NOT_READY не повышать.

Входной production baseline не перепроверялся через сеть: состояние прежних 404/503/backup URL на SpaceWeb NOT_VERIFIED. Локальные Apache и error handling regression проверяют репозиторий, не исправляют сайт сами собой.
