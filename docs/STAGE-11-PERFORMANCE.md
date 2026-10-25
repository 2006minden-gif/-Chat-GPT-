# Stage 11 — производительность

Измерения только loopback PHP 8.4.27 / MySQL 5.7.42 с синтетическими данными. Это не benchmark SpaceWeb и не прогноз нагрузки/времени реального AI или SMTP.

## Изменения по подтверждённому коду

`private/crm/read.php::crm_list`: для projects имя клиента уже загружалось общей веткой deals/orders/projects, затем запрашивалось повторно. Удалён второй идентичный SELECT. Ответ и права не меняются; при странице N проектов устраняются N вызовов. Снижение latency в процентах не измерялось и не заявляется. Остальное обогащение строк содержит bounded N+1: оптимизировать массовыми joins стоит после профилирования реальной staging-нагрузки.

Новый manual API использует 20 jobs на страницу, 20 immutable редакций на задание, максимум 10 файлов и 20KiB содержимого в результате. Индексы project/id и unique job/revision; никакого SELECT всей истории по умолчанию. Invalid project filter возвращает 422, не раскрывает случайно общий список. Статические QA выполняются на ограниченном наборе, без persistent worker/Redis/new runtime.

Фронтенд: shared navigation серверная, без дополнительного polling/отдельной загрузки зависимостей. Один `handoff.js`, existing CSS/system font; внешние CDN не добавлены. Навигация по hash, повторные запросы только по действию; generation marker и disabled submit предотвращают лишние действия. Результаты не грузятся в список полностью: owner выбирает «Посмотреть файлы». Страница не исполняет импортированный HTML/JS/PHP.

## Измеренный эксперимент

`tests/test_system_integration.py::test_07_measured_bounded_lists` делает 5 последовательных HTTP GET `/api.php?r=crm/collab/manual/jobs&page=1`, фиксирует реальные latency в `/tmp/neuro-stage11-performance.json` (синтетическая БД). Итоговые значения перенесены в STAGE-11-REPORT.md. Не сравниваются с «до» — этого endpoint ранее не существовало. Объём fixture мал, для масштабной оценки нужны согласованные staging dataset и нагрузочный профиль.

Browser Chromium 390px проверяет отсутствие горизонтального scroll и JavaScript pageerror в ручном маршруте. Снимок — `docs/stage-11-ux/manual-owner-mobile.png`. Не является accessibility certification или проверкой сгенерированного приложения.

## Ограничения

Списки CRM/collaboration/billing используют ограниченные LIMIT, но OFFSET на глубоких страницах может быть дорогим; keyset pagination требует отдельной измеренной задачи. Production detail Stage10 ограничен graph/revision лимитами, но сообщения/общая история и пользовательские действия со временем требуют retention policy. Нельзя вводить автоматическое удаление без юридического/бизнес-решения.

Дисковое ограничение hosting 1GB: existing quotas private files/безопасный free-space check сохраняются. Actual usage/backup headroom hosting NOT_VERIFIED; автоматическая очистка backup/customer data запрещена. Release package allowlist не менялся по условиям стадии; его полнота — блокер отдельного выпуска, не «оптимизация».
