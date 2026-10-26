# Recurring approval gate and supported unattended authentication

Diagnosis date: 2026-10-26. Completion status: NOT ACCEPTED until the subsequent-PR test below passes.

## Exact rule and primary evidence

GitHub changed this behavior on 2026-06-11. PR events opened/synchronize/reopened caused by the repository GITHUB_TOKEN create approval-required workflows. This is a recurring token/event rule, not a one-time installation approval or the ordinary first-time-fork contributor rule.

Primary sources:
- https://github.blog/changelog/2026-06-11-bot-created-pull-requests-can-run-workflows-if-approved/
- https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow

GitHub recommends App installation tokens or PATs for unattended automation-created PR workflows. A per-run approval does not remove the native-token rule for later PR events. Raising native job permissions or enabling Actions PR creation does not change this identity rule.

Observed repository evidence:

| Evidence | Result |
| --- | --- |
| PR #31 | author github-actions[bot], author_association=CONTRIBUTOR, same source and target repository 2006minden-gif/-Chat-GPT- |
| Run 40282925637 | pull_request, opened by github-actions[bot], exact head 8365fc0600217c8f3361a6e9a8b7858cbfcc0cb8, completed/action_required, jobs=[] |
| Public run page | awaiting maintainer approval in #31; https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/40282925637 |
| Creating workflow 40282901041 | App token steps skipped; selected native fallback; created PR #31 |
| Earlier #29/#30 | historical action_required recorded in previous session; current closed/superseded runs 40281042223/40281697839 now report failure with zero jobs; do not claim their current conclusion is action_required |
| Preview 40282923688 | succeeded independently; did not release the held PR workflow or make PR #31 clean |
| Actual governance audit 40280063632 | strict Actions Validate=true, enforce_admins=true, required_approvals=0; Actions PR permission=true |

This is not a missing PR review. Nor is it evidence that a generic malicious-workflow hold or a fork policy was the cause. The selected token, same-repo event, repeat history, contributor association, public approval banner and documented native-token rule agree. Other GitHub security holds remain authoritative if encountered later.

## Implemented permanent path

Use the existing pinned create-github-app-token integration, or an explicit dedicated fine-grained PAT. Remove the GITHUB_TOKEN and administrative-token fallback from PR writes. Missing credentials stop before network/PR creation. No automatic workflow approval, fake reviews, changed fork settings, pull_request_target execution, dummy commits, or native-token preview substitute.

PR creation stays independent of AUTOMERGE_ENABLED. Exact repo/workflow/run/head checks, trusted-main controller, CI-definition comparison, concurrency, reuse/race handling remain. Merge uses the separate App/PAT write credential; existing BOOTSTRAP_ADMIN_TOKEN reads actual policy. Only clean controller-owned PRs with current required checks/reviews are eligible. Production still uses existing deploy.yml and SpaceWeb SSH delivery.

The native job token loses contents/PR write in these jobs. It can still explicitly dispatch existing main maintenance CI where that existing guarded path is needed; it is not used for PR creation, mutation or merge.

## One-time owner configuration and consequences

Recommended: install a dedicated GitHub App on ONLY 2006minden-gif/-Chat-GPT-.

Repository permissions for the installation:
- Pull requests: read and write, to create/update/merge eligible PRs.
- Contents: read and write, to read refs/CI definitions and perform protected merges.
- Actions: read, to verify authoritative workflow runs/jobs.
- Checks: read, to inspect required check evidence.
- Metadata: GitHub's implicit read access.

No Administration write, Secrets access, production credentials, new bypass actor, or reduced branch protection is requested. Minted creation tokens are further restricted to Contents read, Pull requests write, Actions read. Merge tokens request Contents write, Pull requests write, Checks read, Actions read; policy administration remains separate.

Configure the existing numeric repository variable AUTOMERGE_APP_ID and the existing secret name AUTOMERGE_APP_PRIVATE_KEY in the main-only automation environment. Store the key directly in GitHub Secrets, not chat or Git. Keep the environment restricted to main and the App out of branch/ruleset bypass lists. The key allows minting installation tokens for the App's permitted installation; installation tokens are short lived and job-scoped tokens are revoked by the pinned action. App operations are attributed to its bot account.

Supported alternative: an explicitly authorized fine-grained PAT in automation environment secret PR_AUTOMATION_TOKEN, selected-repository access only, Contents write, Pull requests write, Actions read, Checks read. It acts as the owning user and requires expiry/rotation. Do not copy ChatGPT connector credentials or assume BOOTSTRAP_ADMIN_TOKEN has PR-write scope: its previous POST PR returned403. Existing administrative grant is retained only for policy reads/configuration already authorized.

The owner must authorize/provision one of these identities. Current evidence proves the App path was not selected; it does not establish access to an App private key or a suitable dedicated PAT. No secret values are inspected or exported. This is a bounded credential capability decision, not permission to turn off human workflow approval generally.

References for scope and token behavior:
- https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request
- https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation

## Acceptance after activation

1. Integrate the real authentication repair using the existing permitted bootstrap connection and mandatory checks. This bootstrap PR is not acceptance evidence for unattended delivery.
2. Create a subsequent legitimate, useful project change after the supported identity is configured; do not add dummy commits or reopen a held native-token PR to evade its gate.
3. Observe GHA automatic creation using the App/PAT, normal pull_request Validate executing on the actual PR/merge candidate with jobs started and no routine owner approval.
4. Observe protected integration by the automation identity and real main CI. Do not assume events fired merely because an API call succeeded.
5. Correlate SpaceWeb producer run and deployed main revision; verify file hashes, healthy public site, file backup/recovery, config/data preservation, migrations=[].
6. Record source/merge/deployed SHAs and all run links in project state/release history. Only then declare the repair accepted.

PR #31 and run40282925637 remain evidence. During this diagnosis, the existing bot merged #31 at07:14:27Z into166fbfad87415762a6db29537b553ccb6ec27c9d. Its original PR run now reports failure with zero jobs. Neither that merge nor its separate successful preview proves normal PR CI passed. No approval or dummy update was applied by this repair. The new merge guard requires an actual successful normal PR workflow/Validate job for the exact head/base and trusted CI definition; a green preview cannot substitute.
