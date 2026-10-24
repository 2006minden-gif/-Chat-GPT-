# Stage 4: клиентская авторизация

## Зависимость и состояние

Ветка `feature/stage-4-customer-auth` создана от Stage 3 `968c82d` и включает main `22ff5d7` с существующим CI/CD. Stage 3 PR #4 должен войти в main раньше Stage 4. Миграция 004 и её таблицы не дублируются и не изменяются. Stage 4 не сливается и не публикуется этим заданием.

Главная страница сохранена; добавлена ссылка «Кабинет клиента». `/customer.php` использует существующие styles.css/crm.css и собственное небольшое дополнение. Проекты, заказы и сотрудническая авторизация в клиентском интерфейсе не реализуются этим этапом.

## Данные и lifecycle

005_customer_auth добавляет пять InnoDB-таблиц MySQL 5.7, с FK RESTRICT:

- nd_customer_auth: 1:1 с существующим nd_customer_accounts; способ регистрации, подтверждение email и текущая версия согласия.
- nd_customer_tokens: SHA256 криптографически случайного 256-bit токена, назначение, срок, момент использования, инициатор-владелец. Ссылки/исходные токены не записываются в БД, очередь или журналы.
- nd_customer_sessions: отдельная от nd_sessions таблица, хеш токена и CSRF, FK аккаунта либо NULL для формы до входа, фиксированный срок.
- nd_customer_consents: история явных согласий, timestamp, версия и SHA256 документа, назначение. Значение не выставляется автоматически владельцем при приглашении.
- nd_customer_auth_events: минимальная история авторизации/управления/SMTP acceptance, без паролей, ссылок, тел писем и адресов в тексте событий.

Self-registration создаёт отдельную запись nd_customers и invited account. Email приводится к lowercase ASCII, пробелы по краям удаляются; UNIQUE nd_customer_accounts.email остаётся общим для самостоятельной регистрации и приглашений. Совпадение имени/телефона не объединяет клиентов. Дубликат регистрации не меняет пароль/имя существующего аккаунта и возвращает такой же нейтральный ответ.

Подтверждение email активирует только self account. Приглашение активируется после создания пароля и личного согласия клиента; ссылка одновременно подтверждает владение email. Invitation existing-email никогда не переводит аккаунт другому customer_id. Повтор приглашения для того же явно выбранного customer_id разрешён для ещё не активированного invitation account, предыдущее приглашение аннулируется. Старые Stage 3 accounts без nd_customer_auth не присваиваются автоматически новому заявителю и не активируются без отдельной процедуры.

Владелец может отключать подтверждённый/ожидающий аккаунт, включать ранее подтверждённый аккаунт и завершать все его сеансы. При отключении аннулируются также открытые ссылочные токены; пароль не перезаписывается. Конкурентные операции владельца используют version/HTTP 409. Архивный customer не может войти. Отключённый неподтверждённый аккаунт не активируется административным обходом проверки email.

## HTTP API

Все ответы customer-api.php — JSON/no-store/noindex; неожиданный HTML не считается успешной операцией. settings/session GET не принимают ссылочных токенов. Все изменяющие публичные операции — POST с same-origin и CSRF от предварительного GET session.

| Route r= | Действие |
|---|---|
| settings GET | Feature/privacy readiness, публичные параметры документа |
| session GET | Анонимный CSRF либо текущий подтверждённый клиент |
| register POST | name, email, password, password_confirmation, consent=true, policy_version |
| verify POST | token, consent=true, policy_version |
| resend POST | email, нейтральный ответ; повтор подтверждения self registration |
| login POST | email/password; при обновлении политики consent/policy_version |
| logout POST | Серверное завершение текущего сеанса |
| forgot POST | email, нейтральный ответ |
| reset POST | token, password/password_confirmation; завершение всех старых сеансов |
| invite POST | token, password/password_confirmation, consent/policy_version |
| owner/accounts GET | До 200 аккаунтов; только действующий CRM сеанс владельца |
| owner/invite POST | CRM CSRF; email + явный customer_id либо name нового клиента |
| owner/lifecycle POST | CRM CSRF; account_id, version, action=disable/enable/revoke_sessions |

Приглашения и lifecycle встроены в существующий dashboard CRM, отдельной админской аутентификации не создаётся. Сотрудников/менеджеров нельзя авторизовать передачей employee_id или заголовка: employee login/RBAC пока отсутствует, поэтому действия выполняет действующий администратор nd_admin id=1. Доступ менеджерам потребует будущей проверенной employee authentication/permissions, не открытой формы или общего ключа.

## Защита

