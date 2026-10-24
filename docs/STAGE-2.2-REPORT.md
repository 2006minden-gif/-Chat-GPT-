# Stage 2.2 — форма и первоначальный вход CRM

Дата: 24.10.2026. Ветка `fix/stage-2-2-form-and-login`, основание — main `ad4fb836b3b49858a6e6cb767bd7b62d440ec3a2` (merge PR #2 с безопасной интеграцией Stage 2.1). Проверено через fetch и ancestry; повторного слияния Stage 2.1 не требовалось. AGENTS.md ранее не найден. Исправления и тесты: коммит `c7b3a0b`; данный отчёт — отдельный документационный коммит.

## Выполнено

1. **Потеря новых правок формы.** Причина: после любого подтверждённого успеха вызывался form.reset без сравнения текущих значений с отправленными. В public/script.js выделено получение payload и добавлено сравнение с отправленным снимком. Если форма совпадает, она очищается как раньше; если изменена — все текущие значения и checkbox сохраняются, сообщение явно говорит о сохранении отправленной заявки и наличии ещё не отправленных правок. Ключ завершённого запроса очищается, следующая заявка получает новый ключ. Блокировка повторного submit в полёте и безопасный повтор после ошибки сохранены.
2. **Ошибка при первом открытии CRM.** Причина: общий обработчик 401 показывал ошибку пароля даже для первоначальной проверки session; внешний catch сравнивал текст, отличный от фактического безопасного сообщения API-клиента. В public/crm.js только первоначальный запрос session получает silentUnauthorized. По 401 показывается обычная форма без ошибки. Ошибки пароля при отправке login, 401 списка после успешной проверки session, 503/сеть и потеря сессии во время редактирования не скрываются. PHP/API-контракт не изменён.
3. **Регрессия.** В tests/test_prelaunch.py добавлены два браузерных метода. Первый проверяет отдельное изменение name/contact/service/idea/consent и всех полей во время удержанного успешного ответа: в БД остаётся исходный снимок, в форме — новые значения; повторный submit не создаёт запрос; следующее обращение после явного согласия имеет отдельный ключ/запись; неизменённая форма сбрасывается. Второй проверяет чистый начальный экран, ошибочный/верный пароль, восстановление существующей сессии при открытии страницы, настоящий 401 после session, logout, серверную и сетевую ошибку. Предыдущий тест черновика после истечения сессии также PASS.
4. **Workflow.** Повторно выполнены safety-тесты и actionlint. В main уже присутствует только workflow_dispatch, main-ref guard, явное подтверждение и default dry-run; код workflow этого этапа не менялся. Автопубликация от push/merge остаётся отключённой в проверенном репозитории. Внешние настройки/интеграции не инспектировались.

Изменены: public/script.js, public/crm.js, tests/test_prelaunch.py; добавлен docs/STAGE-2.2-REPORT.md. Дизайн, HTML/CSS, PHP, база, схемы/миграции, зависимости приложения и config.example.php не менялись. Миграций нет. Производственные пароли, ключи, config.php и тексты политик не добавлялись.

## Реально выполненные проверки

| Проверка | Результат |
|---|---|
| unittest test_prelaunch.py с PHP/DB/Chromium | 14 PASS, 0 FAIL, 0 SKIP |
| node --test tests/api-client.test.cjs | 12 PASS, 0 FAIL |
| unittest test_deploy_workflow.py | 6 PASS |
| unittest test_apache_security.py на реальном Apache | 2 PASS |
| node --check script.js/crm.js/api-client.js | 3 PASS |
| PHP lint public/private/scripts/tests | 9 PASS |
| actionlint 1.7.7 (без ShellCheck/Pyflakes) | PASS |
| bash -n shell-шагов workflow | PASS в составе workflow-тестов |
| git diff --check и локальный merge-tree с main | PASS, конфликтов нет |

Всего 34 автоматизированных теста PASS. PHP 8.4.27, Apache 2.4.69, MariaDB 11.8.6, Chromium/Playwright. Только временная копия и случайная loopback-БД neuro_test_*. Синтетический тестовый документ не является юридическим утверждением политики. **Точный MySQL 5.7 и production не проверены.** Команды повторения интеграции и Apache сохранены в STAGE-2.1-REPORT.md, workflow — в SAFE-INTEGRATION-REPORT.md. Реальные SSH/rsync не использовались.

Безопасность: fail-closed для формы и проверка согласия сохранены; подтверждение сохранения требует строгого JSON/HTTP 201 как прежде. Новый тихий режим не отправляется серверу и не изменяет авторизацию. Серверные 401/CSRF/version checks не обходятся. Draft остаётся только в текущей вкладке, без нового локального хранилища персональных данных.

## GitHub и выпуск

Ветка опубликована. Попытка создать PR через gh pr create (base=main, head=fix/stage-2-2-form-and-login) вернула exit 1, `Post https://api.github.com/graphql: Forbidden`. **PR этой попыткой не создан.** Запрос списка Actions также Forbidden: результаты GitHub CI UNVERIFIED, локальные PASS не заменяют CI. Workflow вручную не запускался.

[Создать подготовленный PR с заполненными полями](https://github.com/2006minden-gif/-Chat-GPT-/compare/main...fix/stage-2-2-form-and-login?expand=1&title=Stage+2.2%3A+preserve+pending+edits+and+fix+initial+CRM+login+state&body=Fixes+pending+form+edits+and+initial+CRM+login+state.%0A%0AFull+report+and+test+results%3A+https%3A%2F%2Fgithub.com%2F2006minden-gif%2F-Chat-GPT-%2Fblob%2Ffix%2Fstage-2-2-form-and-login%2Fdocs%2FSTAGE-2.2-REPORT.md%0A%0A34+local+tests+passed.+No+merge+or+production+deployment+authorized.)

Осталось в браузере проверить base=main и compare=fix/stage-2-2-form-and-login, нажать **Create pull request** (или открыть уже существующий, если GitHub предложит его). Слияние и auto-merge без следующего одобрения не выполнять. Текущий main остаётся на Stage 2.1; Stage 2.2 находится только в отдельной ветке. Подключений к SpaceWeb и публикации не было. Старый deployment ZIP не обновлён и не содержит новых исправлений. Юридическое одобрение документов и прежние production 503 — вне этой задачи, никаких предположений об их устранении не делается.

STAGE 2.2 COMPLETE — AWAITING APPROVAL.
