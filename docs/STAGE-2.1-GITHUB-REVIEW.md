# Stage 2.1 — повторная проверка и подготовка GitHub PR

Дата: 23.10.2026. Репозиторий: 2006minden-gif/-Chat-GPT-. Head: stabilize/stage-2-1; base: main.

## Обзор трёх коммитов

| Коммит | Содержимое | Результат обзора |
|---|---|---|
| d688bca | public/.htaccess, tests/test_apache_security.py | Закрывает подтверждённые backup-имена; сохраняет текущие ресурсы, DirectoryIndex и прежние запреты; локальная HTTP-регрессия PASS |
| 6d8c146 | private/app.php, public/privacy.php, scripts/diagnose.php, tests/test_prelaunch.py | Устраняет воспроизведённый TypeError чтения политики, сохраняет fail-closed и API-контракт; диагностика только CLI и без записи; интеграция PASS |
| f3bdbd8 | docs/STAGE-2.1-REPORT.md | Различает исправления репозитория и непроверенный production, отмечает ограничения MariaDB и устаревший ZIP |

В проверенном объёме новых блокирующих дефектов исправлений не выявлено. Это не утверждение об отсутствии всех уязвимостей или о готовности production. Дизайн, JS приложения, схема/миграции и существующий механизм пароля не менялись. Исходники, database/, scripts/ и .github/workflows/ сохранены.

Удалённый main повторно проверен через git ls-remote и fetch: 37df861a895757c4ff091daefbfe625a86086a8b. Перед добавлением документации ветка содержала ровно три коммита поверх него; конфликтов в git merge-tree --write-tree origin/main HEAD нет. Проверка merge-tree не сливает ветки и не запускает Actions. Ранее устаревшая локальная origin/main обновлена явным fetch remote refs; вывод о составе PR сделан после этого обновления.

## Повторно выполненные проверки

- PHP 8.4.27 lint: 9 файлов public/private/scripts/tests — PASS.
- node --check: script.js, crm.js, api-client.js — 3 PASS.
- node --test tests/api-client.test.cjs — 12 PASS, 0 FAIL.
- unittest test_prelaunch.py — 12 PASS, 0 FAIL, 0 SKIP, включая Chromium: установка администратора и запрет перезаписи, login/session/logout/CSRF, политика/согласие, сохранение лидов, версии, идемпотентность, безопасные ошибки и повтор, миграции тестового fixture.
- unittest test_apache_security.py на Apache 2.4.69 — 2 PASS, 0 FAIL.
- git diff --check — PASS.

База — локальная MariaDB 11.8.6. **Точный MySQL 5.7 не запускался.** Тесты используют временные копии и случайные loopback-БД neuro_test_*, не production. Синтетическое согласие не разрешает сбор реальных персональных данных. Альтернативный tests/check_php.py запускает тот же интеграционный класс, отдельных сценариев не содержит.

В этой задаче не выполнялись обращения к SpaceWeb, попытки SSH, чтение production DB, обновление сервера или изменение учётных записей. Hosting/network troubleshooting не проводилось.

## PR и Actions

Описание PR сохранено в docs/STAGE-2.1-PR.md. Выполнена попытка создать draft PR:

`gh pr create --repo 2006minden-gif/-Chat-GPT- --base main --head stabilize/stage-2-1 --draft --title ... --body-file docs/STAGE-2.1-PR.md`

Результат: `Post https://api.github.com/graphql: Forbidden`, exit 1. **Этой попыткой PR не создан; номер и URL существующего PR не подтверждены.** Проверка списка PR также получила Forbidden. Подготовка ветки/описания завершена, создание PR через API заблокировано. Не выдавать compare-ссылку за уже созданный PR.

Ссылка подготовки PR: https://github.com/2006minden-gif/-Chat-GPT-/compare/main...stabilize/stage-2-1?expand=1

`gh run list` вернул Forbidden для GitHub Actions API. **Результаты Actions — UNVERIFIED**, успешные или неуспешные запуски не установлены; локальные PASS не являются результатами GitHub CI. Actions вручную не запускались. Существующий workflow не содержит pull_request или push этой ветки, поэтому он не обеспечивает PR-проверки этой ветки. Новое CI в рамках текущей проверки не добавлено.

## Риск публикации при merge

Существующий .github/workflows/deploy.yml запускается при push main с изменениями public/**, private/** или самого workflow. Этот PR меняет public и private, следовательно merge подходит под триггер. DRY_RUN зависит от vars.DEPLOY_ENABLED; при значении true публикация может выполняться автоматически, включая серверный backup и rsync. Явного environment approval в YAML нет. Значение DEPLOY_ENABLED через API прочитать нельзя: Forbidden. Наличие/содержимое секретов и внешние интеграции не проверены.

**Слияние сейчас не признано безопасным.** Перед ним требуется подтверждённое отключение автопубликации либо отдельное одобренное изменение workflow. Слияние и публикация — разные разрешения; запрос на подготовку PR не разрешает production deployment. Сам PR не запускает указанный workflow, так как pull_request в событиях отсутствует. Прочие внешние автоматизации неизвестны.

Main не изменён. Автослияние не включено. Stage 2.2 не начат, приложение и workflow дополнительно не менялись. В этой задаче добавлены только два документа: данный отчёт и описание PR, отдельным описательным коммитом поверх трёх проверенных.

## Остатки перед одобрением интеграции

1. Создать/подтвердить PR при доступном GitHub API или через подготовленную compare-страницу.
2. Подтвердить барьер от production deployment до merge; сейчас переменная неизвестна.
3. Проверить доступные Actions/checks, не запуская production workflow ради CI.
4. Сохранить ограничения Stage 2.1: серверные 503, production-авторизация и точный MySQL 5.7 не подтверждены; старый ZIP не обновлён.
5. После одобрения перейти к Stage 2.2: правки формы во время отправки, первое сообщение CRM, регрессия и workflow safety. Эти дефекты текущим PR не исправляются.

GITHUB DEVELOPMENT READY — AWAITING APPROVAL.
