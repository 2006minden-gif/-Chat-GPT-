# Восстановление доставки обновлений — 25.10.2026

**Финальный результат: малый выпуск опубликован и проверен на SpaceWeb.**
Commit `30efb5f4285433c73be36325009f3e716f465883`, run [40198377556](https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40198377556).
Ранние записи ниже описывают состояние до завершения pipeline; итоговая
проверка и evidence приведены в конце документа.

## Разделение выпусков

Малый выпуск `fix/visible-website-release` основан непосредственно на main
`478ca7fad33016e4e1421795d2b768a9c9afd9c9`. Commit
`0b78b7372881708b0e9705f48c32e8bb9fda3c05` меняет только подвал главной:
видимый текст «Версия 25.10.2026», маркер `web-2026-10-25-01`.
База, PHP, config, flags и workflows не меняются. GitHub Validate успешно:
https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40197763563 .
Publish и Enable skipped: feature-ветка не является опубликованным main.

Запрос создания PR через доступный API вернул `Forbidden`. Готовая форма:
https://github.com/2006minden-gif/-Chat-GPT-/compare/main...fix/visible-website-release?expand=1 .
Нельзя подменять требуемое независимое review прямым push main.
На момент первой HTTPS-проверки сайт отвечал 200, новый маркер отсутствовал.
Публикация и production SHA не подтверждены.

## Исправление существующего сборщика

Ветка `draft/integrated-release-package` основана на проверенной интеграционной
версии `ce8486967c029768333332c380100ac256373718`, а не на незавершённых
изменениях оплаты Сбербанка. Это отдельный кандидат; он не должен попасть
в production вместе с малой правкой подвала.

- Явная политика содержит все 116 файлов приложения (52 public, 64 private),
  включая вложенные CRM/AI/billing/catalog модули и ресурсы frontend.
- Полнота проверяется сравнением policy со всеми файлами исходников.
  Новый забытый файл блокирует сборку. Не используется безусловный rsync
  всей рабочей папки. Config, privacy document, installer, secrets, uploads,
  backups и development tools не включены в устанавливаемые файлы.
- Сборщик и PHP агент используют согласованный точный allowlist;
  regression проверяет равенство. Tool entries не могут писать public/private.
- Обход каталогов, абсолютные пути и симлинки, включая родительские
  каталоги, запрещены. Недостающие каталоги создаются с ограниченными правами.
- Backup, восстановление в private scratch, проверка хешей, отказ при
  конфликтующем ручном изменении и запрет SQL restore сохранены.
  Старый backup с меньшим набором управляемых файлов остаётся восстанавливаемым.
  Откат вновь добавленных файлов сохраняет чужие файлы и загрузки.
- Post-release HTTPS проверяет все CSS/JS из manifest, включая новые ресурсы;
  baseline перед выпуском продолжает проверять существующий сайт.
- Preflight проверяет PHP >=8.4, MySQL 5.7, PDO MySQL, mbstring, Fileinfo,
  Tokenizer, ZipArchive, proc_open, доступ к config и базовые таблицы.
  Наличие этих возможностей на реальном сервере пока не подтверждено.

## Миграции и безопасная последовательность

В package доставляются SQL и существующие CLI runners в private staging,
но доставка файла не разрешает выполнение. Политика содержит SHA-256 обоих
направлений и последовательные зависимости:

| Версия | Существующий оператор |
| --- | --- |
| 004_crm_foundation | scripts/migrate.php |
| 005_customer_auth | scripts/migrate-customer.php |
| 006_crm_operations | scripts/migrate-crm.php |
| 007_client_collaboration | scripts/migrate-collab.php |
| 008_billing_notifications | scripts/migrate-billing.php |
| 009_ai_automation | scripts/migrate-ai.php |
| 010_project_pricing | scripts/migrate-pricing.php |
| 011_ai_production | scripts/migrate-production.php |
| 012_manual_handoff | scripts/migrate-manual.php |
| 013_service_ordering | scripts/migrate-catalog.php |

Prerequisite: существующая baseline schema и исправления 001–003; нельзя
импортировать schema.sql поверх production. Preflight проверяет требуемые
baseline columns. Вся цепочка 004–013 помечена required=true, automatic=false.
Если версия отсутствует или journal/checksum не совпадает, установка кода
блокируется; SQL не исполняется и данные не изменяются. Существующий узкий
автоматический оператор 004 не расширен до непроверенных ALTER/DDL.

