# NeuroDelo — CI/CD и проверка доступа GitHub

Дата: 24.10.2026. Ветка `ci/automatic-spaceweb` от main `977170a`. Коммиты: `c7bba43` — utf8mb4 test helper; `484c136` — автоматический CI/CD/agent/recovery/governance; `6abbd8c` — hardened bootstrap/backup, тесты и инструкция; данный отчёт отдельным документационным коммитом.

## Итог

**AUTOMATIC DEPLOYMENT NOT YET VERIFIED — исходящий CONNECT-прокси блокирует api.github.com (403), поэтому не созданы/не проверены PR, защита main, environments/App и результаты Actions. Новый pipeline не слит в main, на SpaceWeb не запускался.** Сетевое разрешение на ход было запрошено и выдано, но доменная блокировка осталась. Не путать это с доказанным отсутствием прав в самом GitHub.

Исходники подготовлены и проверены локально. Полный путь GitHub→CI→approved main→SpaceWeb не объявляется выполненным по одному YAML. Есть дополнительные исходные production failures (ниже); они не выдаются за регрессию автоматики или успешный health.

## Запрошенная отдельно проверка read/write

**Git read/write работает.** Проверены чтение репозитория/main, создание ветки и коммита, push, фактическое скачивание файла из GitHub в отдельный пустой bare-репозиторий, точное совпадение содержимого/commit SHA, удаление ветки и отсутствие удалённого ref. Main до/после одинаков, production workflow временной веткой не запускался: она создана от main с manual-only workflow, не от CI-ветки.

```json
{
  "repository": "2006minden-gif/-Chat-GPT-",
  "main_before": "977170a0621253ef394c42d5f239c9505e177de6",
  "branch": "access-check/20261024-704dbfccba53",
  "test_commit": "9bab923444b6ccc6906b21b0d8791949fd271a04",
  "read_main": true,
  "push_branch": true,
  "remote_file_readback": true,
  "temporary_branch_deleted": true,
  "main_after": "977170a0621253ef394c42d5f239c9505e177de6",
  "main_unchanged": true,
  "production_workflow_triggered": false
}
```

Тестовый файл `.codex-access-check.txt` существовал только во временной ветке; её локальная worktree/ветка также удалены. Current main прочитан и оставлен на `977170a0621253ef394c42d5f239c9505e177de6`. Git API/administration доступ **не** следует из успешного Git push. Видимость public/private не подтверждена: API недоступен, неавторизованная web-страница Actions возвращает 404. При этом авторизованный Git-канал читает/пишет текущий репозиторий независимо от его текущей видимости.

## Что реализовано в исходниках

1. `.github/workflows/deploy.yml`: CI каждого push и PR; только main публикуется после обязательного Validate. Без ручных галочек/phrase для обычных main обновлений. Explicit maintenance preview/deploy/rollback остаётся. Artifact привязан к SHA, старый main пропускается, публикации сериализованы. Production секреты используются только publish step deploy job в environment production, не validate/PR jobs.
2. `.github/workflows/auto-merge.yml`, `scripts/github/control.py`: доверенный main workflow/App создаёт PR после успешного CI внутренней ветки; включает native auto-merge только актуального независимо approved head с passing checks и проверенной защитой main. Native GitHub policies и match-head-commit сохраняют защиту от гонки. App нужен также для порождения нового push CI после merge; обычный GITHUB_TOKEN не подходит. Непроверенная ветка/артефакт не выполняется привилегированным workflow. One-time bootstrap сохраняет более строгие checks/review counts, закрывает bypass, настраивает main-only environments и проверяет metadata секретов; их значения не читает/не меняет.
3. `scripts/deploy/release.py`, `policy.json`: 14 allowlisted production code-файлов, включая .htaccess; нет config.php, политики, setup.php, тестов, dumps или ключей. Manifest/revision/checksums, строгое правило миграционного approval.
4. `scripts/deploy/client.py`, `remote.php`: строгий SSH/known_hosts, только приватный rsync staging; проверка PHP/PDO/baseline; timestamped backup управляемого кода до записи; same-directory atomic rename каждого файла. config/policy/uploads/cgi-bin сохраняются. Нет --delete. Ротация сохраняет latest good + pinned DB recovery, незавершённые состояния не перетираются.
5. `scripts/deploy/health.py`: 17 read-only checks + public asset SHA. Baseline/API 503 и backup exposure учитываются как failures, легально закрытая форма при корректном disabled API не считается ошибкой. Новая регрессия → файловый rollback → checksums и HTTP baseline. Неподтверждённое восстановление не называется успешным. Прежние неизменные провалы могут оставить полезные approved исправления, но job/state остаётся FAILED/unhealthy, не known-good.
6. Dev requirements зафиксированы. GitHub CI использует PHP 8.4, MySQL 5.7.44 service, Apache, Python 3.12/Playwright, Node 22. actionlint/actions pinned, все имеющиеся test_*.py запускаются без continue-on-error. Новая миграционная папка без CLI/compatibility/regression suite блокирует сборку.
7. Новые тесты в `test_release_pipeline.py`, обновлённые `test_deploy_workflow.py`, utf8mb4 фикс в test_prelaunch.py. Публичный PHP/JS, дизайн, DB schema не менялись.

