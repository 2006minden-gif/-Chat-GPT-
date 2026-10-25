# Stage 11 — безопасность и восстановление

Область: текущая интеграционная ветка, приложения `public/`, `private/`, SQL, локальные HTTP/PDO/browser fixtures. Production/SpaceWeb логи, реальные права хранения, фактическая версия production code и внешние сервисы NOT_VERIFIED. Это не заявление о юридическом соответствии или независимый pentest.

## Проверенные границы

| Область | Механизм и доказательство | Ограничение |
|---|---|---|
| Владелец | `private/app.php`: password_hash/verify, защищённая DB session, CSRF/origin/rate; `test_prelaunch*` | реальные credentials/owner login на SpaceWeb не проверялись |
| Клиент | `private/customer-auth.php`: email/reset/invitation tokens, срок, active account/current consent; `test_customer_auth` | только test mail transport, live SMTP NOT_VERIFIED |
| Object authorization | `cc_project`, customer portal queries, `ai_scope`, `test_crm_operations`, `test_collaboration`, `test_billing`, `test_production` | security boundary серверная, навигация не является авторизацией |
| Ручные задания | `private/manual/routes.php`: существующий cc_actor, owner-only + flag/migration, GET/read vs POST/write, rate, versions, checksum, idempotency | никакой Codex API и автоматического внешнего переноса |
| SQL/API | подготовленные значения PDO, allowlisted SQL identifiers, scoped queries, bounded pages; тесты malformed input/409/CSRF | не утверждается отсутствие всех возможных дефектов по одному сканированию |
| Импорт | только JSON files-as-data, safe basename/расширения, UTF-8, 10 файлов, 12k каждый/20k суммарно, APP body cap 64KiB | не ZIP extraction, не arbitrary filesystem write; сложные проекты требуют отдельного формата |
| Исполнение | отсутствуют eval/shell/runtime маршруты для результата; генерируемый код никогда не исполняется | статические regex не полноценный security scanner, sandbox отсутствует |
| QA | код/runtime/browser → NOT_TESTED/BLOCKED, JSON/DRAFT_ONLY; серверный отчёт нельзя заменить текстом модели | смысловая корректность документов проверяется владельцем; literal criteria лишь ограниченное evidence |
| Одобрение | точная latest revision + checksum + version, authenticated owner ID/time, stale source отказ | цены/Stage9/сроки ручной маршрут не создаёт и не меняет |
| Файлы/доставка | приватное Stage6 quota storage/0600/0700, attachment+nosniff, authorized download; JSON seal исключает обход через общий редактор | локальная FS проверка не подтверждает hosting permissions |
| Деньги | существующие decimal-safe pricing/billing, exact quote approvals, signed/verified test-provider state, idempotency/refunds authorization | mock transport не live платежи; финансовые операции Stage11 не инициирует |
| Ошибки | существующий fail/server_error, display_errors off, дружелюбные ошибки, request id; rollback/idempotent retry | production logs не запрашивались; централизованный operational review ещё нужен |
| Privacy | исходные flags/политики/consent version/hash сохранены, unchecked checkbox, API fail-closed | реальные тексты, сроки хранения и lawful basis требуют owner/legal review |

## Исправления и оставшиеся риски

- **MEDIUM, исправлено:** разрозненная навигация в `public/{workspace,portal,collaboration,billing,ai,production}.php`. Общий `private/product-navigation.php` с реальными маршрутами и flags; каталог/список клиентских заявок честно обозначены недоступными. Контекстные вкладки сохраняются.
- **MEDIUM, исправлено:** новый длинный QA-отчёт вызывал горизонтальную прокрутку на 390px. `public/production.css` переносит строки/хеши в handoff. Повторный Chromium тест проходит.
- **HIGH, предотвращён:** импортированный результат мог бы восприниматься как проверенный код. `mh_checks` переиспользует серверные проверки Stage10, runtime/browser недоступны и блокируют approve/deliver. Исходник хранится только как JSON-данные.
- **HIGH, предотвращён:** duplicate delivery/approval bypass. Результат latest-only, lock job/result, exact immutable checksum, transactional Stage6 file+deliverable, idempotency; общий cc_file_update отказывает для запечатанного JSON. Два независимых PHP процесса проверяют один эффект.
- **HIGH, BLOCKED до выпуска:** отсутствуют Stage9 accepted offer adapter, проверенный полный deployment package и подтверждённые hosting controls. Не делать feature flags true на production по результатам этих тестов.
- **HIGH, NOT_VERIFIED:** live SMTP/payment/provider, actual backup restore, HTTPS/DB/log/storage проверки SpaceWeb. В этой стадии запрещены подключения/изменения production.
- **MEDIUM, открыто:** retention/удаление рабочих исходников, ТЗ, результатов, согласований и финансовой истории требует бизнес- и правового решения. Сейчас история не удаляется автоматически, старые результаты сохраняются. Импорт не должен содержать реальные секреты или неразрешённые персональные данные.
- **MEDIUM, открыто:** regex-поиск выявляет лишь часть секретов/опасных конструкций; текстовое `contains` не доказывает техническую работоспособность. Владелец должен читать документ и ограничения, а код требует отдельной утверждённой QA-среды.

## Восстановление

Новая миграция `012_manual_handoff` аддитивна, зависит от checksum 011. CLI `scripts/migrate-manual.php status|up|down`, без автозапуска. Up проверяет предыдущую миграцию, strict mode, unmanaged collisions, advisory lock/journal/checksum. Down отказывает при любых новых данных или более поздних миграциях; данные клиента не удаляет. Частичный пустой DDL восстанавливается только проверенным empty rollback, затем повторным up.

Перед будущим одобренным выпуском: защищённый backup БД и private blobs/config отдельно вне Git/public, проверка восстановления на staging, точный approved SHA/пакет, контроль свободного места и checksum. При ошибке остановить выдачу новых задач (флаг false), сохранить журналы/файлы и откатить код к совместимому SHA, не делать автоматический destructive down. Пакет/SQL/hosting actions в Stage11 не выполняются.