Для unattended применения остаются обязательными: фактический journal на
сервере, ревизия каждой DDL-операции, проверенная резервная копия БД и её
восстановление в отдельную БД, staging с production-подобной схемой, доступное
место, стратегия прерывания/повторного запуска и подтверждение совместимости
старого кода после аддитивных изменений. MySQL DDL не является атомарной
транзакцией. Ни down, ни SQL restore нельзя автоматически выполнять поверх
новых клиентских данных. Пока эти gates не доказаны, CRM release заблокирован.

## Границы доступа

Git fetch/push работают. GitHub REST GET/POST в текущей среде возвращает
Forbidden; production secrets SSH_HOST/SSH_PRIVATE_KEY/SSH_KNOWN_HOSTS
в среду не переданы. Секреты в GitHub environment не читаются и не извлекаются.
Workflow dispatch/PR create/merge/production state недоступны через текущий
API. Это ограничивает прямое управление API из текущей среды, а не необходимость
загрузить владельцу файлы или предоставить банковские/SSH пароли в чат.
Существующие workflows и архитектура доставки не изменены.

## Выполненные проверки

- Интегрированная версия: 311 Python tests PASS, 260.947 s, в изолированных
  случайных neuro_test_* БД на PHP8.4/MySQL5.7/Apache2.4 и Chromium.
- После окончательной настройки guard-проверок: 52 release tests PASS.
- Node API client: 12 tests PASS; PHP syntax: 105 files PASS; JS syntax: 18 PASS.
- actionlint, compileall, policy check, manifest SHA-256 и git diff --check PASS.
- Gitleaks текущего дерева: утечек не найдено. Не является аудитом всей истории.
- Production read-only HTTPS baseline: 17/17 PASS; HTTP200 главной;
  ожидаемый новый маркер отсутствует. Это проверка старого сайта, не релиза.
- Ни production SQL, ни запись на SpaceWeb, ни SSH подключение не выполнялись.

Локальный кандидат: 116 application files + 35 tools/SQL + manifest, все
хеши проверены. Это артефакт проверки, а не опубликованный релиз. Публиковать
нужно артефакт, собранный CI для окончательного точного commit SHA.

## Обновление состояния main

После подготовки исправлений обнаружено слияние малого выпуска PR #23:
main `30efb5f4285433c73be36325009f3e716f465883`. Указанный выше запрет
создания PR через локальный API остаётся фактом, но PR уже создан и слит
в GitHub. На повторной HTTPS проверке после merge маркер ещё отсутствовал;
нужно дождаться и проверить публикацию этого exact main SHA, а не считать
merge доказательством деплоя. Main включён в draft-кандидат; конфликт подвала
разрешён сохранением клиентского входа и добавлением новой отметки версии.

## Подтверждённый production результат

PR #23 слит; существующий автоматический release main завершён без изменения
workflows и без ручной передачи файлов/секретов. Run 40198377556: Validate и
Publish approved main SUCCESS, result=deployed_and_verified, mode=deploy.
Release ID: 20261025T133814Z-r40198377556-a1-30efb5f42854.
Все 14 server-side hashes сверены с точным main SHA, не только со словесным
статусом job. Резервная копия и восстановление файлов в private scratch
проверены агентом. Это проверка code recovery; production DB restore не
исполнялся и его пригодность для будущих миграций этим не доказана.

Независимый HTTPS GET 25.10.2026 13:40:41 UTC: HTTP200, оба
`web-2026-10-25-01` и «Версия 25.10.2026» присутствуют. SHA-256 ответа
`e1a206f5217a7bd2dd1c1796b16ad86571b4829921996c56e15a52e3c03d8222`
совпадает с опубликованным public_html/index.html и Git main.
Before/after health: 17/17 PASS. Migrations: []; rollback не потребовался.
Privacy flag остался false. Private config и данные не изменялись.
Машиночитаемое безопасное evidence: [website-release-2026-10-25.json](evidence/website-release-2026-10-25.json).

**CRM ещё не готова к боевому выпуску:** live preflight admin_exists=false,
подтверждённой инициализации владельца нет. Модули расширенной CRM остаются
в draft-кандидате, а обязательные DB checkpoints 004–013 запрещают установку
при неподготовленной схеме. Для unattended миграций остаются обязательными
проверка production journal, отдельный проверенный DB backup/restore и
проверка безопасного выполнения каждой DDL. Не подменять их успешным выпуском
лендинга или code backup. Никакие новые платёжные/AI/privacy функции не включены.

После включения нового main в draft-кандидат: сохранены клиентская ссылка
и новый маркер главной; дополнительные 14 prelaunch tests PASS. Полная
311-test suite выполнялась до этого HTML merge; остальной app/release code
не менялся. Интеграционный draft не слит и не опубликован.