- password_hash/password_verify, минимум 12 символов с буквами и цифрами, максимум 72 UTF-8 байта без NUL (исключено усечение bcrypt). Пароль при регистрации не trim-ится.
- Отдельный cookie `__Host-nd_customer` для HTTPS: Secure, HttpOnly, SameSite=Strict, Path=/, без Domain. Только для строго loopback тестового режима используется nd_customer без Secure.
- Анонимная форма: 30 минут; клиентский сеанс: 8 часов. После входа токен заменяется, старый удаляется; при восстановлении пароля удаляются все клиентские сеансы.
- CSRF хранится в хешированном виде, вычисляется из случайного session token; клиент передаёт X-CSRF-Token. Владелец использует существующий независимый CRM CSRF.
- Ссылки verify 24h, invite 48h, reset 30min; single-use. Account row затем token row блокируются FOR UPDATE в одинаковом порядке; успех и смена состояния фиксируются одной транзакцией. Истечение/повтор/disable отвергаются.
- Исходный токен только в URL fragment; customer.js сразу удаляет fragment из текущего URL, хранит значение только в памяти вкладки. Никаких токенов в localStorage/sessionStorage. GET не активирует аккаунт и не меняет пароль. Referrer-Policy:no-referrer и существующий CSP сохраняются без unsafe-eval/inline scripts.
- Rate limits 15 минут: 120 customer requests/IP, 20/route/IP, 8/email/action, 30 owner operations/IP, 5 приглашений/email. IP/identity keys хешируются; истёкшие limit buckets удаляются ограниченными порциями.
- Unknown/wrong/unverified/disabled login — одинаковый 401. Public register/reset/resend дают одинаковый 202 без подтверждения существования аккаунта/доставки. Dummy bcrypt verify уменьшает различия времени login. Синхронная SMTP отправка означает, что полное выравнивание времени всех сценариев не гарантируется; сохраняются rate limits и нейтральные ответы.
- PDO prepared statements, authorization в backend, безопасные ошибки. SQL/exception text/SMTP replies не попадают в публичный ответ или security events. UI использует textContent, сохраняет поля при сбое и блокирует повторный submit.

## Почта

customer_mail в private/config.php: transport=smtp, host, port, encryption=starttls или ssl, from, username, password. Обязательны TLS 1.2+, проверка сертификата/имени и SMTP AUTH только после шифрования. Нужен PHP OpenSSL и исходящий доступ к SMTP провайдеру. Credentials только вне Git.

Транспорт выполняет до двух попыток. Успех — только SMTP 250 после DATA; это acceptance провайдером, не доказательство доставки в Inbox. Сбой оставляет аккаунт неподтверждённым, записывает только mail_failed. Клиент может повторить resend/forgot, владелец — приглашение по существующему ID; новый токен отменяет предыдущий. У владельца отображается последний mail_accepted/mail_failed. При неизвестном исходе SMTP теоретически возможна повторная доставка одного письма: token одноразовый, аккаунт не дублируется.

Тестовый transport=test-smtp работает только при customer_auth_test_mode=true, loopback app_url и loopback SMTP host. Тестовый сервер хранит письма в памяти процесса, не отправляет их наружу и не создаёт spool. Реальные TLS SMTP credentials/доставку провайдером необходимо проверить отдельно на release staging; production email этим этапом не отправлялся.

## Privacy и выпуск

По умолчанию customer_auth_enabled=false и customer_auth_privacy_approved=false. Дополнительно обязательны существующий privacy_policy_approved=true, непустой private/privacy-policy.txt и валидная версия. customer_auth_privacy_approved означает отдельный review применимости документов к аккаунтам, email и приглашениям: утверждение старого документа только для лидов автоматически не открывает регистрацию. HTTPS обязателен вне изолированных тестов.

Тексты политики не сочинялись, флаги production не менялись, правовое соответствие не заявляется. До включения владельцу/юристу необходимы решения о документах/основании приглашений, сроках хранения аккаунтов и security events, правах клиента/удалении данных и применимости почтового сервиса.

005 запускается только после journalled/checksummed 004. scripts/migrate-customer.php — CLI-only status/up/down, общий advisory lock с 004, checksums, учёт каждого DDL шага. MySQL DDL не выдаётся за транзакционный: частичная операция видна как applying, повтор up блокируется. Down разрешён лишь при полностью пустых пяти таблицах под WRITE locks, не существует force rollback. Старые accounts/customers/admin/leads не изменяются миграцией.

Существующий release.py/remote.php расширен allowlist новых файлов и приватной доставкой scripts/migrate-customer.php и SQL. Старый workflow сохранён; второй механизм доставки не создавался. Agent знает порядок 004 → 005 и выполняет их только после backup/healthy recovery verification; SQL/CLI никогда не помещаются в public_html. В policy.json обе миграции остаются automatic=false/required=false: это не разрешение применения. Feature flag и проверка applied обоих journal states не позволяют запустить регистрацию при неполной схеме.

Перед production: интеграция #4, review Stage 4, verified release/backup recovery, явное одобрение checksum-политики автоматического 005, SMTP staging и legal review. Никакого ручного импорта SQL/загрузки ZIP владельцем эта ветка не требует. Сама ветка/черновой PR не запускает production job и не меняет конфигурацию SpaceWeb.
