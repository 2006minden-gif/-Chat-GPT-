# Issue #8 — безопасное завершение bootstrap CI/CD

Дата проверки: 24.10.2026. Issue: https://github.com/2006minden-gif/-Chat-GPT-/issues/8.

## Итог

**AUTOMATIC DEPLOYMENT NOT YET VERIFIED.** Исправления подготовлены отдельно от main; production-публикация и изменения production config/БД не выполнялись. Нельзя закрывать #8 по одному зелёному CI: acceptance `deployed_and_verified` на SpaceWeb пока не получен.

Исходный main: `22ff5d7b7d5685f1ee73ec561f670e6a65c444a3`. Сохранены Stage 3 `968c82dabf4d8b42bdfabaf0972ebfc8d8b49165` и Stage 4 `92f2b22109509eb6e85e7d5e68160db28f83f633`; в fix-ветку не включены ни их миграции, ни customer authentication. PR #4 и #7 остаются draft. Никакие settings защиты, секреты и privacy flags не менялись этим ходом.

## Реальная авторизованная проверка GitHub

Локальный `gh` не имеет работающего API-доступа: proxy возвращает Forbidden. Это не доказывает отсутствие Git read/write — push отдельных веток работает. Для аудита использован `gh api` на GitHub-hosted runner с штатным GITHUB_TOKEN.

Доказательство: Actions **40093868285**, commit `dd44fec`; JSON в `automation/evidence/runs/40093868285-1.json`.

| Объект | Подтверждённый результат |
|---|---|
| production environment | API 200; custom branch policy — только main, type=branch |
| automation environment | API 200; custom branch policy — только main, type=branch |
| Дополнительные environment review/wait rules | В доступном API только branch_policy; ничего не сбрасывалось |
| Classic protection main | API 403 Resource not accessible by integration — UNVERIFIED |
| GraphQL main branchProtectionRule | Resource not accessible by integration — UNVERIFIED |
| Effective rulesets endpoint | API 200, [] — это НЕ доказательство отсутствия classic protection |
| Repo/env secret metadata, repo variables, workflow permission settings | API 403 — административный аудит этих данных недоступен текущему токену |

Заявленные владельцем защита main/required Validate и значения административных variables не выдаются за самостоятельно проверенные. Бот не может повысить права своего GITHUB_TOKEN.

## Подтверждённый SpaceWeb preflight

Read-only Actions **40094406957**, source `f577218`: все шесть SSH переменных непустые в разрешённом workflow context. Значения не выводились. SSH strict host verification прошла, shell действительно доступна. Использованы существующие credentials/known_hosts; keyscan и auto-accept не использовались.

Read-only Actions **40094811460**, source `a43881f`: `/usr/bin/php8.4` действительно запускает **PHP 8.4.27**, доступны pdo_mysql и mbstring. `/usr/bin/php` на этом аккаунте — **PHP 5.2.17**, поэтому прежнее default php не подходит агенту. Исправлен default клиента на `/usr/bin/php8.4`; явный корректный PHP_CLI override по-прежнему поддерживается.

При попытке загрузки существующего private/config.php обнаружен **ParseError, строка 12**. Приватный журнал подтверждает тот же тип/файл/строку и request IDs. Содержимое конфига/секретов не экспортировалось и не переписывалось. PDO connectivity, данные администратора и схема этой диагностикой НЕ проверены: parse error происходит раньше подключения к БД.

HTTP health завершён технически, но FAIL:

- `/`, `/studio.php` → 200.
- `/api.php?r=privacy` → 503 application/json, request ID `55ac6faddcfcdc8a`.
- `/privacy.php` → 503 application/json, request ID `d9e3b336fde1a6ad`.
- `/~.htaccess`, `/index~.html` → HEAD 200; content в отчёт не выгружался.
- приватный config URL → 404; прямые index.html/crm.html → 403; unauthenticated session/leads → 401.

Actual server code hashes (не hashes config/credentials):

