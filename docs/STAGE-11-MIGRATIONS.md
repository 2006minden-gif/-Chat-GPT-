# Stage 11 — совместимость миграций

MySQL 5.7: последовательность `database/schema.sql` → существующие consent/version/idempotency baseline runner `migrate.php` → 004 foundation → 005 customer auth → 006 operations → 007 collaboration → 008 billing → 009 AI → 010 pricing → 011 production → новая 012 manual handoff. Используются существующие CLI runners, production не запускалась.

001–011 не изменены относительно Stage10. Повторного объявления CRM/financial/pricing таблиц нет. Stage9 отсутствует и не получила фиктивную миграцию. 012 — следующий свободный номер; она не доказывает существование Stage9.

`database/migrations/012_manual_handoff/up.sql` создаёт только `nd_manual_jobs`, `nd_manual_results`. FK на существующие project/task/spec/admin/file/revision; admin ID TINYINT UNSIGNED, остальные ID BIGINT UNSIGNED, соответствуют исходному коду. Unique `(job_id,revision_number)`, file_id и delivery_revision_id защищают версионирование/одно отображение. Project/id индекс поддерживает owner list. States валидируются PHP (не MySQL CHECK, который 5.7 не обеспечивает).

Job хранит неизменяемый source snapshot и копируемый текст, owner/time/hash. Result body/checksum неизменяемы, mutable status/approval/file links защищены version и транзакциями. Старый результат не перезаписывается, максимум 20 редакций. JSON в MEDIUMTEXT с серверной валидацией, без MySQL8 JSON_TABLE/CTE/window functions. Инвентарь/общая навигация не меняют схемы других стадий.

`scripts/migrate-manual.php` повторяет существующий guarded runner: CLI only, exact dependency checksum 011, strict SQL, journal/partial progress, advisory lock, отказ unmanaged collision; down reverse order только пустых новых таблиц под locks. Непустые таблицы, изменённый SQL checksum и более поздние миграции блокируют down/up. Все ошибки не содержат DSN/credentials.

`tests/test_manual_migrations.py`: up/up/down/up и сохранение существующих строк; checksum mismatch; частичный unmanaged DDL → отказ → journal recovery → empty down/up. `test_system_integration` проверяет отказ непустого012 rollback и запрет отката011 при012. Реальная установка всей цепочки выполняется на случайной loopback `neuro_test_*` БД, а не на production.

До одобренного выпуска нужны backup/restore и проверка фактического production migration journal. Не импортировать SQL вручную поверх уже управляемой схемы, не менять checksum старых миграций и не делать down для удаления клиентской истории. При непустом012 для code rollback оставить таблицы и отключить новый flag, не удалять записи. Реквизиты/доступ к production для этого отчёта не требуются.
