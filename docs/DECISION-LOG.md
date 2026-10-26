# NeuroDelo — журнал решений

## 26.10.2026 — продолжение delivery repair

Основание: владелец поручил завершить automatic PR creation, GitHub→SpaceWeb delivery и публикацию существующего public-service-guide. Обычные безопасные релизы разрешены; каждый PR/релиз не требует отдельного подтверждения.

- Сохранить существующие deploy.yml, SSH delivery, private/config.php, данные и uploads. Не включать CRM, миграции и платежи.
- PR creation независимо от AUTOMERGE_ENABLED; merge сохраняет реальные required checks/reviews. Не создавать approvals, не применять --admin/force.
- Сначала получать фактические результаты выбранного grant. Отсутствующее поле API не равно false; недоступная защита не равна отсутствию защиты.
- Диагностика экспортирует только allowlisted booleans/counts, без token, environment dump, response body или client data.
- Успешный deploy не означает работоспособность всей PR automation. Раздельно учитывать feature delivery и остаточные governance/permission blockers.

Новых решений владельца о снижении защиты, отмене review или активации CRM нет.

## Проверенный аудит existing grant

Run40280063632 подтвердил ноль обязательных approvals, strict Validate с admin enforcement и Actions PR permission=true. Сохраняем именно эти правила. Отсутствующее REST-поле читаем через typed GraphQL, не включаем настройку вслепую. Создание PR использует минимальный native job token (либо configured App), administrative grant остаётся у существующей main-only проверки policy. Новых credentials и изменений scope не требуется предполагать до проверки native пути.

## Проверка native PR и границы автоматического слияния

PR#29 создан реальным GHA native token при выключенном merging, повторный validated head переиспользовал его. Proof закрыт/remote branch удалена; production из него не запускалась. В административном scope токена нет необходимости для записи PR/merge: используем отдельный native/App token с явными job permissions. Native-token preview completion должен продолжать approved job, затем exact main CI dispatch компенсирует suppressed push event.

Старые/manual PR (включая #6) не являются текущей delivery-задачей. Auto-merge ограничен controller-owned PR с trusted-run provenance; это выбор scope, а не замена required checks/review. Draft CRM остаётся исключена.

## Обработка action_required без обхода

PR#30 native preview прошёл, но original PR workflow action_required оставил merge state unstable. Две попытки merge отклонены automatic approval review; merge не выполнен. Сохраняем gate. Документируем evidence и выполняем обычный CI после необходимых обновлений project records; не публикуем код в обход checks, не подделываем workflow/review approvals. При сохранении gate требуется одна внешняя workflow approval, не ручной merge или deployment.

## Снятие исторического gate и итоговая приёмка

После необходимого documentation update GitHub выполнил ordinary push/PR CI нового head (40282178098/40282183543), обе проверки SUCCESS, merge state clean. PR#30 слит разрешённым exact-head способом в 087b22b; original action_required не был подделан или объявлен успешным. Проверяем финальный documentation-only PR существующей автоматизацией; его actual run/evidence определяет факт полного цикла.

## Постоянная аутентификация, 26.10.2026

Подтверждено официальными GitHub Docs и changelog11.06.2026: GITHUB_TOKEN-generated PR events opened/synchronize/reopened создают approval-required workflows. PR#31 same-repo/CONTRIBUTOR, run40282925637 jobs=0 подтверждает этот recurring gate. Предыдущее предположение о достаточности native preview отвергнуто.

Подготовлен fail-closed App/PAT path без native/admin fallback для PR writes. Никаких workflow approvals, ослабления settings/protection или dummy commits. Установка scoped App либо dedicated PAT — ещё не принятое решение владельца; exact permissions/consequences и acceptance описаны в PR-AUTOMATION-APPROVAL-DIAGNOSIS.md. Completion требует следующего легитимного unattended PR → checks → integrate → SpaceWeb → evidence.

## Наблюдение существующего bot merge во время диагностики

Старый controller самостоятельно слил#31 в166fbfa в07:14:27Z. Original PR workflow40282925637 завершён failure с нулём jobs. Это НЕ acceptance. Ветка bootstrap обновлена настоящим merge текущего main с сохранением project records, без dummy commit. Добавлен отдельный exact head/base normal pull_request workflow/Validate gate, чтобы head preview и mergeable state не заменяли intended PR CI.
