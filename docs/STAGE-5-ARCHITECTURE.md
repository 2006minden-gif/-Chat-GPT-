# Stage 5: архитектура и API

## Зависимости и безопасность релиза

Ветка `feature/stage-5-crm-operations` создана от main bcb5797, затем обычным merge включена ветка Stage 4 92f2b22, содержащая Stage 3 968c82d. На момент проверки PR #4/#7 не merged (их commits не ancestors main). Это зависимость только dev-ветки, не разрешение публикации. Миграции 004/005 сохранены без изменения checksums. Workflows `.github/` и весь `scripts/deploy/` идентичны исходному main; production credentials, flags, данные не читались и не менялись.

**Deployment blocker:** существующий production allowlist не включает новые CRM/customer assets/services. Он намеренно не меняется этой задачей. Нельзя сливать Stage 5 в автоматически публикуемый main до отдельного одобрения зависимостей и согласованного release manifest, approval миграций и проверки staging. Прохождение CI текущего production bundle не означает готовность пакета Stage 5. Ручной development packager `scripts/package.py` включает все новые PHP services и CLI migrations, без working config и policy; это не новый CI/CD механизм.

## Слои

- `private/crm/core.php`: gate, модели, валидация, переходы состояний, транзакции, idempotency, события.
- `read.php`: dashboard, ограниченная пагинация, detail projections и связи.
- `write.php`: owner-only изменения, optimistic locking и явные операции связей/конверсий.
- `routes.php`: подключается из существующего `api.php` только для prefix `crm/`.
- `portal.php`: отдельная projection для Stage 4 customer session; не использует owner endpoints.
- `workspace.php`, operations.js/css: новый рабочий интерфейс. Старый studio.php/CRM остаётся доступен, включая управление приглашениями Stage 4.
- `portal.php`, portal.js: клиентские заказы/проекты/этапы; ссылка после существующей авторизации.

Без новых framework, CDN, build steps и CSP exceptions. Локальные стили и системный шрифт. Включение `crm_operations_enabled === true` и существующие одобренные опубликованные privacy documents обязательны. Отсутствие схемы даёт safe 503. Флаг по умолчанию false; UI настроек не меняет gates. Customer requests дополнительно проходят ca_gate, ca_session, ca_account_allowed, текущую consent version/hash. Employee records не являются аккаунтами; запись разрешена только владельцу.

## HTTP contracts

Все API: JSON, Cache-Control:no-store; ошибки существующего формата `detail,error_code`. Успех CRM: `ok:true`. Unauthorized owner 401, origin/CSRF 403, unknown ID 404, stale version/idempotency mismatch 409, validation/transition 422, unavailable schema/DB/gate 503. Роуты `api.php?r=crm/...`:

| Метод / маршрут | Результат |
|---|---|
| GET dashboard | Реальные kpi, recent_leads, projects, deadlines, activity |
| GET settings | Read-only модели, статусы и сведения о настройках |
| GET customers/deals/orders/projects/tasks/employees/stages | items,total,page,page_size (25) |
| GET entity/ID | record и связанные records/history; связанные коллекции ограничены |
| POST entity | request_key (64 lowercase hex), поля модели; atomic create + history |
| PATCH entity/ID | version integer + изменённые разрешённые поля |
| POST entity/ID/archive или restore | version, без уничтожения истории |
| POST customers/ID/link | version, lead_id integer; без автоматического reassignment |
| POST deals/ID/convert | version, confirm:true, request_key; только won, максимум один order на deal |
| POST projects/ID/members | version, employee_id, role=manager/contributor/observer; только бизнес-роль |
| POST projects/ID/reorder | version, stage_ids: полный ordered список integer IDs |
| GET leads/activity/notifications | Owner-only коллекции, пагинация |
| POST notifications/sync | CSRF-protected bounded deduplicated evaluation |
| POST notifications/ID/read или all/read | Отметка прочтения |

Filters: search (имя/название), status, kind, customer_id, project_id, assignee_employee_id, priority, overdue=true, due_soon=true, archived=true/all, active=true, unread=true; применяются только подходящие allowlisted поля. Глобальный UI-поиск объединяет первые 25 результатов каждого раздела. Поиск не рассматривается как выгрузка всех записей.

