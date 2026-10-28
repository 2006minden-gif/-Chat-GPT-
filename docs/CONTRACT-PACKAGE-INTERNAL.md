# Только владельцу и Codex

Этот файл и manifest.json НЕ ПЕРЕДАВАТЬ заказчикам и не включать в клиентские PDF.
Этот архив заменяет монолитный neurodelo_contract_package.docx как источник шаблонов.

## Файлы
01_contract.docx — договор; 02_specification.docx — ТЗ; 03_acceptance_act.docx — акт; 04_change_agreement.docx — допсоглашение; 05_portfolio_permission.docx — разрешение на портфолио; 06_review_permission.docx — отзыв и разрешение на публикацию.
Каждый файл — самостоятельный шаблон, а не раздел для поиска по номеру страницы. Номера страниц меняются при заполнении; разбивать по ним запрещено.

## Разделение адресатов
В клиентских шаблонах нет пояснений об исходниках, источников законодательства, инструкций по внедрению или юридической проверке. Они содержат поля {{...}} до заполнения. Шаблон с незаполненными полями не является готовым документом для клиента.
Тексты являются проектами для согласования. Перед включением в использование проверить правовую модель сделки, авторский заказ при применимости, потребительские отношения, цепочку прав и персональные данные. Нельзя обещать юридическую экспертизу на основании этих файлов.

## Кодекс внедрения
Use manifest.json as an explicit allowlist. Import only the six customer templates, separately, into the existing private template registry. Do not render the archive or this guide. Each applicable template must produce its own private downloadable PDF. Keep draft/approved versions and owner approval gates. Never infer owner approval from file existence or successful import.
Use the saved owner profile and reviewed client details; commercial conditions come only from an owner-approved proposal. Freeze exact inputs and template versions. Changes must not rewrite sent/signed documents. Block PDF release if required placeholders, missing approvals, invalid totals or unresolved optional fields remain.
Remove optional absent lines cleanly. owner.postal_address_line is either a complete reviewed postal address line or an empty removable paragraph. Email is the primary agreed correspondence channel; this does not replace signing or special statutory delivery methods. Do not invent a physical address.
Current signing is paper signatures with private scan/photo exchange and owner review; no SMS service or code-based signing. Preserve original uploads and signed versions. No automatic legal validation of an image.
Use the actual existing brand header once per page. Do not prepend NeuroDelo to document titles or repeat branding in the footer. Preserve 13 pt body text and generous line/paragraph spacing. Export with Cyrillic-capable fonts and inspect generated PDFs.

## Проверки перед выдачей
- Все обязательные данные реальны и проверены владельцем; клиент и подписант выбраны корректно.
- ТЗ содержит конкретные функции, исходные условия, однозначные сроки, критерии приёмки, зависимости, стоимость и график платежей.
- price.rights_fee заполнено и включено в цену, модель прав проверена; для допсоглашения указаны новая цена и изменение вознаграждения за права.
- spec.milestones разворачивается в согласованный график с результатами, датами, критериями и ценой каждого этапа. При внедрении его можно отображать повторяемыми строками таблицы; текст нельзя обрезать.
- support.duration и support.start_event утверждены, не подставлены автоматически. Закрытие кабинета не прекращает законные требования и не удаляет доказательства.
- В акте явно фиксируются отсутствие или наличие замечаний и оставшихся обязательств; пустое поле не трактовать как отсутствие замечаний.
- Публикации всегда отдельные добровольные решения по точной версии материалов. Формы 05/06 не являются универсальными согласиями на распространение персональных данных. До публикации идентифицирующих сведений проверить основание и подготовить отдельное согласие по статье 10.1 Закона № 152-ФЗ, если требуется; для изображения — статью 152.1 ГК РФ. До выполнения требований блокировать соответствующую публикацию, а не прятать нерешённый вопрос в клиентском тексте.
- Подтверждение оплаты остаётся ручным; официальный чек выдаётся в «Мой налог». Акт и счёт не заменяют чек.

## Когда выдавать
Договор + ТЗ — после проверки реквизитов и условий, до подписания. Акт — по фактической готовности результата. Допсоглашение — при согласованных изменениях. Формы 05/06 — отдельные добровольные запросы при завершении заказа. Не высылать все шесть файлов каждому клиенту автоматически.

## Учёт изменений
Служебное введение и юридические пояснения вынесены сюда. Убраны повторные названия продолжений договора, подсказки «заполнить», инструкции по редактированию шаблона, объединение акта с изменением задания, объединение двух разных разрешений. Основные договорные условия сохранены. Форма изменения развёрнута в самостоятельное допсоглашение. Необязательный почтовый адрес обрабатывается отдельно. Суммы, сроки, реквизиты и юридическое одобрение не выдуманы.
