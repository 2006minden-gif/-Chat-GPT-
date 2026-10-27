# Owner first login

The owner explicitly requested creating/configuring owner access and publishing.
The grant in private/owner-bootstrap.json contains only SHA-256 of a random
256-bit capability and a three-day expiry. Its unhashed value stays outside Git,
CI, artifacts and server logs; deliver the personal fragment URL only to the
requesting owner. It is not the permanent password.

GET /owner-setup.php does not expose the grant or account status. The browser
reads the URL fragment into memory and immediately clears it from the address.
The owner chooses a 12–72 byte UTF-8 password; JSON POST enforces same-origin,
capability/expiry, matching password and rate limit. Only password_hash is stored.
A unique nd_admin id=1 INSERT atomically consumes the capability. Existing
accounts can never be reset; no UPDATE/REPLACE exists in this mechanism. Any
replay, including after a file rollback, cannot overwrite an existing owner.
Expired/missing/malformed grants fail closed. No DB migration, config/credential
rewrites, initial password in Git, public registration, or live test account.

CI uses disposable loopback DBs to verify invalid/expired grants, CSRF, validation,
concurrent consumption, actual creation/login/session, replay preservation and
mobile browser fragment removal. Production smoke uses only GET and an invalid
capability POST, which is rejected before any DB access or write. The real grant
remains unused until the owner chooses a password.
