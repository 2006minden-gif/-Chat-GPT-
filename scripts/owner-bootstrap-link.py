#!/usr/bin/env python3
"""Generate a one-time first-login link for the owner (after payment).

Creates a fresh 32-byte capability token, writes ONLY its SHA-256 and an
expiry into private/owner-bootstrap.json, and prints the client-ready link:
    https://neurodelo.pro/owner-setup.php#token=<64 hex>

The raw token is never stored on disk. Deliver the link over a private
channel; it expires automatically (default 3 days) and is consumed atomically
when the admin account is created.
"""
import argparse, hashlib, json, secrets, sys, time
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='private/owner-bootstrap.json', help='grant file path')
    ap.add_argument('--days', type=int, default=3, help='validity in days (default 3)')
    ap.add_argument('--base-url', default='https://neurodelo.pro', help='site base URL (no trailing slash)')
    args = ap.parse_args()

    if args.days < 1 or args.days > 30:
        print('error: --days must be between 1 and 30', file=sys.stderr); return 2

    token = secrets.token_hex(32)
    grant = {
        'enabled': True,
        'expires_at': int(time.time()) + args.days * 86400,
        'token_sha256': hashlib.sha256(token.encode()).hexdigest(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp'); tmp.write_text(json.dumps(grant, indent=2) + '\n')
    try:
        out.chmod(0o600)
    except OSError:
        pass
    tmp.replace(out)

    print(f'Grant written : {out} (hash only, chmod 600 attempted)')
    print(f'Valid until   : {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(grant["expires_at"]))}')
    print()
    print('ONE-TIME LINK (send via private channel, then delete your copy):')
    print(f'{args.base_url.rstrip("/")}/owner-setup.php#token={token}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
