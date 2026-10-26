# NeuroDelo — состояние проекта

Обновлено 26.10.2026. Статусы относятся к указанным SHA и runs.

Сервис-гайд опубликован: https://neurodelo.pro/services.php.
Feature head: `8a561f6ecc1b1d250acaf6e57f623f46776675f5`, PR [#24](https://github.com/2006minden-gif/-Chat-GPT-/pull/24), merged main `821a8b58e91f872cd49297963ec0e514cca3c0a9`.
Последняя сверенная production revision: `ed2b8b8a607b809f94dc5baa1ac90a8783ca6f76`, [run 40278274795](https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40278274795), `deployed_and_verified`.

PR creation отделено от merge eligibility в PR #25. PR #26 добавил безопасные Actions annotations. Полная автоматическая цепочка пока не доказана: create_pr job получил HTTP403 (run40277825832), configure_integration повторно остановлен (run40278588212). Ответ connected API содержит allow_auto_merge=true, тогда как административный GHA handler трактовал false/отсутствие поля одинаково. Подготовлена read-only диагностика конкретного выбранного grant с различением missing/false; настройки и protection не меняются.

Production evidence: 18 файлов, verified file backup/recovery и finalize, migrations=[]. DB: baseline nd_admin/nd_leads/nd_limits/nd_sessions; journal пуст, admin_exists=false, privacy_approved=false. Это не доказательство live DB restore или готовности расширенной CRM. Draft PR #4/#7/#21/#22 не выпускать.

Live smoke: verified HTTPS 200 для services.php, AI query, styles.css, guide.css и guide.js. Chromium 375×812 выполнял полученные production bytes: выбор AI, создание локального брифа, Telegram draft, сброс результата после правки, отсутствие overflow/JS errors. Прямой browser TLS не проверен; внешний Google Font исключён. Проверка не отправляла сообщения и персональные данные.

Следующая точка: интегрировать проверенную диагностику штатным GitHub path и получить фактические permissions/settings через existing main-only administrative grant. Только затем завершать разрешённую настройку или сообщить точную внешнюю блокировку.
