# NeuroDelo — журнал решений

## 26.10.2026 — продолжение delivery repair

Основание: владелец поручил завершить automatic PR creation, GitHub→SpaceWeb delivery и публикацию существующего public-service-guide. Обычные безопасные релизы разрешены; каждый PR/релиз не требует отдельного подтверждения.

- Сохранить существующие deploy.yml, SSH delivery, private/config.php, данные и uploads. Не включать CRM, миграции и платежи.
- PR creation независимо от AUTOMERGE_ENABLED; merge сохраняет реальные required checks/reviews. Не создавать approvals, не применять --admin/force.
- Сначала получать фактические результаты выбранного grant. Отсутствующее поле API не равно false; недоступная защита не равна отсутствию защиты.
- Диагностика экспортирует только allowlisted booleans/counts, без token, environment dump, response body или client data.
- Успешный deploy не означает работоспособность всей PR automation. Раздельно учитывать feature delivery и остаточные governance/permission blockers.

Новых решений владельца о снижении защиты, отмене review или активации CRM нет.