| Путь на сервере | SHA256 |
|---|---|
| public_html/.htaccess | eb8eeae2b95fa90098344d60143a01e6fe82d4f1834b1f37beba7ca8cadf4705 |
| public_html/privacy.php | 23add180c078aa8d4aa7dd48a658100a7e37ebed071b07f8303d10f16b88ab08 |
| public_html/api.php | 087929c654366f659fe06e9a74a03a9f6933fb9ed37367a6deda7fc38e93af80 |
| private/app.php | 69d6df77c05be2e8cba592deb43462bba0b90fca383d6098ecda89a0942fc4d0 |

.htaccess, privacy.php и app.php отличаются от main; API совпадает. Это подтверждает, что состояние GitHub не равно состоянию сервера. Исходный SSH blocker `account unavailable` в новой проверке больше не воспроизводится.

## Исправления в отдельной PR-ветке

1. **control.py/bootstrap** принимает union repository- и production-environment secret names. Никакого требования переносить ключ, удаления repository secret, получения plaintext или повторного ввода существующих SSH secrets. Метаданные не выдаются за проверку работоспособности credentials.
2. Bootstrap проверяет существующие main/env policies, не отправляет PUT branch protection и не сбрасывает reviewers/wait timers/environments. Единственный scope изменения — automation variables после административной авторизации. READY выставляется false и не повышается.
3. Нативный review gate ≥1 сохранён. CI-only opt-in не включён: отдельного согласия владельца на изменение review policy нет. Созданный ботом PR может получить настоящее review владельца, но это остаётся человеческим действием; при self-authored PR нужен независимый reviewer. Самоодобрения API и --admin bypass отсутствуют.
4. Обычный GITHUB_TOKEN merge не считается источником push CI. Есть явный dispatch существующего deploy.yml на main с exact expected_revision. SHA проверяется перед CI и перед публикацией; artifact должен соответствовать этому SHA. Для dispatch используется узкий GITHUB_TOKEN с actions:write, даже если App применён для чтения protection/merge.
5. READY=false даёт только CI/preview. Первый bootstrap требует CONFIGURED_SHA и отдельного APPROVED_SHA, совпадающих с текущим main, уже прошедший main Validate, затем собственный новый Validate и main-only production environment. DEPLOY_PAUSED блокирует bootstrap; исключения emergency pause остаются лишь для preview/rollback.
6. Bootstrap запрещает migration entries и не передаёт 004/005 в автоматическое исполнение. Preflight должен пройти; unhealthy baseline останавливает bootstrap до transfer/backup/apply. Известные production ошибки не маскируются как успех и не обходятся ради первого зелёного статуса.
7. Agent копирует backup кода в private recovery scratch, сверяет hashes и убирает scratch; после применения фиксирует реальные hashes всех 14 управляемых файлов. Защищённые config/policy/uploads не входят в managed copy.
8. Отдельная административная операция promote принимает лишь успешный trusted main workflow_dispatch, где Validate и Publish прошли, bootstrap report подтверждает healthy before/after, отсутствие миграций, actual file/asset hashes, backup/recovery и финальный server state. READY=true — последняя запись; SHA/run proof сохраняются, одноразовое APPROVED_SHA очищается. Неуспешный/чужой/устаревший run не разблокирует публикацию.
9. Manual-only bootstrap.yml — однократное управление GitHub variables, не второй deploy: нет SSH, rsync, SQL и доступа к production secret values. Оно использует временную admin grant только из main-only automation environment. Реальная доставка остаётся только в существующем deploy.yml.
10. Commit status с именем Validate не может заменить настоящий successful check GitHub Actions app_id=15368.

Изменены: `.github/workflows/deploy.yml`, `auto-merge.yml`; новый `bootstrap.yml`; `scripts/github/control.py`, новый `bootstrap.py`; `scripts/deploy/client.py`, `remote.php`; `tests/test_bootstrap.py`, `test_deploy_workflow.py`, `test_release_pipeline.py`; эта документация и указатели из CICD.md/CICD-REPORT.md. Дополнительные read-only relay changes находятся только в automation/github-control, не в main.

## Проверки

