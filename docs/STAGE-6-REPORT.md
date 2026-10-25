# Stage 6 — отчёт разработки

Дата: 25.10.2026. Ветка: `feature/stage-6-client-collaboration`.

## Зависимости и границы

Stage 6 разработан поверх Stage 5 `a6a7b8c` (draft PR #21), который содержит Stage 4 `92f2b22` / PR #7 и Stage 3 `968c82d` / PR #4. Main на проверке — `478ca7f`; предыдущие development stages не считаются merged/deployed. Никакого merge в main, production deployment, SQL на SpaceWeb, изменения SSH credentials, GitHub settings или privacy flags не выполнялось. Workflows `.github/` и `scripts/deploy/` идентичны main.

Новый `client_collaboration_enabled` выключен по умолчанию и не заменяет gates Stage 4/5. Все activation и migration approvals остаются отдельными решениями владельца.

## Реализованные модули

1. **Сообщения.** Persistent project threads, customer/project search, last preview/time, unread by actor, chronological pages, composer и attachments, monotonic read markers, actor-bound idempotent send. Plain text rendering, network/HTML error сохраняет draft, polling только active/latest chat каждые 30 секунд. Реальных fictitious conversations/seed records в приложении нет.
2. **Файлы.** Multipart upload PDF/JPG/PNG/WebP/DOCX/XLSX; MIME/signature/size/name/OOXML checks, private random storage, restrictive permissions, total/per-file quota и free-space guard. Metadata/file SHA verified before commit; DB failure удаляет только незавершённый собственный upload. Owner visibility/archive, customer-scoped attachment download с nosniff/no-store, неизменяемые физические bytes. Не AV scanner.
3. **Документы.** Структурированное ТЗ/описание/план/результат/final/milestone, incomplete drafts, ready/submit, readonly exact revisions, archive прежней версии, owner new revision, history, escaped print-ready HTML. Серверный PDF не симулируется.
4. **Согласования.** Exact revision+checksum, optimistic version, document mutex + fresh locking reads, immutable decision/account/time/feedback. Explicit confirm, meaningful changes feedback, stale revision 409, replay не создаёт второе решение. Owner withdraw только pending. Ни payment, ни electronic-signature semantics не добавлены.
5. **Результаты работ.** Deliverable version со stored files и acceptance criteria, submit → feedback → revised version → approval. Прежние bodies/files/decisions сохраняются. Milestone/final requests требуют завершённый соответствующий этап/все этапы и тот же target version при решении; приложение не объявляет проверенными произвольные текстовые критерии автоматически и не меняет owner-only project status за клиента.
6. **Общий кабинет.** Stage 5 owner project links + «Сообщения»; customer navigation orders/projects/messages/files/docs/reviews/results/profile использует прежнюю идентичность. Dashboard: реальные проекты/unread и выбранный project reviews/files/results, полезные empty states, desktop/mobile local design. No fake KPI/activity.

Activity/owner notifications используют существующие Stage 5 tables, правильные actor IDs, project/customer references и fixed metadata; document/message bodies, feedback contents, passwords, cookies и reset tokens в audit не копируются. Internal CRM notes/employee private information не включены в customer projection.

## Файлы и модель

- `private/collab/core.php`, `messages.php`, `files.php`, `documents.php`, `approvals.php`, `routes.php`.
- `public/collaboration.php`, `.js`, `.css`; `collab-download.php`, `collab-print.php`, `collab-print.js`.
- Интеграция: `private/crm/routes.php`, `private/customer-auth.php`, `public/operations.js`, `public/portal.php`.
- Defaults/security: `private/config.example.php`, `.gitignore` (private storage исключён).
- **Migration 007:** `database/migrations/007_client_collaboration/up.sql`, `down.sql`; CLI `scripts/migrate-collab.php`; readonly inventory `scripts/check-collab-storage.php`.
- `scripts/package.py` включает новые services/CLI, без config.php и uploaded blobs. Это ручной dev packager, не изменение CI/CD.
- `tests/test_collaboration.py`, `test_collaboration_migrations.py`, local router allowlist.
- Документация: `STAGE-6-ARCHITECTURE.md`, `STAGE-6-STORAGE-SECURITY.md`, `STAGE-6-UX.md` и synthetic screenshots.

007 — девять additive InnoDB tables, FKs, indexes, unique revisions/decisions. 004/005/006 SQL и checksums сохранены. Не создаются параллельные customers/orders/projects/auth/history tables.

## Фактически выполненные проверки

**Полный локальный suite: 208 Python PASS, 0 FAIL/0 SKIP.** Включая 17 Stage 6 tests с несколькими HTTP/security/browser assertions. **12 существующих Node tests PASS.** PHP 8.4.27 syntax — 36 файлов PASS; JavaScript syntax, compileall, actionlint, release policy, diff --check PASS. Redacted Gitleaks working-tree scan — 0 находок. Среда: real isolated MySQL 5.7.42, Apache/Chromium и PHP, Fileinfo/ZipArchive включены только в локальном тестовом runtime; repository dependencies/workflows для этого не менялись. Hosted CI проверяется отдельно для опубликованного head, не подменяется local PASS.

Подтверждены:

- Owner ↔ customer messages, persisted IDs/order/unread/pagination, exact send replay; чужие threads 404, no-CSRF 403, archived project write conflict.
- Private PDF upload; positive PNG/WebP и inspected DOCX/XLSX; fake PNG/PHP/HTML/active PDF/macros/arbitrary Office members/traversal/empty/oversize rejected.
- Visibility change → permitted exact byte download; чужие/hidden/unknown file IDs имеют одинаковый 404 body. Missing bytes/invalid storage key дают safe 503 без path.
- Interrupted multipart HTTP body не создаёт metadata. Quota concurrent requests дают один persisted upload и 507 для превышения. Synthetic DB trigger failure не оставляет dangling row/blob. Low physical free-space branch проверена synthetic capacity values, реальный диск не заполнялся.
- Readonly orphan inventory сохраняет unreferenced fixture и не выводит filenames/paths/keys.
- ТЗ v1 → changes requested → v2 → approval → finalize/print; sent/approved body update rejected, old bytes/body/checksum сохранены; outdated first decision rejected, same idempotent decision ровно одна запись.
- Deliverable v1/files → feedback → v2/files → approval; cross-customer messages/files/documents/reviews/print isolation; customer не создаёт owner documents; disabled account и separate feature gate закрывают доступ.
- Required milestone/final state и stale target version; old customer/admin/lead/auth/CRM regression suite.
- Migration up/up/down/up preserves old rows; nonempty rollback, checksum mismatch, unmanaged collision, older-stage rollback refusal и partial journal empty recovery.
- Chromium owner upload/message/document submit + customer mobile approve; all collaboration tabs mobile без horizontal overflow/pageerror; stored script остаётся текстом, HTML вместо JSON не считается success. Снимки и пределы UX проверки — STAGE-6-UX.md.

## Не проверено / ограничения

- SpaceWeb runtime, реальная CRM/SMTP/registration, account filesystem quota, production downloads и production миграции не проверялись и не активировались.
- Наличие Fileinfo/ZipArchive, `upload_max_filesize`, `post_max_size`, actual private/document root, permissions и disk/account capacity необходимо подтвердить перед activation. При недостающем extension — fail closed; Office positive local tests не доказывают наличие extension на хостинге.
- Format inspection не гарантирует отсутствие malware. Внешний antivirus не настроен. OOXML intentionally conservative: сложные legitimate документы могут отвергаться; unreviewed formats не разрешены.
- Dashboard preview ограничен страницей проектов/выбранным проектом, lists paginated; это не полнота глобальной BI-агрегации. Parent Stage 5 notification batch limitations остаются прежними.
- Нет большого multi-worker production load test, expert screen-reader/axe audit, server-side PDF/signatures, billing/payments, external notifications или AI.
- Принятие явно подтверждает человек; произвольные требования свободного текста не проверяются машиной. Не выполняется автоматическое завершение проекта, оплаты или legal-contract workflow.
- Server-side drafts сохраняются только после Save. Message draft sessionStorage ограничен вкладкой; unsaved document form после full reload может быть потеряна. Visibility revoke сохраняет historical decision, но запрещает последующий download; pending review требует доступных файлов.
- Crash между filesystem move и DB commit может оставить private unreferenced blob. Он учитывается quota; inventory ничего не удаляет. DB и filesystem backups должны быть согласованы.

## Действия перед production

1. Review/integration Stage 3/4/5, затем Stage 6; draft не является разрешением auto-merge/deploy.
2. Отдельно согласовать полный release allowlist: текущий production manifest намеренно не включает новые Stage 5/6 assets/services. Workflows/deploy scripts этой задачей не изменялись.
3. Maintenance + проверенный private DB/storage backup и явно одобренные migrations 004–007; сначала isolated/staging verification. Down только empty-only; populated/непроверенный partial state — forward repair/verified restore, без force/drop рабочих данных.
4. Проверить extensions, private root/storage permissions/host limits и conservative quotas. До этого не включать `client_collaboration_enabled`.
5. Owner/legal approval документов и data-processing purposes/retention, затем явные Stage 4/5/6 flags и действующая customer auth configuration. Здесь legal text и compliance не придуманы, новые identities/mail credentials не требовались.

Deployment: **не выполнялся**. Main/production data/config/credentials/privacy settings сохранены.

**STAGE 6 DEVELOPMENT COMPLETE — READY FOR REVIEW.**
