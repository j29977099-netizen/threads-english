"""Refresh the long-lived Threads access token.

Long-lived tokens last 60 days and can be refreshed once they are at least
24 hours old; each refresh restarts the 60 days. The workflow runs this weekly.
The new token is written to --out and never printed.

    THREADS_ACCESS_TOKEN=... python tools/refresh_token.py --out /tmp/token
"""
import argparse
import os
import sys

import requests

HOST = os.environ.get("THREADS_OAUTH_HOST", "https://graph.threads.com")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="file to write the refreshed token to")
    args = parser.parse_args(argv)

    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        print("THREADS_ACCESS_TOKEN is not set", file=sys.stderr)
        return 2
    resp = requests.get(HOST + "/refresh_access_token",
                        params={"grant_type": "th_refresh_token", "access_token": token}, timeout=30)
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400 or "access_token" not in body:
        print("refresh failed: %s" % (body.get("error", {}).get("message") or "HTTP %d" % resp.status_code),
              file=sys.stderr)
        return 1

    new = body["access_token"]
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(new)
    changed = new != token
    print("token refreshed: valid for %d more days (%s value)"
          % (body.get("expires_in", 0) // 86400, "new" if changed else "same"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write("changed=%s\n" % str(changed).lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
