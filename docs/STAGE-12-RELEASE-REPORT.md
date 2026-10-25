# Stage 12 — решение автоматических release gates

Дата: 25.10.2026. **Результат: RELEASE_BLOCKED.** Боевой выпуск не выполнялся.

## Разрешение владельца

Владелец разрешил автоматическую публикацию проверенных обновлений без повторного per-release подтверждения. Прежние требования повторного owner approval именно для обычной публикации заменены этим разрешением; коммерческие/правовые approvals остаются самостоятельными. Это разрешение действует только после прохождения всех обязательных technical gates. Оно не утверждает коммерческие цены/предложения/передачу клиентских результатов и не включает privacy/legal/payment/paid-AI флаги. Эти бизнес-проверки сохранены.

В существующем `.github/workflows/deploy.yml` уже есть автоматическая публикация main после Validate и bootstrap/environment проверок. Новый deploy workflow, SSH способ или механизм публикации не создавались. Production environment/branch protection/variables сейчас недоступны через API; нельзя утверждать, что они перенастроены. Отдельный ручной gate не добавлялся и владелец не должен повторно подтверждать готовый обычный релиз.

## Кандидат и фактическая версия

Кандидат приложения: `ba473cbac3d7dd13d7fe7dbd6f123b9c53808246` (интеграция Stage11). Main: `478ca7fad33016e4e1421795d2b768a9c9afd9c9`. Кандидат не является предком main и не был слит автоматически ради публикации. Его GitHub CI ранее успешно прошёл: run [40177897621](https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40177897621), обе publishing jobs skipped. Новые проверки этого задания: 278 Python tests PASS (229.899 с), 12 Node tests PASS, lint92 PHP / syntax15 JS PASS; actionlint, release policy, bundle checksum validation, git diff --check PASS. Gitleaks текущего дерева: утечек не найдено. PHP 8.4.27, MySQL 5.7.42, Apache 2.4.69, Chromium/Playwright; только изолированные loopback synthetic DBs. Успех этих проверок не заменяет FAIL release closure и NOT_VERIFIED production gates.

Точный текущий production SHA из private deployment state недоступен. Здоровый HTTP baseline не означает, что этот новый кандидат уже опубликован. Релизная процедура не запускалась, post-deployment smoke для нового релиза неприменим.

## Safety gates

| Проверка | Результат | Доказательство / причина |
|---|---|---|
| Полный applicable regression | PASS: 278/278, 229.899 с | изолированная PHP/MySQL/Apache/browser suite |
| Синтаксис / Node / workflow policy | PASS: PHP92, JS15, Node12, actionlint/policy | реальные локальные проверки |
| Существующий production HTTP baseline | PASS | 17/17 read-only HTTPS checks, TLS без отключения проверки |
| Полнота release candidate | **FAIL** | существующий сборщик отдаёт 14 app-файлов; отсутствуют необходимые модули и ссылки главной |
| Совместимость runtime production | NOT_VERIFIED для кандидата | PHP8.4/MySQL5.7 локально проверены, live private preflight/extensions/config/fs не выполнен |
| Политика unattended migrations | **FAIL для новой цепочки** | manifest migrations=[], исполнитель поддерживает только 004; нужны 005–012 зависимости новых функций |
| Действующий пригодный backup/recovery на сервере | NOT_VERIFIED | код и изолированные тесты есть, актуальный server state/backup hashes/recovery evidence недоступны |
| GitHub environment/protection/readiness variables | NOT_VERIFIED | API Forbidden; выгрузка variables/protection status403, deployment evidence отсутствует |
| Отсутствие критических дефектов | ограниченная локальная проверка | известный package blocker исключает выпуск; полный production security audit не заявляется |

Любой FAIL/NOT_VERIFIED обязательного gate запрещает выпуск. Разрешение владельца не подменяет техническое доказательство.

## Точный блокер пакета

