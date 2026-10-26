# NeuroDelo — передача контекста следующему чату

Обновлено: 26.10.2026. Это рабочая хронология и точка продолжения, а не копия
полной переписки. Перед действием перечитать реальные GitHub refs, PR/checks и
production evidence: статусы ниже могут измениться.

## Действующая задача и решения владельца

Восстановить полный цикл DEVELOP → TEST → CREATE PR → INTEGRATE → DEPLOY →
VERIFY → REPORT. Не просить владельца создавать каждый PR или подтверждать
обычный безопасный релиз. Использовать существующую GitHub→SpaceWeb delivery.
Нельзя обходить действующую branch protection, подделывать reviews, публиковать
непроверенный код, перезаписывать config/данные, автоматически откатывать БД.
Если реальное правило review конфликтует с solo-owner автоматизацией — указать
точное правило и подготовить минимальное одноразовое решение владельца.

Stack: PHP8.4/MySQL5.7/Apache2.4, vanilla JS/CSS, neurodelo.pro, SpaceWeb.
Дизайн тёмный синий/серый/неоновые акценты. Контакт: Telegram @minden2006.
Не включать сбор персональных данных, live payments и платный AI без оснований.
Цены AI: расчёт затрат/маржи, immutable quotation version; обязательное реальное
owner approval точной версии перед коммерческим обещанием. Не придумывать rates.

## Краткая хронология

1. Собраны лендинг и legacy CRM, baseline tables nd_admin/nd_leads/nd_sessions/
   nd_limits. Setup ранее имел 404/503. Производственные исправления и
   CI/CD bootstrap интегрированы. Secrets остаются вне Git.
2. Разработаны расширения: Stage3 data foundation, Stage4 customer auth,
   Stage5 operations, Stage6 collaboration, Stage7 billing, Stage8 AI/pricing,
   Stage10 production automation, Stage11 integration/manual handoff.
   Stage9 service ordering завершён позднее на существующей модели.
   Это не означает, что они опубликованы.
3. Stage12 выявил неполный package (14 old app files), неподдержанную цепочку
   миграций, отсутствие live DB recovery evidence. См. docs/STAGE-12-RELEASE-REPORT.md
   в интеграционной ветке. Не применять автоматически chain004–013.
4. Малый выпуск PR#23: production SHA 30efb5f4285433c73be36325009f3e716f465883,
   run40198377556, deployed_and_verified, реальный footer «Версия25.10.2026».
5. draft/integrated-release-package содержит полный кандидат (116 app files),
   guarded package/nested dirs/rollback и required/manual checkpoints004–013.
   Эта ветка не слита/не опубликована. Последний известный SHA
   e07375f4cc564f7ce9d7c84211fb3fe0c42b2b79. 311 local tests PASS на тот момент.
6. Независимая feature/public-service-guide создана на main без CRM-зависимостей:
   услуги + локальный бриф/clipboard/Telegram draft, без API отправки/DB/storage.
   Перенесены general-purpose package guards; 18 app files, nested dirs,
   SHA checks всех CSS/JS, metadata-only DB preflight. 133 tests + Node12 PASS.
   Branch SHA8a561f6ecc1b1d250acaf6e57f623f46776675f5, CI40200125083 SUCCESS.
7. Ранее local GitHub API запрещал сетевой proxy: Tunnel403 к api.github.com,
   тогда как git работал. Добавлен network draft api.github.com, прежний
   neurodelo.pro сохранён. 26.10 API уже работает. Новые credentials не нужны.
8. Найден реальный дефект: auto-merge.yml job approved gated AUTOMERGE_ENABLED,
   а ensure_pr_for_validated_branch находился внутри auto_merge; отключённое
   слияние отключало и создание PR.
9. Новый проверенный create-pr handler программно создал PR#24 (без владельца).
   Запущен штатный native --auto --squash --match-head-commit, без --admin.
   GitHub слил PR#24: main SHA821a8b58e91f872cd49297963ec0e514cca3c0a9.
   Production run40275235437: Validate+Publish SUCCESS, deployed_and_verified.
   Все18 server hashes сверены с точным main; backup/recovery verified;
   migrations[]. Функциональный browser smoke ещё доводится (см. ниже).

## Фактический production metadata (run40275235437)

PHP8.4.27, MySQL5.7.27-30-log, database_connected=true, admin_exists=false,
privacy_approved=false. Tables: nd_admin, nd_leads, nd_limits, nd_sessions.
Migration journal отсутствует/пуст. Schema metadata SHA256
8aaa4e0c7ef7a95d31ff84a72b06385cc5084c124d0212d34a5d907d9042387c.
Нет утверждения о готовности расширенной CRM или DB restore на production.

## Активная ветка исправления автоматизации

`fix/independent-pr-creation` в checkout /workspace/neurodelo-services.
Содержит 4f0dbac (independent PR handler/job) и merge def7ab5 актуального main
с PR#24. Последующие рабочие изменения необходимо проверить в Git.

Реализовано:
- create_pr job не зависит от AUTOMERGE_ENABLED. workflow_run successful trusted
  branch и явный replay validated_run_id; checkout main, pinned actions,
  отдельная concurrency, существующие App/automation credentials.
