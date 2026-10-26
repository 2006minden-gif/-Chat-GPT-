# NeuroDelo — состояние проекта

Обновлено 26.10.2026. Статусы относятся к указанным SHA и runs.

Сервис-гайд опубликован: https://neurodelo.pro/services.php.
Feature head: `8a561f6ecc1b1d250acaf6e57f623f46776675f5`, PR [#24](https://github.com/2006minden-gif/-Chat-GPT-/pull/24), merged main `821a8b58e91f872cd49297963ec0e514cca3c0a9`.
Последняя сверенная production revision: `c77710a8ac4ed467218211f0500ae34195dcfdd1`, [run 40279749813](https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40279749813), `deployed_and_verified`.

PR creation отделено от merge eligibility в PR #25. PR #26 добавил безопасные Actions annotations; PR #27 интегрировал диагностику выбранного grant и три документа проекта. CI #27: 163 Python + 12 Node PASS; actionlint PASS.

Аудит40280063632/job121431191743 подтвердил: REST allow_auto_merge отсутствует, хотя permissions.admin=true; Actions can_approve_pull_request_reviews=true; protection доступна, strict_checks=true, enforce_admins=true, Actions Validate=true, required_approvals=0. Это не выключенная настройка и не обязательный независимый review. Connected API возвращает allow_auto_merge=true. Старый handler ошибочно объединял отсутствие поля с false.

Следующее исправление читает отсутствующую настройку через типизированное GraphQL autoMergeAllowed с проверкой exact nameWithOwner; unknown/errors по-прежнему блокируют merge. GHA create_pr использует GitHub App при наличии либо native GITHUB_TOKEN с job pull-requests:write/actions:write вместо административного токена, ранее получившего POST PR403. Native PR suppression учитывается явным preview dispatch существующего deploy.yml. Никакие settings/protection не меняются. Реальное выполнение нового пути ещё требуется подтвердить.

Production evidence: 18 файлов, verified file backup/recovery и finalize, migrations=[]. DB: baseline nd_admin/nd_leads/nd_limits/nd_sessions; journal пуст, admin_exists=false, privacy_approved=false. Это не доказательство live DB restore или готовности расширенной CRM. Draft PR #4/#7/#21/#22 не выпускать.

Live smoke: verified HTTPS 200 для services.php, AI query, styles.css, guide.css и guide.js. Chromium 375×812 выполнял полученные production bytes: выбор AI, создание локального брифа, Telegram draft, сброс результата после правки, отсутствие overflow/JS errors. Прямой browser TLS не проверен; внешний Google Font исключён. Проверка не отправляла сообщения и персональные данные.

Следующая точка: интегрировать исправление, проверить фактические configure_integration и native create_pr, повтор/idempotency и последующие required checks. Затем сверить main deployment evidence.
