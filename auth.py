"""Auth resolver — picks the right credential path for the runtime.

Three paths, in priority order:

1. **Service account JSON** (production / Render, when org policy allows).
   Set env var `GOOGLE_SVC_ACCOUNT_JSON` to the FULL JSON of the service-account
   key. The key authenticates as `<svc>@<project>.iam.gserviceaccount.com`.
   Each show's bible + episode sheets must be shared with that email as Editor.

1b. **OAuth user token via env var** (production fallback when (1) is blocked
   by `iam.disableServiceAccountKeyCreation` org policy).
   Set env var `GOOGLE_USER_TOKEN_JSON` to the contents of your local
   `token.json`. Same OAuth identity that works locally; refresh token works
   indefinitely until manually revoked. Less auditable than a service account
   but unblocks deploy when svc keys aren't allowed.

2. **OAuth user token from disk** (local dev).
   Reads `token.json` (already authorized) or runs the InstalledAppFlow against
   `client_secret.json`, opening a browser to authorize. Writes `token.json`
   on success.

Same `SCOPES` either way: spreadsheets + drive.

All three paths return a `google.auth.credentials.Credentials` instance that
gspread + the Drive client both accept.
"""
import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HERE = Path(__file__).parent
CLIENT_SECRET = HERE / "client_secret.json"
TOKEN = HERE / "token.json"


def get_credentials():
    """Return a Credentials object, picking service-account if env var set,
    otherwise OAuth user creds. The return type differs slightly between the
    two paths (Credentials vs ServiceAccountCredentials) but both implement
    the same interface gspread/google-api-python-client need."""

    # Path 1 — service account (production, when org policy allows).
    svc_json = os.environ.get("GOOGLE_SVC_ACCOUNT_JSON", "").strip()
    if svc_json:
        try:
            info = json.loads(svc_json)
        except json.JSONDecodeError as e:
            raise SystemExit(
                f"GOOGLE_SVC_ACCOUNT_JSON is set but isn't valid JSON: {e}\n"
                "Paste the entire contents of the service account .json file "
                "(including the surrounding {} braces) as the env var value."
            )
        return ServiceAccountCredentials.from_service_account_info(
            info, scopes=SCOPES,
        )

    # Path 1b — OAuth user token via env var (production fallback when the
    # GCP org policy disables service account keys, e.g. Workspace orgs with
    # iam.disableServiceAccountKeyCreation). Paste the contents of your
    # local token.json into GOOGLE_USER_TOKEN_JSON. The refresh token works
    # indefinitely until manually revoked. Less auditable than a service
    # account but functional, and identical to the local-dev code path.
    user_json = os.environ.get("GOOGLE_USER_TOKEN_JSON", "").strip()
    if user_json:
        try:
            info = json.loads(user_json)
        except json.JSONDecodeError as e:
            raise SystemExit(
                f"GOOGLE_USER_TOKEN_JSON is set but isn't valid JSON: {e}\n"
                "Paste the entire contents of your local token.json file."
            )
        creds = Credentials.from_authorized_user_info(info, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    # Path 2 — OAuth user creds (local dev).
    creds: Credentials | None = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not CLIENT_SECRET.exists():
            raise SystemExit(
                f"No GOOGLE_SVC_ACCOUNT_JSON env var AND no {CLIENT_SECRET} "
                "for OAuth flow. Either set the service-account env var "
                "(production), or place client_secret.json in the project root "
                "and run `python3 auth.py` to authorize (local dev)."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=0)

    TOKEN.write_text(creds.to_json())
    return creds


if __name__ == "__main__":
    creds = get_credentials()
    if isinstance(creds, ServiceAccountCredentials):
        print(f"✓ Authenticated via service account: {creds.service_account_email}")
    else:
        print(f"✓ Authenticated via OAuth user token: {TOKEN}")