- control.py create-pr --run-id сверяет authoritative run/repo/workflow ID/path,
  successful Validate job, exact current SHA до записи, ahead(main), existing
  PR (включая stacked/draft), совпадение CI definition с main. Нет branch-code
  execution с privileged credentials. 422 race → existing PR, bounded403 advice.
- Native-token PR имеет dispatch существующей branch validation, без production.
- configure-integration отдельно проверяет actual strict CI/review policy и
  main-only automation env, включает только AUTOMERGE_ENABLED. Не меняет rules.
- Bootstrap не сбрасывает ранее разрешённую интеграцию; initial absent flag false.
- Auto-merge следует фактическому required approval count, не навязывает1 при0.
  Требуемые reviews сохраняются; автор не считается независимым reviewer;
  REVIEW_REQUIRED, failed CI, stale SHA блокируют. Native GitHub gates сохраняются.
- После successful validated main + AUTOMATION_READY configure_integration job
  использует existing BOOTSTRAP_ADMIN_TOKEN, exact validated SHA; production
  secrets/SSH не используются. deploy.yml не изменён.

Новые tests/test_pr_automation.py покрывают24 сценария; общий набор158 PASS
(35.558s), Node12 ранееPASS, actionlint PASS. В ранних прогонах был failing mock
bootstrap после нового read flag; fixture исправлен и добавлен тест сохранения
существующего enable flag. Не выдавать ранний failed run за PASS.

## Следующие действия

1. Зафиксировать/отправить оставшиеся проверенные изменения этого repair branch;
   прогнать lint/actionlint/full applicable suite, создать PR программно через
   новый handler после trusted CI (не просить владельца создавать PR).
2. Проверить current PR protection через реальные API. GET branch summary
   показывает protected=true, required Actions Validate15368 for everyone.
   Full protection/variables/settings и branchProtectionRules GraphQL из local
   integration дают GitHub403, несмотря на repo.permissions.admin=true.
   PR#24 reviewDecision=null и normal native merge состоялся без bypass.
   Это не даёт права гадать о скрытых дополнительных правилах. Использовать
   existing administrative GHA grant для полного policy audit.
3. Интегрировать repair только штатным passing GitHub path. Не --admin/force.
   Проверить configure_integration job и независимое PR creation на реальном
   successful branch run при выключенном merging; безопасно использовать
   временный draft proof branch, затем закрыть/удалить только собственный proof.
4. Проверить actual production release SHA/evidence после repair и public guide.
   Chromium direct TLS даёт ERR_CERT_AUTHORITY_INVALID для proxy CA среды.
   TLS verification не отключать. /tmp/neuro-live-service-smoke.py загружает
   настоящие production bytes через Python verified HTTPS trust и выполняет UI
   в Chromium без ignoreHTTPSErrors. Первый URL ?service=ai дал403, тогда как
   /services.php и оба guide assets дали200; перепроверить query/transient cause,
   не считать functional smoke пройденным до успешного результата.
5. Лишь после current feature/release verified переходить к incremental CRM:
   live schema/journal, actual applicable DB backup/restore evidence, guards
   каждого004–013, безопасный identity-bound owner setup (admin отсутствует).
   Не придумывать owner пароль, не публиковать пустые CRM screens.

## Где искать evidence и тестовая среда

GitHub repo 2006minden-gif/-Chat-GPT-. REST работает через existing GH_TOKEN binding;
не печатать значения. Артефакты Azure download могут блокироваться network403.
Безопасный existing evidence exporter: branch automation/evidence, latest.json
и runs/<evidence-workflow-run-id>-1.json; читать также GitHub contents API/base64.
Deployment report соответствует producer deploy run, не любому latest.json.
Проверять revision/result/apply.files_sha256/backup/recovery/migrations/finalize.

Локальные временные evidence:
/tmp/neuro-service-production-report.json (реальный report40275235437),
/tmp/neuro-automation-final-tests3.log (158PASS),
/tmp/neuro-live-service-smoke.py. Пути /tmp не гарантированы в новом окружении.

Проверки:
PATH=/tmp/neuro-runtime:$PATH PYTHONPATH=/tmp/neuro-runtime/python
NEURO_TEST_DSN=mysql:host=127.0.0.1;port=33078 PHP_BIN=/tmp/neuro-runtime/php
APACHE_BIN=/tmp/neuro-runtime/apache
APACHE_MODULE_DIR=/tmp/neuro-runtime/root/usr/lib/apache2/modules
python -m unittest discover -s tests -p 'test_*.py' -q
node --test tests/api-client.test.cjs
/tmp/neuro-workflow-bin/actionlint -shellcheck= -pyflakes=

Только случайные loopback neuro_test_* БД. Live DB/credentials не копировать в Git.
Имеется незавершённая отдельная Sber manual-payment работа в
/workspace/-Chat-GPT-, branch feature/sberbank-manual-payments, uncommitted.
Её не включать в текущий release и не терять/удалять. Stage3/4 draft branches,
другие старые PR и production data сохранять.