Полная настройка, file layout, retention и recovery: [CICD.md](CICD.md).

## Реально выполненная локальная проверка

| Проверка | Результат |
|---|---|
| Полный Python unittest discover | 62 PASS, 0 FAIL, 0 SKIP |
| Node API-client unit | 12 PASS |
| PHP syntax public/private/scripts/tests | 10 PASS |
| JavaScript syntax | 3 PASS |
| actionlint 1.7.7 с SHA256 (без ShellCheck/Pyflakes), bash -n | PASS |
| Политика release/migrations, compileall, git diff --check | PASS |
| Fresh Git remote readback + push/delete тестовой ветки | PASS |

Python-матрица: 14 исходных PHP/API/Chromium тестов, 2 настоящего Apache, 7 workflow-contract tests, 39 pipeline/recovery/governance/health тестов. После последних точечных hardening изменений 39 pipeline-тестов повторены отдельно — PASS. Bootstrap REST настройки проверены на фальшивом API, **не** на реальных settings GitHub.

Среда: PHP 8.4.27, **настоящий изолированный MySQL 5.7.42**, mysqldump 5.7.42, Apache 2.4.69, Chromium/Playwright, Python. CI сконфигурирован на MySQL 5.7.44, но реальный CI run/result из GitHub недоступен; его нельзя помечать PASS. Production patch 5.7.27 отдельно не проверен.

Не только mocks: PHP-agent реально применял/откатывал файлы в временном дереве, проверял хеши и protected files, валидировал конфликты ручных правок, ротацию, symlink safety и good snapshots. Создан реальный private mysqldump перед **синтетической** одобренной добавочной миграцией; этот dump импортирован в другую случайную neuro_test_restore_* БД, admin rows сравнены. Реставрация не шла поверх исходной тестовой БД и не затрагивала production. Синтетический migration operator не является тестированием ещё не слитого Stage 3 runner.

SSH transport/Actions coordinator и некоторые отказные сценарии тестировались заглушками. Нет утверждения о выполнении удалённого PHP-agent на SpaceWeb, реальной site rollback или настройке GitHub protections. Прежний успешный SSH dry-run сообщил владелец; он не доказывает новую полную цепочку.

Репродукция на подготовленной изолированной среде:

```sh
PATH=/tmp/neuro-runtime:$PATH PYTHONPATH=/tmp/neuro-runtime/python NEURO_TEST_DSN='mysql:host=127.0.0.1;port=33078' PHP_BIN=/tmp/neuro-runtime/php APACHE_BIN=/tmp/neuro-runtime/apache APACHE_MODULE_DIR=/tmp/neuro-runtime/root/usr/lib/apache2/modules python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/api-client.test.cjs
```

В GitHub используются те же suites с dev requirements/browser/install шагами, не перенос /tmp binaries. Missing dependency/test → fail-safe, не skip. Тестовые БД случайные loopback-only, реальные leads/passwords не загружались.

## Независимые production-проблемы

Свежие GET/HEAD до какой-либо публикации этой ветки:

| Путь | Статус | Content-Type / Request ID |
|---|---|---|
| / | 200 | HTML |
| /studio.php | 200 | HTML; это не подтверждённая авторизация |
| /privacy.php | 503 | JSON, 17bc23643c20b574 |
| /api.php?r=privacy | 503 | JSON, 06fa1e13ff843264 |
| /~.htaccess | HEAD 200 | text/plain |
| /index~.html | HEAD 200 | text/html |

Backup content не скачивался, секреты в нём не утверждаются. Root cause приватного 503 без server log/config доступа **не установлен**, credentials не запрашивались. Новый preflight выдаст безопасные type/basename/line и PDO readiness, а health сохранит request IDs при разрешённом реальном запуске. Нельзя включать privacy approval/приём PII ради зелёного deployment. Пока эти проверки не пройдут, автоматике запрещено заявлять здоровый release.

## Миграции

Список `policy.json:migrations` пуст. Stage 3 source не слит и в CI-ветку не переносился. Никаких production DDL или fixture imports нет. При будущем reviewed checksum entry разрешается только поддерживаемая additive 004, с DB backup, journal/state проверкой и совместимостью старого приложения. required manual migration без applied state блокирует выпуск. Destructive/irreversible не выполняются автоматически, нет force, automatic down или database restore. Нужен отдельный одобренный maintenance-план/оператор. Подробный pre-migration recovery план в CICD.md; автоматический SQL restore поверх живой БД намеренно отсутствует.

