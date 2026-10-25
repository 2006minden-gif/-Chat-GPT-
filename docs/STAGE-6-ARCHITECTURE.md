# Stage 6 — совместная работа: архитектура и API

Дата: 25.10.2026. Dev-ветка `feature/stage-6-client-collaboration` основана на Stage 5 `a6a7b8c` (draft PR #21), содержащем Stage 4 `92f2b22` / PR #7 и Stage 3 `968c82d` / PR #4. На момент проверки main `478ca7f` их не содержит. Это зависимость разработки, не разрешение merge/migration/deployment. Stage 5 реализован и протестирован, но не опубликован. Новая migration — **007_client_collaboration**, 006 уже занята Stage 5 и не переписывается.

## Интеграция

PHP 8.4, MySQL 5.7, HTML/CSS/vanilla JS. Без framework, WebSocket, cron, CDN и PDF libraries. Owner API в существующем `api.php?r=crm/collab/…`; customer API — `customer-api.php?r=collab/…` после Stage 4 legal gate/rate limit. У каждого защищённого запроса проверяются действующая сессия, разрешения и реальный customer_id из server account. Все mutations требуют существующие CSRF и same_origin. Owner/customer mode в URL выбирает механизм сессии, а не выдаёт роль.

Нужны оба Stage 5/privacy gate и отдельный `client_collaboration_enabled === true`; default false. Нужна applied 007. Customer дополнительно проходит Stage 4 ca_gate, verified/active account, active customer и актуальные policy version/hash. Решение о согласовании повторно проверяет и блокирует account внутри транзакции. Ни регистрации, ни отправки писем Stage 6 не включает.

Новые модули `private/collab/{core,messages,files,documents,approvals,routes}.php`; UI `public/collaboration.php/js/css`. Owner CRM получает «Сообщения» и ссылки вкладок в карточке проекта; customer portal — общую навигацию с существующими заказами/проектами/профилем, не отдельные аккаунты. Ссылки скрыты, пока gate выключен. Content Security Policy не ослабляется.

## Модель

007 добавляет только девять таблиц InnoDB/utf8mb4:

| Таблица | Назначение и ограничения |
|---|---|
| nd_cc_messages | project FK, actor role/id, plain text, UTC; project/id index |
| nd_cc_reads | compound project/actor PK, монотонный last_message_id |
| nd_cc_files | project FK, unique random storage_key, display/MIME/size/SHA256, actor, visibility, archive/version |
| nd_cc_message_files | message/file FKs и составной PK |
| nd_cc_documents | project FK, optional composite project/stage FK, kind, logical title, head/version/archive |
| nd_cc_revisions | document FK, unique document/revision_number, body/checksum/status/version/archive |
| nd_cc_revision_files | revision/file FKs, составной PK, неизменяемая связь после отправки |
| nd_cc_approvals | unique revision FK, exact checksum, target version, state/version/due date |
| nd_cc_decisions | unique approval FK, customer account FK, decision/feedback/checksum/UTC |

Order выводится из существующего project.order_id; отдельная параллельная сущность заказа не создаётся. Deliverable — документ kind=deliverable; его редакции и файлы используют ту же immutable модель. Отдельный final/milestone kind обеспечивает проверку состояния при приёмке. Kind description/plan/specification соответствует описанию, плану работ и ТЗ.

Не создаются новые history/notification tables: события пишутся в nd_activity_history с правильным actor_admin_id **или** actor_customer_account_id, project/customer FK, фиксированным action/summary. Через существующий crm_notice они видны владельцу. В history не пишутся тела сообщений/документов/feedback, file contents, passwords или tokens. Содержимое хранится только в предназначенных приватных business tables.

## API

JSON success `ok:true`, mutation ID/record где применимо; errors — прежние `detail,error_code`. HTTP 401/403/404/409/422/503 и 507 для квоты. Отсутствующий/чужой объект получают одинаковый 404 response body. Клиент отвергает HTML, malformed JSON и неподтверждённые структуры ответа. Параметры ID не задают customer identity.

| Метод / collab route | Действие |
|---|---|
| GET threads | scoped проекты, последний preview/time, unread, search, project_id, page |
| GET projects/ID/context | safe project/customer/order info и milestones |
| GET projects/ID/messages | 30 записей страницы, по времени/ID, только разрешённые attachments |
| POST projects/ID/messages | body 1–5000, file_ids ≤10, request_key; persisted id |
| POST projects/ID/read | last_message_id из этого проекта, never decreases read cursor |
| GET projects/ID/files | metadata без storage_key, page size 25 |
| POST upload | multipart file/project_id/visibility/request_key; CSRF header |
| POST files/ID | owner-only version, visibility и archived boolean |
| GET projects/ID/documents | версии документов, customer только когда отправлены |
| POST projects/ID/documents | owner kind/title/optional stage_id/fields/file_ids/key; incomplete draft разрешён |
| GET revisions/ID | exact immutable snapshot, safe files, approval/decision |
| POST revisions/ID/save | owner, draft only, current version integer, fields/file_ids/key |
| POST documents/ID/revise | owner document version, new revision, old snapshot retained |
| POST revisions/ID/ready | owner; title и acceptance criteria обязательны |
| POST revisions/ID/submit | owner; confirm=true, exact revision version, optional due_on |
| GET projects/ID/approvals | reviews/status/deadline/version/checksum, page size 25 |
| POST approvals/ID/decide | customer, approval version/checksum/confirm/decision/feedback/key |
| POST approvals/ID/withdraw | owner, pending only, version/key; decision не удаляется |
| POST revisions/ID/finalize | owner, approved current version only |
| POST documents/ID/archive | owner version/key/archived; withdrawal pending, no content deletion |
| POST revisions/ID/archive | owner; только прежняя редакция, snapshot/decision сохранены |

`collab-download.php?mode=owner|customer&id=…`: отдельная authenticated attachment response. `collab-print.php?mode=…&id=…`: escaped print-ready HTML без поддельного PDF. Print доступен авторизованному владельцу; клиенту — только опубликованная редакция собственного проекта.

## Транзакции и lifecycle

Создание сообщений/редакций/решений использует существующую nd_crm_requests: hash includes actor type + actor ID + operation + payload. Поэтому чужой actor не может replay получить чей-то result. Повтор того же ключа не создаёт дубль, другой payload — 409. Legitimate отдельные uploads с одинаковыми filenames сохраняются разными private objects.

Draft → ready → sent → approved/changes_requested → finalized (только approved). Body/attachments можно менять исключительно у current draft; optimistic version проверяется под lock. После ready/content freeze для изменения нужна новая редакция. Родительский document row сериализует revision/submit/decision; после ожидания lock mutating code повторно читает актуальные revision/approval FOR UPDATE, не использует старый repeatable-read snapshot для сохранения.

Отправка фиксирует canonical SHA256 от project/kind/stage/ordered fields и id/checksum attachments. Проверяются физические файлы и явная customer visibility. New revision отзывает только pending запросы прежних версий. Старое принятое решение не стирается. Customer approve требует текущий head, pending request, exact checksum/version и confirm=true. Changes requested — содержательное feedback ≥5 символов. Unique decision/approval + actor-bound key защищают от повторов. Решение связано с exact revision/checksum/account/time.

Milestone request требует существующий **completed** milestone того же проекта. Final request требует непустые полностью завершённые milestones. Target version проверяется повторно перед решением: изменившийся milestone/project требует новую редакцию. Текстовые критерии проверяет человек при явном подтверждении; приложение не заявляет автоматическую проверку произвольных бизнес-требований. Согласование само не меняет owner-only project/task states и не означает оплату, договор или юридически значимую электронную подпись.

Архивированный/отменённый project или архивный customer запрещают новые mutations; история остаётся доступной уполномоченным читателям. Disabled/archived account не получает контент. Message read markers — идемпотентный счётчик чтения, могут обновляться при чтении архивной истории. При archive проекта физические файлы не удаляются.

## UI и ограничения объёма

Chat: список проектов, sender role/time, paginated history, composer, private upload, real XHR byte progress. Refresh заменяет ordered page без дублей, текст остаётся в форме/sessionStorage этой вкладки. Автообновление 30 секунд выполняется только у активной страницы сообщений и только для последней страницы; при document.hidden нет polling. Документы не polling'уются во время редактирования.

Общий dashboard показывает реальные проекты/непрочитанные сообщения доступной страницы, а reviews/files/results — выбранного проекта. Это явно подписано. Lists — 25 с pagination; messages — 30; dashboard preview — до 10. Это не глобальная агрегированная отчётность по всем страницам. Существующие orders/projects/profile открываются штатной навигацией Stage 4/5. Editor предупреждает о видимости и unsaved close, сохраняет text draft при ошибке; недописанные поля допустимы до ready. Browser print используется как HTML, серверного PDF engine нет.

## Контролируемые миграции

Только в одобренной maintenance-среде после проверенного private DB backup: `php8.4 scripts/migrate-collab.php status/up/down`. Runner проверяет applied/checksummed 006, собственные checksums, strict SQL mode, advisory lock, newer journal, unmanaged collisions. 004–006 SQL не менялись. Up/up идемпотентен, прогресс DDL журналируется. MySQL 5.7 DDL не transactional: partial state не auto-adopt/auto-continue. Explicit empty rollback частично созданных tables возможен под locks; populated rollback отказывается. Для populated/непроверенного partial состояния нужны forward repair или проверенное восстановление backup, не редактирование journal ради успеха.

Production миграции/feature flags не выполнялись и не включены в автоматический deployment manifest. Workflows и scripts/deploy идентичны main. Пока Stage 3/4/5 не reviewed/integrated и новый полный release manifest не согласован, Stage 6 не предназначен для публикации из main.
