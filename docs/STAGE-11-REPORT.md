# Stage 11 — интеграция и review

**Готовность продукта: NOT_READY.** Разработка безопасной интеграционной ветки подготовлена для review; это не разрешение выпуска и не заявление о завершённом каталоге/автономном исполнителе.

Ветка: `integrate/stage-11-system`, база Stage10 `51412fd8a92cdb3464459f43061472ea938a468e`. История main сохранена. Совместимая цепочка Stage3–8/10 уже является предками этой ветки; повторные merge/cherry-pick не выполнялись. Stage9 отсутствует в доступных исходниках/remote feature branches. Main, SpaceWeb, production DB/config, SSH, CI/CD и deployment scripts не изменялись.

## Выполненные этапы

| Фаза | Результат |
|---|---|
| 11.1 Inventory | исходные branches/SHA/PR, ancestry, features/routes/migrations/activation — STAGE-11-INVENTORY.md |
| 11.2 Integration | отдельная ветка с существующей совместимой историей, без дублирования миграций/финансов/очередей |
| 11.3 UI | общий contextual switcher CRM/customer на существующих страницах, flags скрывают недоступные разделы; каталог честно unavailable |
| 11.4 Journey | A–I разделены на реальные application checks, mock external transport и missing dependencies; полный journey BLOCKED |
| 11.5 Security | owner/customer/CSRF/source freshness/checksum/files/payment/privacy границы и открытые operational/legal риски документированы |
| 11.6 Fixes | мобильный overflow нового QA, понятный русский отчёт, безопасный manual import/approval/delivery, stale source/version/duplicate protections |
| 11.7 Performance | устранён повторный SELECT имени клиента на каждый project; bounded manual lists, реальный loopback timing, без выдуманных процентов |
| 11.8 Tests | повторяемая существующая suite + ручной маршрут/browser/concurrent delivery/migration recovery |
| 11.9 Readiness | NOT_READY с конкретными блокерами/backup-release требованиями |
| 11.10 Acceptance | русская инструкция по реальным страницам/кнопкам, без запросов новых API keys |

## Что реализовано и что интегрировано

Stage1–6 реализованы в исходниках и доступны в общей тестовой цепочке. Stage7–8 частичны в отношении live external services; локальные transport tests не означают настоящий платёж/AI. Stage10 реализует draft artifacts/static QA, не runtime sandbox. Stage9 MISSING. Все эти исходники находятся в Stage11 ветке, но не автоматически в production main. Точная таблица статусов и PR — в Inventory.

Добавлен независимый ручной handoff поверх реальных Stage5 tasks и Stage6 принятого ТЗ/файлов/приёмки. Он не создаёт accepted offer, не меняет коммерческие обязательства и не обходит Stage9 gate автоматического Stage10. Owner подтверждает подготовку, получает копируемое задание с предупреждением/редакцией исходников, вручную переносит его во внешнюю среду, импортирует JSON data-only результат. QA повторно использует server static checks; technical code без sandbox BLOCKED. Документальный результат проходит точное owner approval и отдельную Stage6 delivery. Код не выполняется. Codex API, provider credentials и background executor не нужны и не добавлены.

## Файлы и коммиты

- `e32d8d9`: `private/manual/{core,actions,routes,seal}.php`, `database/migrations/012_manual_handoff/{up,down}.sql`, `scripts/migrate-manual.php`, `tests/test_manual_migrations.py`; hooks `private/collab/routes.php`, `private/production/seal.php`, default false в config.example.
- `1cdf9c2`: `private/product-navigation.php`, `private/crm/{routes,read}.php`, `public/handoff.{php,js}`, shared navigation hooks в `public/{workspace,portal,collaboration,billing,ai,production}.php`, `public/operations.js`, scoped mobile CSS, `tests/router.php`, `tests/test_system_integration.py`.
- `e4932dd`: русский читаемый QA перед техническими доказательствами, видимый разделитель ссылок.
- `2cf34e3`: исходная inventory. Документы/снимок — отдельный завершающий documentation commit.

012 создаёт две новые таблицы, не меняет 001–011. Реальные MySQL5.7 up/down/checksum/partial recovery tests; production migrations не выполнялись. Полнота deploy allowlist для новых файлов остаётся отдельным блокером, его запрещено менять в этой стадии.

## Результаты проверок

