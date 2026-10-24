# Stage 2.1 — безопасная GitHub-интеграция

Ветка: `integrate/stage-2-1-safe-workflow`, основана на `stabilize/stage-2-1` (`78fb800`). Исходный main `37df861` сохранён без переписывания истории. Включены одобренные d688bca, 6d8c146, f3bdbd8 и документационная проверка 78fb800.

Новые коммиты: `de3a4ba` (workflow и 6 safety-тестов), `8b5b871` (подготовленное описание PR); данный отчёт добавлен отдельным документационным коммитом. Код приложения дополнительно не менялся, схемы/миграции/исходники/деплой сохранены. Изменены `.github/workflows/deploy.yml`, добавлены `tests/test_deploy_workflow.py`, `docs/SAFE-INTEGRATION-PR.md` и этот отчёт.

## Проверка безопасности

В предлагаемом deploy.yml только workflow_dispatch; job дополнительно ограничен ручным событием и refs/heads/main. Push и merge не запускают этот workflow. Реальная публикация требует одновременно dry_run=false, ввода `PUBLISH neurodelo.pro`, DEPLOY_ENABLED=true. По умолчанию dry_run=true. Ввод передаётся через env, не вставляется в shell-код. Настоящие секреты не запрашивались и не менялись.

Dry-run не выбирает backup-шаг и передаёт --dry-run обеим командам rsync. Проверка сервера содержит только read-only preflight. В тестах ssh/rsync заменены локальными заглушками; реального соединения не было. Прежние host-key checks, ограничения путей, permissions/concurrency, приватный backup, исключения config/policy и cleanup сохранены.

Это подтверждает безопасность **предлагаемой версии**, а не изменение текущего main. До слияния main содержит старый workflow. Ранее записанный в исторических отчётах риск неизвестного DEPLOY_ENABLED устранён для автоматического запуска предлагаемой версией: даже true больше не включает публикацию от push. Флаг сохранён как дополнительное условие ручной публикации. Внешние интеграции и настройки вне исходников не проверены.

## Выполненные проверки

- actionlint 1.7.7 — PASS: YAML, события, типы и выражения. ShellCheck/Pyflakes отключены, bash -n для всех shell-шагов выполнен отдельно.
- 6 workflow-тестов — PASS (условия ручной авторизации, неверные/неполные подтверждения, инъекция через ввод, dry-run, backup, rsync-исключения, SSH-проверки).
- 12 клиентских + 12 интеграционных + 2 Apache-теста — PASS; всего 32 теста, 0 FAIL.
- PHP lint 9 файлов, JS syntax 3 файла, git diff --check — PASS.
- Локальная проверка merge-tree с актуальным main — без конфликтов; это не merge веток.

Интеграционная среда: PHP 8.4.27, Apache 2.4.69, MariaDB 11.8.6, Chromium/Playwright. Точный MySQL 5.7 не запускался. Только случайная локальная neuro_test_* БД и временная копия, без production-данных.

Повторить workflow-проверку: Python с PyYAML 6.0.3, `python -m unittest discover -s tests -p test_deploy_workflow.py -v`. Линтер: `actionlint -shellcheck= -pyflakes= .github/workflows/deploy.yml`. Интеграционные команды описаны в STAGE-2.1-REPORT.md. SSH/rsync не требуются для safety-тестов и не должны заменяться настоящими командами.

## PR и GitHub Actions

Ветка опубликована. Попытка `gh pr create --repo 2006minden-gif/-Chat-GPT- --base main --head integrate/stage-2-1-safe-workflow --title ... --body-file docs/SAFE-INTEGRATION-PR.md` завершилась exit 1: `Post https://api.github.com/graphql: Forbidden`. PR этой попыткой не создан; номер PR не подтверждён. GitHub Actions API также Forbidden, поэтому результаты Actions UNVERIFIED. Локальные PASS не выдаются за GitHub CI. Workflow вручную не запускался; deploy.yml не запускает CI на PR.

[Открыть подготовленный PR с заполненными полями](https://github.com/2006minden-gif/-Chat-GPT-/compare/main...integrate/stage-2-1-safe-workflow?expand=1&title=Stage+2.1%3A+fixes+and+manual-only+deployment&body=Stage+2.1%3A+reviewed+fixes+plus+manual-only+production+deployment.%0A%0AFull+description+and+test+results%3A+https%3A%2F%2Fgithub.com%2F2006minden-gif%2F-Chat-GPT-%2Fblob%2Fintegrate%2Fstage-2-1-safe-workflow%2Fdocs%2FSAFE-INTEGRATION-PR.md%0A%0ANo+automatic+merge+or+production+deployment+authorized.+Stage+2.2+is+pending+integration+approval.)

Минимальное ручное действие: открыть ссылку, проверить base=main и compare=integrate/stage-2-1-safe-workflow, нажать **Create pull request**. Если GitHub уже показывает существующий PR, открыть его вместо создания дубликата. Название и описание уже заполнены; полный текст лежит в SAFE-INTEGRATION-PR.md. Кнопку Merge и auto-merge не нажимать до одобрения интеграции.

## Следующий этап и разрешения

Слияние технически подготовлено и предложенный workflow проверен. Само слияние не выполнялось и остаётся отдельным одобрением. Публикация на production не разрешена этой интеграцией. Нет обращения к SpaceWeb или изменения его файлов, настроек, данных, учётных записей.

Stage 2.2 пока не реализуется: условие пользователя — сначала одобрение интеграции. План отдельной ветки `fix/stage-2-2-form-and-login` от одобренного интегрированного main: сохранить правки полей, сделанные после начала отправки, не показывать ошибку пароля/сессии при первом открытии CRM, добавить браузерную регрессию обоих случаев, сохранить дизайн/PHP API и проверить workflow на случайную публикацию. Эта ветка пока не создана, в текущем PR изменений Stage 2.2 нет.

Production 503 и реальная авторизация не диагностировались в этой задаче. Юридическое согласование по-прежнему требуется для реального сбора данных; fail-closed сохранён. Старый ZIP не обновлён. До одобрения следующего этапа работа останавливается.

AWAITING APPROVAL.
