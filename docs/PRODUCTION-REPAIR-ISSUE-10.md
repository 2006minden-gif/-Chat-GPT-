# Issue #10 — точечный ремонт production без раскрытия конфигурации

Дата: 24.10.2026. Ветка `fix/issue-10-production-repair` от main `22ff5d7`. Это отдельный путь ремонта, не выпуск Stage 3/4 и не включение CI/CD.

## Подтверждено в production

SSH с существующим ключом/known_hosts работает; используется `/usr/bin/php8.4`, PHP 8.4.27, tokenizer доступен. Никакие credentials не менялись и не передавались в чат.

Read-only runs: 40098940224, 40099712843, финальное подтверждение **40102116329** (source `b4ba80b`). PHP сообщает ParseError на строке 12, unexpected_identifier. Одиночные comma/semicolon и key-quote варианты отвергнуты. Подтверждён конкретный кандидат: **два неэкранированных apostrophe внутри полного standalone single-quoted значения на строке 12**. Требуются ровно 2 вставки PHP escape `\`, без удаления/замены исходных символов значения. Серверный TOKEN_PARSE и строгий literal-array parser принимают кандидат; никакие actual values, имя поля или сам config не экспортировались. Кандидат пока НЕ устанавливался; реальная PDO-проверка и нативная проверка decoded-value hash обязательны в prepare до target writes.

private/config.php существует, читается, 506 bytes. Ни содержимое, ни его hash не попали в Git/артефакты/отчёты. .htaccess — 170 bytes, отличается от защищённого source main. В публичном дереве обнаружены 2 backup-style copies, 20 файлов при ограниченном обходе; архивов/дампов и symlinks в этом обходе нет.

- `~.htaccess`: 0 bytes.
- `index~.html`: 349694 bytes. Выполнен только ограниченный marker scan первых 65536 bytes; отсутствие markers в префиксе НЕ доказывает отсутствие секретов/персональных данных во всём файле. Весь файл не выгружался в GitHub.
- Оба URL возвращают **GET 200 и HEAD 200**, проверено без чтения/вывода HTTP bodies. Даже пустой backup остаётся blocker при публичном 200.
- privacy API/page продолжают возвращать 503 по предыдущей авторизованной диагностике; это не разрешённый disabled-policy HTML ответ.

До применения reviewed repair production baseline остаётся **UNHEALTHY**. PDO connection/схема production в этом ходе не объявляются проверенными: существующий config не парсится.

## Почему требуется один server-local edit

Рабочий config отсутствует в Git по требованиям безопасности, и обычный deploy обязан его сохранять. Подстановка config.example.php уничтожила бы credentials/flags и запрещена. При этом обычный deployment preflight требует загрузить config и сейчас падает. Выход — проверенная CLI-операция на самом сервере, которая использует его существующие значения и никогда не возвращает содержимое наружу.

scripts/repair/production.php передаётся через SSH stdin, не публикуется в public_html. Клиент использует существующий строгий SSH Remote/known_hosts. Никакого keyscan/auto-accept, upload ZIP, изменения PHP ini на хостинге или SQL import нет.

## Допустимый ремонт config

Разрешены только проверенные вставки отсутствующих array commas/terminal semicolon и кавычки в имени известного параметра. Кавычка имени исправляется лишь в позиции ключа массива, из ограниченной schema allowlist. Для одного полного standalone single-quoted объявления дополнительно разрешено только PHP-экранирование уже существующего внутреннего apostrophe: символ не удаляется и не заменяется. Существующие valid escapes сохраняются. Отсутствующий внешний delimiter, несколько объявлений на строке, inline code и неоднозначные варианты отвергаются. Все байты строковых/числовых/boolean значений, комментарии и whitespace остаются прежними. Fingerprint учитывает нормализацию допустимого синтаксиса ключа/escape. Для escape отдельно вычисляется server-local hash объявленной последовательности байтов значения с правилами PHP single quotes; **нативный require кандидата должен вернуть точно те же bytes** до любых target writes. Hash и значение не экспортируются. Строки не заменяются placeholders/defaults, пароль не сбрасывается; рабочие credentials дополнительно проверяются read-only PDO. Проверяются PHP TOKEN_PARSE, строгая декларативная грамматика `return` literal array, fingerprint сохранённых tokens и повторная проверка установленного файла. Не выполняются arbitrary calls, eval, шаблонная перегенерация или переформатирование.

Если синтаксис нельзя исправить этими операциями без изменения последовательности байтов самих значений, prepare **отказывается**. Нет force/ignore-parser/ignore-PDO флага. Неоднозначное экранирование, неизвестные bare identifiers вне строго распознанного standalone value и отсутствующие внешние quotes в значениях не исправляются вслепую: сначала нужна отдельная доказуемая server-local remediation, не передача секрета в чат. Диагностические операции не изменяют production, даже если ремонт пока недоступен.

## Защита файлов и план ремонта

План содержит только 4 фиксированных имени: private/config.php, public_html/.htaccess и 2 конкретные backup copies. Произвольные имена/paths и symlinks не принимаются.

1. Lock и новое private directory `.neurodelo-repair/<plan-id>` (0700) вне document root.
2. Проверка места под backup/recovery. Все исходные файлы копируются потоково в `.before` (0600), hashes проверяются до/после копирования; восстанавливаются в private scratch и повторно сверяются. Private backup создаётся и проверяется **до любых изменений config/public targets**. Создание самого backup/lock — необходимая private запись, не изменение исходных файлов.
3. Кандидаты (0600) и manifest остаются только на сервере. У config всё ещё исходные bytes; prepare проверяет PDO кандидата с `SET SESSION TRANSACTION READ ONLY` и SELECT LIMIT 0 для исходных четырёх таблиц, без миграций/записей.
4. apply принимает только подготовленный plan ID. Проверяются hashes backups, кандидатов и текущих sources; повторные/параллельные планы и внешние изменения останавливают операцию. Перед rename — повторная проверка source hash.
5. Две конкретные copies перемещаются в private quarantine, а не удаляются. Другие пользовательские файлы не трогаются. .htaccess получает appended managed block, существующие правила/rewrites сохраняются. Config заменяется атомарно в его private directory, с исходным mode и неизменёнными values.
6. PDO preflight повторяется, создаются лишь кратковременные **синтетические** public probes (не секреты и не PHP debug), чтобы проверить фактическое Apache поведение, включая hidden directory. Имена уникальны; существующие файлы не перезаписываются.
7. Клиент требует healthy full HTTP snapshot и **GET + HEAD** 403/404 для backup paths, существующих probes, hidden/config/archive URLs. Запреты не подтверждаются по HEAD в одиночку. Bodies запрещённых ресурсов не читаются и не логируются. CSS/JS hashes должны остаться прежними.
8. Только после receipt выполняется confirm, удаляются только собственные probes, повторяется health. Никакие AUTOMATION_READY/privacy/setup/customer flags, settings GitHub или DB records не меняются.

Managed Apache block блокирует tilde/editor copies, hidden files/directories, dump/key/config/diagnostic files и архивы. Проверено на настоящем Apache 2.4, включая URL encoding и GET/HEAD. Обычные assets/страницы и ACME challenge остаются доступными. Архивы не считаются публичными downloads по умолчанию; будущие legitimate downloads требуют отдельного защищённого пути/проверенной allowlist.

## Откат и отказ

Сбой apply/HTTP validation приводит к byte-for-byte rollback config/rules из private backup. Quarantined copies **никогда не возвращаются в public_html**, чтобы не восстановить их публичную выдачу. Если repair уже подтверждён, последующий ручной rollback config сохраняет проверенные security rules. Внешние изменения владельца или повреждённый backup не перезаписываются: операция останавливается для расследования.

Восстановление старого config может вернуть прежний ParseError — это восстановление исходных bytes, НЕ «здоровый сайт». Отчёт отдельно фиксирует rollback bytes и фактический health; зелёный release/READY из этого не получается. Ни удаления customer data, ни DB rollback/migration не существует в этом инструменте.

## Reviewed выполнение после PR

Workflow **One-time production blocker repair** доступен только workflow_dispatch; secret-bearing job разрешён только на main в existing main-only production environment. До него переиспользуется полный существующий CI через workflow_call `validation_only=true`; production job обычного deploy при таком вызове всегда skipped. Это не конкурирующая доставка и не обход review.

Порядок оператора (Codex/авторизованная automation; не требуется вручную редактировать PHP):

1. Получить настоящее review и интегрировать этот PR по действующим правилам. Feature branch не может запускать repair job.
2. `inspect` — без writes, подтвердить текущую диагностику.
3. `prepare` с уникальным plan_id и exact `expected_revision` reviewed main SHA — только private backup/candidate и read-only PDO. Если config candidate не доказан, STOP; apply не запускать.
4. Изучить **redacted** prepare report (не конфиг), затем `apply` того же plan_id/exact SHA. Helper проверит backup, установит цели, проверит GET/HEAD + full health, подтвердит или откатит.
5. При необходимости `status`/`rollback` того же плана. Backups/quarantine остаются server-local; удалять их по retention автоматически запрещено.
6. Только после доказанного healthy baseline возвращаться к Issue #8 exact-SHA smoke/promotion. Никакое успешное выполнение repair не включает автоматический release само по себе.

Workflow не требует нового admin PAT или переноса SSH keys. Для первого запуска нужны reviewed main source и существующие права Actions/production environment. Ветки Stage 3/4, source config.example.php, privacy document и database/ не менялись.

## Тесты и границы

Проверки выполняются только на временных configs и случайных loopback MySQL databases. Покрыты: минимальные commas/semicolon, неподдерживаемые/исполняемые configs, literal preservation, большой backup stream, 0600/0700, quarantine/rollback, stale source, corrupt backup, symlink refusal, отказ подтверждения при GET 200, отсутствие transport baseline, настоящие PDO+HTTP repair с неизменностью всех четырёх исходных таблиц и выключенного privacy flag, реальный Apache GET/HEAD/ACME.

Браузерная/app regression suite сохраняется через обычный CI. Динамический isolated PHP HTTP fixture и настоящий Apache authorization fixture проверяются отдельно; это не выдаётся за уже применённый production repair. Фактические test counts, commit SHA, PR и hosted CI statuses приведены в completion report.

**Production repair not applied; baseline not yet healthy.** Причина остановки — обязательный reviewed path; syntax candidate подтверждён на сервере, но private backup/prepare/native value/PDO и apply ещё не выполнялись, а не разрешение игнорировать проверки. Ни production backups/edits, ни DB migrations, ни Stage 3/4 deployment этим ходом не выполнялись.

## Выполненная локальная верификация

Полный набор этой ветки: 86 Python tests PASS (64 прежних + 22 repair tests), Node API-client 12 PASS. PHP 8.4.27 syntax: 11 файлов; JS syntax: 3 файла. Изолированный настоящий MySQL 5.7.42, read-only PDO, Apache 2.4.69 и browser regressions. actionlint и release policy/diff checks прошли; redacted secret scan — 0 findings. CI/GitHub результат отдельного PR фиксируется после push, не подменяется локальными результатами.

Синтетический end-to-end ремонт действительно применялся и откатывался только в временных директориях/случайной loopback DB. Проверка Apache выполнялась отдельно на реальном Apache; dynamic PHP fixture — отдельно на локальном PHP server. Production .htaccess/config/data оставались неизменны, baseline здоровым пока не называется.
