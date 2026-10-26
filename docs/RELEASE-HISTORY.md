# NeuroDelo — история подтверждённых релизов

## Public service guide и automation repair, 26.10.2026

- Feature head `8a561f6ecc1b1d250acaf6e57f623f46776675f5`; feature CI40200125083 success.
- [PR#24](https://github.com/2006minden-gif/-Chat-GPT-/pull/24) → main `821a8b58e91f872cd49297963ec0e514cca3c0a9`; production run40275235437 deployed_and_verified.
- [PR#25](https://github.com/2006minden-gif/-Chat-GPT-/pull/25) → main `6171a76805697c2ea774df3dddc46ca6c1ca0249`; CI+Publish run40276737596 success.
- [PR#26](https://github.com/2006minden-gif/-Chat-GPT-/pull/26) → main/deployed `ed2b8b8a607b809f94dc5baa1ac90a8783ca6f76`; [run40278274795](https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40278274795) Validate+Publish success. Exporter40278588225 records exact producer and deployed_and_verified, file backup/recovery, 18 file hashes, finalize.files_verified=true, migrations=[].

Live URL: https://neurodelo.pro/services.php?service=ai. Verified production assets and mobile local brief interactions documented in PROJECT-STATE.md. Feature delivery: DEPLOYED_AND_VERIFIED. Whole automation repair remains incomplete until selected-token PR403 and integration setting discrepancy are resolved or demonstrated as external blockers.

## Earlier visible release, 25.10.2026

PR#23, revision `30efb5f4285433c73be36325009f3e716f465883`, run40198377556: historically deployed_and_verified. Superseded by the revisions above.

## Диагностика GHA grant, PR #27

Main/deployed `c77710a8ac4ed467218211f0500ae34195dcfdd1`; run40279749813 Validate+Publish success, exporter40280063589: deployed_and_verified, file backup/recovery verified, migrations=[]. Application files сохранены. Аудит40280063632 выявил missing REST auto-merge field; сам automation repair пока не завершён.

## Native PR и typed policy, PR #28

Main/deployed `6f1291edf31bee8f31c0940970fc6631825b2c0f`; run40280808627 success. Exporter40281088490: exact revision deployed_and_verified, verified backup/recovery, migrations=[]. Configure integration40281088553 success, protection unchanged. Native creation proof40281018269 → draft#29 при false merging; replay40281288598 → тот же PR, без дубликата. Старый preview отменён новым head; это не PASS. Latest proof push/PR checks40281079415/40281084505 success.

## Подготовленный последний repair, PR #30

Source `348a7cb70a89690306fb621433549d4ad11afa3e`: branch CI40281499149 и explicit native preview40281695641 SUCCESS. GHA auto-created PR#30. Native preview выполняет обязательный Validate без production. Bot-triggered PR run40281697839: action_required; исходный head не интегрирован/не опубликован. Следующее обновление records получает собственный head и требует fresh CI; старый PASS не переносится на него автоматически.

## Интеграция последнего repair, PR #30

Documentation-updated source `cfc29a80ea57e51e76907c45c37ee3546cd522b5`: push40282178098 и PR40282183543 SUCCESS, clean state. [PR#30](https://github.com/2006minden-gif/-Chat-GPT-/pull/30) → main `087b22bcef4eb7b2037ebdee505b93746f168d6a`. Main CI40282458133 проверяется отдельно; запись не утверждает публикацию до producer deployment evidence. Final documentation-only acceptance получает собственный SHA/PR/run. Последующие evidence exports являются источником фактической production revision.

## Исправление приёмочного критерия

PR#31/run40282925637: action_required, zero jobs. Explicit preview success не равен successful normal PR CI и не доказывает постоянную automation. Last verified production остаётся087b22b/run40282458133; новый auth patch и bootstrap PR не считаются последующим unattended acceptance release. См. PR-AUTOMATION-APPROVAL-DIAGNOSIS.md.