`python scripts/deploy/release.py` реально собрал кандидат во временный каталог вне repository/production. `policy_check` и checksum validation проходят для старого allowlist, но не проверяют полноту нового приложения.

`scripts/deploy/policy.json`: public_files — базовый лендинг/первый CRM, private_files — только `.htaccess`, `app.php`; migrations — пусто. Среди обязательных отсутствующих файлов:

- `public_html/workspace.php`, `portal.php`, `customer.php`, `handoff.php`;
- `private/product-navigation.php`, `customer-auth.php`, `crm/routes.php`, `manual/routes.php`.

Главная `public/index.html` подключает `ai.css` и `ai-widget.js`, которых в manifest также нет. Это подтверждённое расхождение, а не предположение по документации.

Блокер не исправляется добавлением имён в JSON: `scripts/deploy/release.py` разрешает только плоские имена private файлов, а `scripts/deploy/remote.php::paths/verify_bundle` жёстко ограничивает тот же прежний состав. Для новой схемы нужны согласованные allowlist/closure/preflight/migration операторы в **существующем** механизме. Их изменение/переконфигурация прямо запрещены текущим заданием; поэтому ничего из этого не менялось. Нельзя выдать неполный пакет за проверенный выпуск.

## Миграции и восстановление

Аддитивные миграции и guarded CLI runners проверяются на случайных loopback neuro_test_* БД. Это не доказательство, что production journal соответствует им или что unattended оператор умеет их применять. `release.py::policy_check` и `remote.php::migrate_approved` автоматически поддерживают только 004. Новая цепочка не занесена в утверждённую policy, часть миграций имеет ALTER и свои отдельные safety guards. Универсальный auto-up не добавлялся, production SQL не выполнялся.

Existing rollback восстанавливает управляемые code files только после проверки backup/current hashes и конфликта посторонних изменений, затем проверяет HTTP baseline. SQL backup не импортируется автоматически. Данные, созданные после снимка, не восстанавливаются поверх текущих записей. В этом задании rollback не запускался: изменений на сервере нет. При недоказанном recovery gate публикация запрещена, а не сопровождается разрушительным «пробным» восстановлением.

## Реальная доступность сайта

`https://neurodelo.pro/` и `/studio.php`: HTTP200. Privacy API: HTTP200, enabled=false. `/privacy.php`: ожидаемый HTTP503 с объяснением отключённого приёма заявок — это корректный fail-closed ответ, не новая авария. Session/leads без авторизации: HTTP401. Backup-style `~.htaccess` и `index~.html`: HEAD403; `.htaccess`, `index.html`, `crm.html`: HEAD403; `/private/config.php`: HEAD404. Пять основных CSS/JS: HTTP200 с hashes. Все 17 checks PASS.

Проверки read-only: нет тестовых лидов, входа owner-паролем, отправки писем, платежей, AI-разговоров или чтения содержимого private config/backup. Private logs/runtime/backup state не читались. Поскольку нового выпуска не было, мониторинг его immediate deployment errors и подтверждение нового production SHA не выполнялись.

## Что требуется дальше

Нужна отдельная доработка полноты пакета и безопасных migration/preflight контрактов существующего deployment механизма, проверка на изолированном staging и доступное evidence текущего environment/backup/recovery. Это техническая работа, не просьба владельцу копировать команды, управлять БД, искать ключи или подтверждать каждый выпуск. В пределах текущего запрета менять deployment automation такие блокеры не устраняются обходным способом.

После устранения обязательных блокеров действующее разрешение автоматического выпуска сохраняется; дополнительный per-release owner confirmation не требуется. Live payments/новые платные AI/privacy-sensitive features не активировать побочным эффектом релиза.

## Изменения

Только этот отчёт в отдельной ветке `release/stage-12-gate-report`. Application code, `.github/`, `scripts/deploy/`, `scripts/github/`, schemas, main, secrets, hosting settings и production data не менялись. Никакого деплоя или автоматического восстановления БД.
