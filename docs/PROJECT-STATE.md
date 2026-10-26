# NeuroDelo — состояние проекта

Текущая приёмка automation repair: НЕ ЗАВЕРШЕНА. Точная recurring GITHUB_TOKEN approval rule и постоянный App/PAT путь: [PR-AUTOMATION-APPROVAL-DIAGNOSIS.md](PR-AUTOMATION-APPROVAL-DIAGNOSIS.md). Разовое одобрение #31 не исправляет последующие PR. Нельзя использовать dummy commit или успешный head preview для обхода held PR workflow.

Обновлено 26.10.2026. Статусы относятся к указанным SHA и runs.

Сервис-гайд опубликован: https://neurodelo.pro/services.php.
Feature head: `8a561f6ecc1b1d250acaf6e57f623f46776675f5`, PR [#24](https://github.com/2006minden-gif/-Chat-GPT-/pull/24), merged main `821a8b58e91f872cd49297963ec0e514cca3c0a9`.
Последняя сверенная production revision: `6f1291edf31bee8f31c0940970fc6631825b2c0f`, [run 40280808627](https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40280808627), `deployed_and_verified`.

PR creation отделено от merge eligibility в PR #25. PR #26 добавил безопасные Actions annotations; PR #27 интегрировал диагностику выбранного grant и три документа проекта. CI #27: 163 Python + 12 Node PASS; actionlint PASS.

Аудит40280063632/job121431191743 подтвердил: REST allow_auto_merge отсутствует, хотя permissions.admin=true; Actions can_approve_pull_request_reviews=true; protection доступна, strict_checks=true, enforce_admins=true, Actions Validate=true, required_approvals=0. Это не выключенная настройка и не обязательный независимый review. Connected API возвращает allow_auto_merge=true. Старый handler ошибочно объединял отсутствие поля с false.

Следующее исправление читает отсутствующую настройку через типизированное GraphQL autoMergeAllowed с проверкой exact nameWithOwner; unknown/errors по-прежнему блокируют merge. GHA create_pr использует GitHub App при наличии либо native GITHUB_TOKEN с job pull-requests:write/actions:write вместо административного токена, ранее получившего POST PR403. Native PR suppression учитывается явным preview dispatch существующего deploy.yml. Никакие settings/protection не меняются. Реальная проверка: run40281018269/job121434102854 создал draft PR#29 автором github-actions[bot] при merge flag=false/unset и dispatch preview40281040873. Первый preview отменён concurrency после нового тестового head; его нельзя выдавать за PASS. Новый head прошёл push CI40281079415 и PR CI40281084505; run40281288598/job121434944934 подтвердил PR already exists. Один PR, без дубликатов. Proof PR закрыт, собственная remote proof branch удалена, в main не включалась.

Configure integration40281088553/job121434324935: protected_integration_enabled, required_approvals=0, required_checks=[Validate], branch_protection_modified=false. GraphQL fallback работает, AUTOMERGE_ENABLED включён существующим проверенным main-only grant.

Последняя проверка выявила, что approved job пытался обработать старый manual PR#6 и падал (40281280606/40281288598). Следующая правка ограничивает merge controller-owned PR с provenance trusted Validate run, сохраняет draft/legacy/manual PR, использует native/App write token отдельно от administrative policy read grant и принимает successful same-repo non-main workflow_dispatch preview для продолжения цепочки. Required checks/reviews и exact head остаются обязательными.

Production evidence: 18 файлов, verified file backup/recovery и finalize, migrations=[]. DB: baseline nd_admin/nd_leads/nd_limits/nd_sessions; journal пуст, admin_exists=false, privacy_approved=false. Это не доказательство live DB restore или готовности расширенной CRM. Draft PR #4/#7/#21/#22 не выпускать.

Live smoke: verified HTTPS 200 для services.php, AI query, styles.css, guide.css и guide.js. Chromium 375×812 выполнял полученные production bytes: выбор AI, создание локального брифа, Telegram draft, сброс результата после правки, отсутствие overflow/JS errors. Прямой browser TLS не проверен; внешний Google Font исключён. Проверка не отправляла сообщения и персональные данные.

Следующая точка: интегрировать последний merge/event-chain repair через permitted bootstrap path, затем проверить controller-owned PR → native preview → GHA merge → exact main dispatch → SpaceWeb → evidence.

## Последняя проверка repair PR #30

GHA создал PR#30 из docs/verified-delivery-result после trusted branch CI40281499149. Explicit native preview40281695641 завершился SUCCESS, включая Validate, full suite и release build. Исходный bot-triggered pull_request run40281697839 имеет action_required; PR остался unstable. Автоматическая проверка безопасности отклонила merge в этом состоянии. Он не был выполнен; не обходить эту блокировку.

Этот documentation update фиксирует результаты перед повторной проверкой обычного push/PR CI нового head. Только fresh exact-head required checks и проверенный GitHub merge state позволяют продолжать. Если action_required останется, необходимо одобрение запуска через разрешённую GitHub workflow approval operation; в текущем наборе connector tools такой операции нет. Feature остаётся DEPLOYED_AND_VERIFIED на указанной выше production revision; полный repair не считать завершённым до законного merge, deploy и evidence.
