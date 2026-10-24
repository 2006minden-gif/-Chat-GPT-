# Проверка диагностического PR #14

Дата: 24.10.2026. База main: c7284548b9a61909d8fad8e73f0073a0316621d1. Stage 3/4 не включены.

## Безопасность и назначение

Probe делает только GET фиксированного GitHub repository API endpoint и возвращает фиксированную категорию HTTP/transport/missing_token. Он не печатает token, raw stderr, headers, response body или proxy URL. Для неизвестной ошибки gh повторяется только read-only repository GET: исходный POST/PATCH никогда автоматически не повторяется. Изменения не дают дополнительных API permissions, не меняют production, environments, branch protection, credentials или READY.

При review найден и исправлен потенциальный перенос Authorization при HTTP redirect стандартным urllib-клиентом: добавлен NoRedirect, запрещающий все перенаправления. Добавлены проверки 301/302/307/308/500, фиксированного URL/GET/timeout, отсутствия чтения response body. Unit tests больше не вызывают реальный probe при моделировании unknown gh failure.

## Фактически выполненные проверки

106 Python tests PASS (0 failures/skips), 12 Node tests PASS. PHP 8.4.27 lint: 11 файлов; JS syntax, compileall, actionlint, release policy check, diff --check PASS. Изолированные MySQL 5.7.42, Apache, Chromium. Redacted Gitleaks working-tree scan: 0 находок. Hosted CI последнего commit проверяется отдельно после push, прежний зелёный CI не подтверждает новые изменения.

## Ограничения и порядок продолжения

PR пока не интегрирован: публичная GitHub страница при review показывает No reviews. Настоящее обязательное review не заменяется локальным анализом Codex. Защита main, variables и permissions ранее возвращали 403 для GITHUB_TOKEN; это не диагностика административного BOOTSTRAP_ADMIN_TOKEN и не основание менять существующие credentials. Actual configure root cause (authorization/permissions/transport) пока НЕ УСТАНОВЛЕН: safe probe в административном main workflow в этом ходе ещё не запускался. Не выводить произвольные administrator job logs; использовать только фиксированные redacted categories.

После обязательного review и интеграции: запустить configure с уже сохранённым BOOTSTRAP_ADMIN_TOKEN в main-only automation environment; классифицировать actual safe_probe/status, устранить подтверждённую причину. Не менять существующие ключи по предположению. Убедиться в защите main/required Actions Validate и main-only environments через авторизованный API. Configure оставляет READY=false. Затем отдельный exact-SHA bootstrap smoke при здоровом preflight, verified backup/recovery, без миграций; проверить реальные managed file hashes, HTTP health и trusted delivery evidence; только после успеха выполнить promotion. Реальную routine automatic release также подтвердить run ID/SHA. До этого итог — AUTOMATIC DEPLOYMENT NOT VERIFIED.

Никаких production write/SSH/config edits, SQL migrations, Stage 3/4 deployment, настройки READY или merge bypass в этом ходе не выполнялось.