Полный локальный набор fix-ветки: **77 Python PASS**, 0 FAIL/0 SKIP; **12 Node PASS**. PHP 8.4.27, изолированный MySQL 5.7.42, настоящий Apache/Chromium. Проверены backup/restore/rollback с реальными файлами, секреты/config/uploads сохранены, dry-run без writes, минимальный secret metadata union, stale SHA, подделка Validate status, неподтверждённый run, реальный ZIP reader evidence, READY-last, review retention, manual main-only admin workflow. Hosted CI статус и PR ссылка фиксируются отдельно после push; локальные проверки не подменяют GitHub Actions.

PHP/JS syntax, compileall, actionlint, release policy check, diff --check и redacted Gitleaks — PASS. Синтетические тесты восстановления не выдаются за выполненный production rollback; actual production deploy SHA/run отсутствуют, потому что first-write prerequisites не пройдены.

## Какие действия действительно требуют владельца

**Уже настроено, не повторять:** оба main-only environments, существующие SSH credentials/known_hosts, работающий SSH. Перенос/перегенерация SSH ключа не нужен.

1. **Настоящий review отдельного fix PR и интеграция по существующей защите.** Codex не может подделать owner's approval или слить PR через --admin. #4/#7 остаются draft и не включаются в эту интеграцию.
2. **Однократная административная авторизация для metadata/variables.** После review доступен workflow `One-time CI/CD administration` на main. Для него owner создаёт краткоживущий fine-grained grant только на этот repository: Administration read, Actions read, Contents read, Secrets read, Environments read, Variables write; кладёт его как `BOOTSTRAP_ADMIN_TOKEN` в environment automation (не чат/Git). Никаких Secrets write или Administration write скриптам не требуется. Альтернатива — те же проверенные CLI операции в уже авторизованной admin среде. Configure оставит READY=false, проверит metadata и зафиксирует CONFIGURED_SHA; если реальные правила недостаточны, он остановится, не меняя их.
3. **Право runtime-контроллера читать main protection.** Текущий GITHUB_TOKEN классическую защиту читать не может. Если существующий App не настроен, owner может установить App только на этот repo: Administration read, Contents write, Pull requests write, Checks read, Actions read, Metadata read; ID в AUTOMERGE_APP_ID, private key в automation/AUTOMERGE_APP_PRIVATE_KEY. App НЕ нужен для порождения main CI: эту задачу выполняет SHA-bound dispatch. Но при нынешней недоступности classic protection нужен App/read grant либо проверенный эквивалентный читаемый ruleset; добавление ruleset должно сохранить более сильные существующие ограничения. Наличие App variables/secrets текущим токеном не проверено — нельзя объявлять их отсутствующими.
4. **Первое разрешение production smoke для точного reviewed main SHA** через BOOTSTRAP_APPROVED_SHA, только после исправления config syntax и прохождения preflight/health. Планировщик выполнит dispatch сам; повторных routine deployment кнопок нет. После реального успешного smoke администратор однократно запускает promote с его run ID; подмена/ранний запуск не разблокируют READY. Затем временный BOOTSTRAP_ADMIN_TOKEN удалить/отозвать; не превращать его в постоянный runtime token.
5. **Если нужен полностью CI-only merge без человеческого review — отдельное явное решение владельца.** Сейчас такое изменение не авторизовано и не реализовано. При сохранении независимого review полностью hands-off merge невозможен: genuine approval остаётся обязательным, deployment после него может быть автоматическим.

Production blockers, не задача ручного редактирования владельцем: исправить ParseError config.php:12, сохранив все секретные значения, и восстановить ожидаемую защиту backup URLs/health через отдельную проверенную repair/release процедуру. Ни пересылка конфига в чат, ни ручной SQL/ZIP, ни скриншоты не требуются. В этом ходе production-файлы не менялись, поскольку preflight и native review ещё не пройдены.

До выполнения этих условий первый verified smoke, promotion и полноценная acceptance #8 остаются заблокированы. Административные scopes/branches не ослаблялись, issue не закрывается автоматически.
