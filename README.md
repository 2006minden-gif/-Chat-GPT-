# НейроДело

Главная страница, портфолио и личный редактор портфолио `/studio.php`. Контакты ведут напрямую в MAX и Telegram. CRM, заявки, клиентские кабинеты, бриф, оплата и автоматические уведомления удалены.

PHP 8.4, MySQL 5.7, Apache с mod_rewrite. Рабочая схема — `database/schema.sql`: три таблицы авторизации и три таблицы портфолио. Конфигурация `private/config.php` и загруженные файлы находятся вне публичного каталога. Пароль существующего владельца сохраняется.

Публикация выполняется проверенным GitHub Actions → SSH каналом. Перед каждой публикацией проверяются резервные копии и восстановление полной базы во временные таблицы. Подробнее: [CI/CD](docs/CICD.md), [удаление старых систем](docs/PORTFOLIO-ONLY.md).

Для ручной работы с заказчиками: [шесть шаблонов Word](manual-templates/NeuroDelo_shablony_DOCX.zip).

Проверки для разработчика запускаются только с отдельной локальной базой:

```sh
python scripts/deploy/release.py --check
node --test tests/site.test.cjs
NEURO_TEST_DSN='mysql:host=127.0.0.1;port=3306' python scripts/run-tests.py -v
```

Для браузерных и Apache тестов задаются `CHROMIUM_BIN`, `APACHE_BIN`, `APACHE_MODULE_DIR`. Полный набор проверок PHP 8.4/MySQL 5.7 выполняется в GitHub Actions перед публикацией.
