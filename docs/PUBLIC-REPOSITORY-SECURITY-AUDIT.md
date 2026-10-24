# Проверка перед публикацией NeuroDelo

Дата: 24.10.2026. Проверенный main: `977170a0621253ef394c42d5f239c9505e177de6`; CI head: `f384161cf53441f3fcee6ae63bf3849dce9c4e71`. Видимость не изменялась. Проверка конфиденциальности исходников не является подтверждением production readiness.

## Охват и метод

- Получены все 10 удалённых веток, все доступные теги (0), 5 PR head refs и 2 доступных PR merge refs. Репозиторий не shallow.
- Проверены все достижимые локальные и полученные refs: 64 commit objects и 131 уникальное содержимое файлов (Git blobs). Gitleaks отдельно обработал 54 коммита с проверяемыми изменениями; merge/empty commits не обязаны давать отдельный diff.
- Gitleaks 8.30.0: полный Git history scan `--all --full-history`, затем отдельная проверка полных исторических blob contents, распакованных файлов архива и commit messages. Использован `--redact=100`; SHA256 скачанного scanner archive совпал с официальным release checksums.
- Дополнительная проверка имён исторических файлов, credential assignments, PEM private-key headers, email, российских телефонов, SQL INSERT/data dumps. Все найденные credential assignments и contact candidates рассмотрены по контексту. Недоступных/слишком больших/encrypted файлов при обходе не было.
- Проверен единственный исторический ZIP blob `f42b07516d69112946a020b08a30bfa61f430e02`, `deployment-packages/neurodelo-spaceweb-deploy.zip`, включая скрытые файлы, все 16 entries. Найденные в Git evidence JSON также входят в blob scan.

## Результаты

| Категория | Результат |
|---|---|
| Gitleaks, history и полные contents | 0 находок |
| Production passwords, access/API tokens, private SSH keys | Не обнаружены |
| Рабочий private/config.php или .env в истории | Не обнаружены |
| Customer data / production database dump | Не обнаружены |
| Архив развёртывания | 16 файлов, нет config.php, dumps, ключей или клиентских записей |
| private/config.example.php, включая архивную копию | Только placeholders, пустой setup key, сбор данных выключен |
| Email/телефоны в тестах | Синтетические fixtures; email только example.com / example.invalid |
| Ключи/пароли в тестах и MySQL CI | Синтетические значения/пустой пароль изолированного CI service; не production credentials |

В архив входят 3 private-файла (.htaccess, app.php, config.example.php) и 13 public_html-файлов (.htaccess, api-client.js, api.php, crm.css, crm.html, crm.js, index.html, index.php, privacy.php, script.js, setup.php, studio.php, styles.css). Архив старый: он не заменяет новую автоматическую доставку и не считается рекомендацией повторной установки production.

Доменные имена, публичный Telegram владельца, имя hosting account, пути установки, commit/run IDs и сведения об архитектуре встречаются в исходниках/отчётах. Это информация для разведки, но не credentials или клиентская база; публичный контакт намеренно находится на сайте. После публикации исходники и эти operational details станут доступны всем. Их конфиденциальность в дальнейшем не предполагается.

## Безопасные изменения

Подтверждённых утечек, требующих отзыва ключей/паролей или очистки Git history, не найдено. История не переписывалась, ветки/данные не удалялись. .gitignore дополнен защитой от случайного добавления env variations, private config copies, ключей, runtime logs/backups/dumps. Шаблоны и реальные versioned schema/migrations сохранены.

Проверено: git check-ignore для временных путей секретов; шаблон конфига, schema/migrations и deployment ZIP не игнорируются. После изменений повторён scanner. .gitignore не является secret scanner и не удаляет уже отслеживаемые файлы; в данном случае чувствительных отслеживаемых файлов не найдено.

## Границы вывода

Проверены доступные ветки и достижимая Git history на указанный момент, включая удалённые из последних версий файлы. Нельзя восстановить неизвестные удалённые server refs, сторонние clones/forks, недоступные GitHub caches и содержимое вне Git. GitHub Actions logs/artifacts, release assets, issues и production filesystem не входят в этот Git-content verdict; проверка истории не подтверждает их конфиденциальность. Значения encrypted GitHub secrets не извлекались.

Для публичного репозитория production secrets должны оставаться в environment production с main-only доступом, PR tests не должны получать их, privileged workflows должны исполнять только trusted main. Не добавлять pull_request_target с выполнением untrusted PR code. Эти требования сохраняются независимо от чистой истории; план первоначальной настройки описан в AUTOMATION-VERIFICATION.md. Включить доступные GitHub secret scanning/push protection после решения владельца о публикации.

**PUBLIC REPOSITORY SECURITY CHECK: PASS** — в пределах перечисленных Git refs, истории и архивов. Публикация автоматически не выполнена.