## Rollback и ограничения

На новой регрессии workflow сам пытается вернуть только управляемый код текущей попытки, не старый успешный release по ошибочному ID. Проверяются backup/candidate/current hashes до первой restore операции и served HTTP/asset baseline после. При чужих правках/битом backup/SSH failure — отказ и UNVERIFIED, без затирания файлов или ложного успеха. При сохранённой прежней неисправности результат остаётся FAILED, даже если файлы восстановлены к такому baseline. DB/config/policy не откатываются. Atomicity — по одному файлу, не транзакционный switch всего сайта.

Emergency recovery после одноразовой настройки — maintenance operation=rollback из main, не ручные SSH-команды. Routine deployment не требует запуска этого workflow вручную. Pending state после насильственного прерывания не перезаписывается новой попыткой; сначала recovery. Privileged assets/credentials нельзя класть в public_html. Quota/CLI/proc_open/permissions/backup restore на реальном хостинге ещё требуют живого подтверждения.

## GitHub integration и точный blocker

git push CI-ветки прошёл. Попытки gh pr create и gh run list завершились Forbidden. Bootstrap --apply остановился на первом **GET repository**, до любых PATCH/PUT/POST; main protection/environments/variables/secrets не менялись. Проверка urllib установила `Tunnel connection failed: 403 Forbidden` для api.github.com. Выданное сетевое разрешение не сняло этот фильтр. Публичная web-страница Actions 404 не даёт проверить private runs.

[Создать первый подготовленный PR](https://github.com/2006minden-gif/-Chat-GPT-/compare/main...ci/automatic-spaceweb?expand=1&title=Automate+approved+NeuroDelo+releases+with+CI+and+verified+recovery&body=Automatic+CI%2FCD+implementation+and+local+verification.%0A%0AFull+report%3A+https%3A%2F%2Fgithub.com%2F2006minden-gif%2F-Chat-GPT-%2Fblob%2Fci%2Fautomatic-spaceweb%2Fdocs%2FCICD-REPORT.md%0ASetup+and+recovery%3A+https%3A%2F%2Fgithub.com%2F2006minden-gif%2F-Chat-GPT-%2Fblob%2Fci%2Fautomatic-spaceweb%2Fdocs%2FCICD.md%0A%0AProduction+deployment+is+NOT+YET+VERIFIED.+Review+required+before+initial+integration%3B+no+bypass+of+main+rules.)

Только первоначальная интеграция при нынешнем API-блокере требует этого browser шага; после установки доверенного workflow/App будущие PR создаются самим GitHub после branch CI, Codex достаточно git push. Не обходить текущие review/check rules ради первого merge. Автослияние и публикация этой ветки не выполнялись.

Однократно требуется:

1. Разрешить api.github.com исходящему GitHub-управлению Codex либо предоставить рабочую GitHub-интеграцию с нужным админ-доступом; Git transport уже исправен, повторно проверять пароль/SSH ради этого не нужно.
2. Проверить/настроить main protection, production/automation environments и metadata App/секретов скриптом bootstrap по CICD.md. Наличие этих настроек пока **неизвестно**, а не доказанно отсутствует. Нераскрываемый API секрет переносится владельцем в GitHub UI только если ещё не перенесён; никаких паролей, PAT или private keys в чат.
3. Одобрить первую интеграцию по правилам репозитория. Перед включением ordinary deployments убедиться в PHP CLI/host preflight и диагностировать старые 503 приватно через разрешённый канал. Не просить владельца разбирать PHP или присылать screenshots.
4. Выполнить настоящий controlled reviewed no-product-change run и сохранить evidence. Рутинные дальнейшие выпуски — автоматические; отдельные approval сохраняются для кода PR и destructive migrations.

## Восемь пунктов реальной end-to-end проверки

| Пункт | Факт сейчас |
|---|---|
| Код отправлен в GitHub | VERIFIED, CI-ветка и независимый read/write roundtrip |
| CI реально запустился автоматически | NOT VERIFIED: событие предусмотрено, metadata runs недоступна |
| Required checks реально прошли в GitHub | NOT VERIFIED; локально PASS |
| Одобренное изменение дошло до main | Не выполнялось, main сохранён |
| Автоматический deploy стартовал | Не выполнялось |
| SpaceWeb получил новые файлы | Не выполнялось |
| Production health прошёл | Не прошёл в текущем baseline; см. 503/200 backup |
| GitHub записал реальный deployment result | NOT VERIFIED |

Никаких изменений БД/файлов SpaceWeb или настроек видимости репозитория в этой работе нет. Подготовка кода не является production delivery.

**AUTOMATIC DEPLOYMENT NOT YET VERIFIED — GitHub API blocked by CONNECT proxy; bootstrap/main integration and real CI→SpaceWeb health evidence are not completed.**
