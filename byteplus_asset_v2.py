#!/usr/bin/env python3
"""
byteplus_asset_v2.py — Real BytePlus Asset Group / Asset API client.

Replaces byteplus_asset_upload.py (which probed wrong endpoints).
Uses Volcengine OpenAPI SigV4 signing on ark.ap-southeast-1.byteplusapi.com.

Endpoints (all on https://ark.ap-southeast-1.byteplusapi.com/?Action=...&Version=2024-01-01):
  - CreateAssetGroup
  - CreateAsset (async — poll GetAsset until Active)
  - GetAsset
  - ListAssetGroups / ListAssets

Auth: HMAC-SHA256 with BYTEPLUS_ACCESS_KEY / BYTEPLUS_SECRET_KEY.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

AK = os.getenv("BYTEPLUS_ACCESS_KEY")
SK = os.getenv("BYTEPLUS_SECRET_KEY")
HOST = "ark.ap-southeast-1.byteplusapi.com"
REGION = "ap-southeast-1"
SERVICE = "ark"
VERSION = "2024-01-01"

if not AK or not SK:
    sys.exit("BYTEPLUS_ACCESS_KEY / BYTEPLUS_SECRET_KEY missing in .env")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date_stamp: str) -> bytes:
    k_date = _hmac_sha256(secret.encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, REGION)
    k_service = _hmac_sha256(k_region, SERVICE)
    return _hmac_sha256(k_service, "request")


def call(action: str, body: dict | None = None, method: str = "POST") -> dict:
    """Sign and execute a Volcengine OpenAPI call. Returns parsed JSON.
    Auto-injects ProjectName from BYTEPLUS_PROJECT env (default 'default') —
    every BytePlus asset action requires this for IAM scoping."""
    body = dict(body or {})
    body.setdefault("ProjectName", os.getenv("BYTEPLUS_PROJECT", "default"))
    body_json = json.dumps(body, separators=(",", ":")).encode("utf-8")
    payload_hash = _sha256_hex(body_json)

    now = datetime.now(timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    query = urlencode([("Action", action), ("Version", VERSION)], quote_via=quote)
    canonical_uri = "/"
    canonical_query = query
    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{HOST}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{x_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = "\n".join([
        method,
        canonical_uri,
        canonical_query,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{date_stamp}/{REGION}/{SERVICE}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256",
        x_date,
        credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])

    signing_key = _signing_key(SK, date_stamp)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth = (
        f"HMAC-SHA256 Credential={AK}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    url = f"https://{HOST}/?{canonical_query}"
    headers = {
        "Content-Type": "application/json",
        "Host": HOST,
        "X-Content-Sha256": payload_hash,
        "X-Date": x_date,
        "Authorization": auth,
    }
    r = requests.request(method, url, headers=headers, data=body_json, timeout=120)
    try:
        return r.json()
    except Exception:
        return {"_status": r.status_code, "_raw": r.text[:1000]}


def create_asset_group(name: str, description: str = "") -> str:
    resp = call("CreateAssetGroup", {
        "Name": name,
        "Description": description,
        "GroupType": "AIGC",
    })
    err = resp.get("ResponseMetadata", {}).get("Error")
    if err:
        sys.exit(f"CreateAssetGroup failed: {err}")
    gid = resp.get("Result", {}).get("Id")
    if not gid:
        sys.exit(f"CreateAssetGroup unexpected response: {json.dumps(resp)[:500]}")
    return gid


def create_asset(group_id: str, url: str, asset_type: str, name: str = "") -> str:
    body = {"GroupId": group_id, "URL": url, "AssetType": asset_type}
    if name:
        body["Name"] = name
    resp = call("CreateAsset", body)
    err = resp.get("ResponseMetadata", {}).get("Error")
    if err:
        sys.exit(f"CreateAsset failed: {err}")
    aid = resp.get("Result", {}).get("Id")
    if not aid:
        sys.exit(f"CreateAsset unexpected response: {json.dumps(resp)[:500]}")
    return aid


def get_asset(asset_id: str) -> dict:
    return call("GetAsset", {"Id": asset_id})


def poll_asset(asset_id: str, timeout: int = 600) -> dict:
    start = time.time()
    last_status = None
    while time.time() - start < timeout:
        resp = get_asset(asset_id)
        result = resp.get("Result", {})
        status = result.get("Status")
        if status != last_status:
            print(f"  [{int(time.time()-start)}s] {asset_id} status: {status}")
            last_status = status
        if status == "Active":
            return result
        if status == "Failed":
            sys.exit(f"Asset failed: {json.dumps(result)[:500]}")
        time.sleep(5)
    sys.exit(f"Asset polling timed out after {timeout}s")


def list_groups() -> list:
    resp = call("ListAssetGroups", {})
    return resp.get("Result", {}).get("Items", []) or resp.get("Result", {}).get("Groups", []) or []


def list_assets(group_id: str) -> list:
    resp = call("ListAssets", {"GroupId": group_id})
    return resp.get("Result", {}).get("Items", []) or resp.get("Result", {}).get("Assets", []) or []


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_g = sub.add_parser("create-group")
    p_g.add_argument("--name", required=True)
    p_g.add_argument("--description", default="")

    p_a = sub.add_parser("create-asset")
    p_a.add_argument("--group", required=True)
    p_a.add_argument("--url", required=True)
    p_a.add_argument("--type", required=True, choices=["Image", "Video", "Audio"])
    p_a.add_argument("--name", default="")
    p_a.add_argument("--wait", action="store_true", help="Poll until Active before returning")

    p_get = sub.add_parser("get")
    p_get.add_argument("asset_id")

    sub.add_parser("list-groups")
    p_la = sub.add_parser("list-assets")
    p_la.add_argument("--group", required=True)

    args = ap.parse_args()
    if args.cmd == "create-group":
        gid = create_asset_group(args.name, args.description)
        print(f"GROUP_ID={gid}")
    elif args.cmd == "create-asset":
        aid = create_asset(args.group, args.url, args.type, args.name)
        print(f"ASSET_ID={aid}")
        if args.wait:
            result = poll_asset(aid)
            print(f"ACTIVE: {json.dumps(result, indent=2)[:600]}")
    elif args.cmd == "get":
        print(json.dumps(get_asset(args.asset_id), indent=2)[:1500])
    elif args.cmd == "list-groups":
        print(json.dumps(list_groups(), indent=2)[:2000])
    elif args.cmd == "list-assets":
        print(json.dumps(list_assets(args.group), indent=2)[:2000])


if __name__ == "__main__":
    main()