- Полный итоговый Python regression: **278 тестов PASS**, 228.620 с. Реальные PHP 8.4.27, MySQL 5.7.42, Apache 2.4.69 и Chromium/Playwright, случайные loopback neuro_test_* БД.
- Новые проверки: 9 system integration tests PASS (clipboard/import/HTML failure, static QA, owner exact approval, Stage6 delivery, customer isolation, stale source/CSRF, unsafe files, mobile UI, flags/navigation, независимые PHP процессы), 3 manual migration tests PASS.
- Отдельный CRM regression после удаления duplicate SELECT: 9 тестов PASS, 8.372 с.
- PHP lint **92 файла PASS**, JS syntax **15 файлов PASS**, Node **12/12 PASS**.
- actionlint, release policy check, compileall, git diff --check — PASS. CI/CD файлы не изменялись. Existing release check не подтверждает, что allowlist уже включает Stage11.
- Gitleaks текущего дерева: утечек не найдено. Не повторный full-history audit.
- Browser fixture проверяет реальный clipboard, отказ HTTP200 HTML без DB insert с сохранением JSON поля, последующий успешный импорт, QA/approval, responsive 390px и отсутствие pageerror. Снимок `docs/stage-11-ux/manual-owner-mobile.png`.
- Loopback HTTP manual/jobs, 7 synthetic jobs, 5 замеров мс: 7.22, 6.825, 7.006, 6.785, 6.89. Это измерение нового bounded endpoint, не доказательство ускорения hosting.
- Live SMTP/payment/AI/Codex/sandbox/SpaceWeb/production SQL/deploy: **NOT_VERIFIED / не выполнялись**.

Повторение: существующая команда `python -m unittest discover -s tests -p 'test_*.py' -q` при loopback-only NEURO_TEST_DSN, PHP_BIN, APACHE_BIN/APACHE_MODULE_DIR и Playwright/Chromium согласно test dependencies. Запущено с `/tmp/neuro-runtime/php`, Apache2.4 modules из тестового runtime, DSN `mysql:host=127.0.0.1;port=33078`; production credentials не использовались. `node --test tests/api-client.test.cjs`, `node --check`, `php -l`, `python scripts/deploy/release.py --check` выполнены реально. GitHub push CI фиксируется отдельно по точному итоговому SHA; локальный PASS не выдаётся за remote CI.

История исправлений тестов: первый новый012 FK имел неправильную разрядность admin ID; исправлен на реальный TINYINT UNSIGNED до публикации. Первый mobile QA вызывал overflow; scoped wrap и читаемое collapsed QA исправлены, повторный browser test прошёл. В первом полном прогоне новый HTML-failure browser test не перехватил URL из-за glob `*`, не соответствовавшего slash в query route; исправлен на `**`, затем подтверждены неизменное поле и 0 DB results при HTTP200 HTML. Эти неуспешные попытки не выдаются за PASS.

## Security и остающиеся ограничения

Не найдено подтверждённого auth bypass/финансового повреждения в выполненных локальных проверках; это не доказательство отсутствия всех уязвимостей. HIGH production blockers: Stage9, полный checked release package, hosting/private FS/HTTPS/logs/backup verification, реальная политика/retention/activation approval. Live email/payment/AI NOT_VERIFIED и не активированы. Нет runtime sandbox, Nodul integration, постоянного worker или автоматического Codex исполнения. Импорт ограничен JSON/10 файлов/20KiB, документационные статические критерии не доказывают смысловую полноту работы. Внешний ручной шаг владельца в Codex не моделируется как выполненный API-вызов.

Миграции совместимы в изолированной тестовой цепочке MySQL5.7; реальный production migration journal не инспектировался. Цены/маржа/налоги из Stage8 сохраняют отдельное authenticated owner approval. Ручной handoff не отправляет proposal, не меняет сумму/срок, не создаёт платёж или refund. Existing consent/legal flags не ослаблены, формы не включены на production.

## Материалы review

- [Inventory/dependency map](STAGE-11-INVENTORY.md)
- [Journey matrix и manual protocol](STAGE-11-JOURNEYS.md)
- [Migration compatibility](STAGE-11-MIGRATIONS.md)
- [Security/recovery](STAGE-11-SECURITY.md)
- [Performance](STAGE-11-PERFORMANCE.md)
- [Readiness](STAGE-11-READINESS.md)
- [Owner checklist](STAGE-11-OWNER-CHECKLIST-RU.md)

После review требуется отдельное решение по scope Stage9, privacy/retention, external services и approved package/migration/release. Разработка не даёт автоматического разрешения main merge/deployment.