Все owner mutations требуют существующий nd_session и X-CSRF-Token + same_origin. Create, activity, relationships, notifications и receipt в одной транзакции. Повтор того же ключа/содержимого возвращает тот же result, ключ с иным содержимым — 409. История не содержит payload, паролей/токенов/контактных значений. Одноразовый conversion ledger + lock deals исключает второй order даже с другим ключом. Обычные самостоятельные заказы с одинаковыми названиями не объединяются.

Customer read API: `customer-api.php?r=portal/orders` или `portal/projects`, optional `/ID`, page. Только GET; ownership customer_id привязан к серверной Stage 4 account, не query параметру. Точное allowlist полей: order id/number/title/status/total_amount/currency/due_on/created_at; project id/order_id/title/status/starts_on/due_on/completed_at; stages id/title/status/position/due_on/completed_at, computed progress. Ни notes, description, employees, tasks, auth metadata, ни чужие records не возвращаются. Для чужого ID тот же 404, что для отсутствующего.

## Бизнес-правила

Stage 3 ENUM остаются прежними. Сделки: new → qualified → proposal/negotiation → won/lost; отказ можно вернуть в new. «Согласование» отдельно не хранится: используется negotiation, не придумывается новый ENUM. Won не создаёт order автоматически. Won terminal; lost → new разрешён.

Orders: draft → confirmed → in_progress → completed, отмена до completion; cancelled → draft. Projects: planned → active ↔ on_hold → completed, отмена до completion; cancelled → planned. Stages: planned → active → completed, cancelled; completed → active, cancelled → planned. Tasks: todo → in_progress/blocked, in_progress → done/blocked, blocked → todo/in_progress; done/cancelled → todo. Сервер — источник истины, отклонённый drag сохраняет прежнюю карточку; формы доступны без drag.

Связи customer/project/order/deal после создания неизменяемы через edit. Lead link — отдельное явное действие, существующая чужая связь даёт 409. Task stage проверяется в контексте project. Assignment требует active employee. Архив не удаляет rows/FKs/history; customer archive немедленно закрывает его customer account через существующий Stage 4 gate. Restore employee возвращает suspended: доступ автоматически не возникает.

Progress = floor(completed stages / all stages ×100). Все этапы, включая отменённые, входят в denominator; без этапов percent=null («Этапы не добавлены»). Для завершения проекта нужны непустые полностью завершённые этапы; deadline ничего не завершает. UTC хранение/ввод DATETIME; деньги принимаются только decimal strings, без float arithmetic, до DECIMAL(15,2), RUB.

Notifications: event rows при owner mutations. Новые leads и deadline events обнаруживаются при явном authenticated POST sync; event_key unique предотвращает повтор. Один sync проверяет последние 100 leads и по 100 due tasks/projects: большие backlog требуют отдельного согласованного batch механизма, не молчаливого предположения о cron. Нет email/push/background dependency. Обычный GET не порождает уведомления.

## Миграция 006 и recovery

`database/migrations/006_crm_operations/up.sql`: nullable due_on/loss_reason в deals, due_on/notes в orders, position в employees; nd_crm_requests (idempotency receipt), nd_crm_conversions (unique deal/order), nd_crm_notifications (unique event_key, read_at/id index). Никакого копирования или автоматического связывания старых клиентов. Existing foreign keys/indexes 004 используются без дублирования.

Только в одобренном maintenance window, после проверенного приватного backup БД и отключения app writers: `php8.4 scripts/migrate.php up`, затем `migrate-customer.php up`, затем `migrate-crm.php status/up`. CLI читает private/config.php по sibling path, не принимает пароли в аргументах. Запуск на production этой задачей запрещён и не выполнялся.

006 проверяет checksums обеих зависимостей/своих SQL, strict sql_mode, advisory lock, отсутствие unmanaged tables/columns и newer migrations; DDL journal фиксирует completed_steps. MySQL 5.7 DDL не transactional: partial state не продолжается автоматически. В таком случае сверить private backup/journal и восстановить БД из проверенной копии в maintenance, не редактировать журнал ради зелёного статуса.

`migrate-crm.php down` разрешён только для applied 006, когда все три новые таблицы пусты и новые columns NULL. Проверка под LOCK TABLES; иначе отказ без удаления рабочих данных. 004/005 rollback не допускается, пока есть newer journal. Для populated системы recovery — forward fix либо проверенный backup, не DROP данных. Production migration policy не менялась.
