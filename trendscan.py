#!/usr/bin/env python3
"""trendscan.py — pulls trending posts in Raymus's niches via Apify + YouTube Data API.

Output: a dated folder with raw scrape JSON + a self-contained HTML brief at
        Social Media Posts (Image)/personal-brand/_trends/<YYYY-MM-DD>/index.html

Usage:
  python3 trendscan.py                       # all 5 niches, defaults
  python3 trendscan.py --niches ai_video microdrama   # scope to specific niches
  python3 trendscan.py --dry-run             # show plan + cost estimate, don't fire
  python3 trendscan.py --skip-tiktok         # YT-only if you want a free scan
  python3 trendscan.py --skip-instagram
  python3 trendscan.py --max 10              # tighter per-platform cap
"""
import argparse, json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
YT_API_KEY = os.getenv("YT_DATA_API_KEY")

NICHES_CFG = json.loads((HERE / "_niches.json").read_text())
OUTPUT_BASE = Path("/Users/raymuschang/Desktop/Social Media Calendar Pipelines/Social Media Posts (Image)/personal-brand/_trends")

# ───────────────────────────────────────── YouTube Data API ──────────────────
def yt_search(query: str, max_results: int = 20, days: int = 14) -> list[dict]:
    """Search YouTube Shorts by query, last N days, sorted by view count."""
    if not YT_API_KEY:
        return []
    published_after = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoDuration": "short",
        "order": "viewCount",
        "publishedAfter": published_after,
        "maxResults": max_results,
        "key": YT_API_KEY,
    }
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=30)
    if not r.ok:
        print(f"  ⚠ YT search '{query}' failed: {r.status_code} {r.text[:200]}")
        return []
    items = r.json().get("items", [])
    video_ids = [it["id"]["videoId"] for it in items]
    if not video_ids:
        return []
    # Hydrate with statistics + contentDetails
    r2 = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids), "key": YT_API_KEY},
        timeout=30,
    )
    if not r2.ok:
        return []
    out = []
    for it in r2.json().get("items", []):
        sn, st = it.get("snippet", {}), it.get("statistics", {})
        out.append({
            "platform": "youtube",
            "id": it["id"],
            "url": f"https://youtube.com/shorts/{it['id']}",
            "title": sn.get("title", ""),
            "description": sn.get("description", "")[:500],
            "channel": sn.get("channelTitle", ""),
            "channel_id": sn.get("channelId", ""),
            "published_at": sn.get("publishedAt", ""),
            "tags": sn.get("tags", []),
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "duration": it.get("contentDetails", {}).get("duration", ""),
            "thumbnail": sn.get("thumbnails", {}).get("high", {}).get("url", ""),
        })
    return out


# ───────────────────────────────────────── Apify (TT + IG) ───────────────────
def apify_run_actor(actor_id: str, input_data: dict, timeout: int = 300) -> list[dict]:
    """Run an Apify actor synchronously and return dataset items."""
    if not APIFY_TOKEN:
        return []
    actor_path = actor_id.replace("/", "~")
    # Synchronous run + get dataset items
    url = f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items"
    params = {"token": APIFY_TOKEN}
    try:
        r = requests.post(url, params=params, json=input_data, timeout=timeout)
    except requests.exceptions.Timeout:
        print(f"  ⚠ {actor_id} timed out after {timeout}s")
        return []
    if not r.ok:
        print(f"  ⚠ {actor_id} failed: {r.status_code} {r.text[:300]}")
        return []
    try:
        return r.json()
    except Exception:
        return []


def scrape_tiktok(hashtags: list[str], max_per_tag: int = 15) -> list[dict]:
    """Pull top TikTok posts for hashtags via Apify TikTok scraper."""
    actor = NICHES_CFG["apify_actors"]["tiktok_hashtag"]
    items = apify_run_actor(actor, {
        "hashtags": hashtags,
        "resultsPerPage": max_per_tag,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    })
    out = []
    for it in items:
        out.append({
            "platform": "tiktok",
            "id": it.get("id", ""),
            "url": it.get("webVideoUrl", ""),
            "title": it.get("text", "")[:300],
            "description": it.get("text", "")[:500],
            "channel": it.get("authorMeta", {}).get("name", ""),
            "channel_id": it.get("authorMeta", {}).get("id", ""),
            "published_at": it.get("createTimeISO", ""),
            "tags": [h.get("name") for h in it.get("hashtags", []) if h.get("name")],
            "views": int(it.get("playCount", 0)),
            "likes": int(it.get("diggCount", 0)),
            "comments": int(it.get("commentCount", 0)),
            "shares": int(it.get("shareCount", 0)),
            "duration": it.get("videoMeta", {}).get("duration", 0),
            "thumbnail": it.get("videoMeta", {}).get("coverUrl", ""),
        })
    return out


def scrape_instagram(hashtags: list[str], max_per_tag: int = 15) -> list[dict]:
    """Pull top Instagram posts for hashtags via Apify."""
    actor = NICHES_CFG["apify_actors"]["instagram_hashtag"]
    items = apify_run_actor(actor, {
        "hashtags": hashtags,
        "resultsLimit": max_per_tag,
    })
    out = []
    for it in items:
        out.append({
            "platform": "instagram",
            "id": it.get("id", ""),
            "url": it.get("url", ""),
            "title": (it.get("caption") or "")[:300],
            "description": (it.get("caption") or "")[:500],
            "channel": it.get("ownerUsername", ""),
            "channel_id": it.get("ownerId", ""),
            "published_at": it.get("timestamp", ""),
            "tags": it.get("hashtags", []),
            "views": int(it.get("videoViewCount") or it.get("videoPlayCount") or 0),
            "likes": int(it.get("likesCount", 0)),
            "comments": int(it.get("commentsCount", 0)),
            "type": it.get("type", ""),  # GraphImage / GraphSidecar (carousel) / GraphVideo
            "is_carousel": it.get("type") == "Sidecar" or it.get("__typename") == "GraphSidecar",
            "thumbnail": it.get("displayUrl", ""),
        })
    return out


# ───────────────────────────────────────── Orchestrator ──────────────────────
def scan_niche(niche: dict, args) -> dict:
    """Run all enabled scrapers for one niche."""
    print(f"\n→ {niche['label']} ({niche['id']})")
    results = {"niche": niche["id"], "label": niche["label"], "posts": []}

    if not args.skip_youtube and YT_API_KEY:
        for q in niche["yt_queries"][:2]:  # 2 queries per niche to control quota
            print(f"  yt: '{q}'...", flush=True)
            results["posts"].extend(yt_search(q, max_results=args.max, days=args.lookback))

    if not args.skip_tiktok and APIFY_TOKEN:
        print(f"  tt: {niche['tt_hashtags']}...", flush=True)
        results["posts"].extend(scrape_tiktok(niche["tt_hashtags"][:3], max_per_tag=args.max))

    if not args.skip_instagram and APIFY_TOKEN:
        print(f"  ig: {niche['ig_hashtags']}...", flush=True)
        results["posts"].extend(scrape_instagram(niche["ig_hashtags"][:3], max_per_tag=args.max))

    print(f"  → {len(results['posts'])} posts collected")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--niches", nargs="*", help="subset of niche ids to scan")
    ap.add_argument("--max", type=int, default=NICHES_CFG["defaults"]["max_per_platform_per_niche"])
    ap.add_argument("--lookback", type=int, default=NICHES_CFG["defaults"]["lookback_days"])
    ap.add_argument("--skip-tiktok", action="store_true")
    ap.add_argument("--skip-instagram", action="store_true")
    ap.add_argument("--skip-youtube", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="show plan + cost estimate, don't fire")
    args = ap.parse_args()

    selected = NICHES_CFG["niches"]
    if args.niches:
        selected = [n for n in selected if n["id"] in args.niches]
        if not selected:
            sys.exit(f"no niches matched: {args.niches}")

    # Cost estimate
    tt_count = 0 if args.skip_tiktok else len(selected)
    ig_count = 0 if args.skip_instagram else len(selected)
    est = (tt_count * NICHES_CFG["cost_estimates_usd"]["_per_run_typical"]["tiktok_per_niche"]
         + ig_count * NICHES_CFG["cost_estimates_usd"]["_per_run_typical"]["instagram_per_niche"])

    print(f"\n=== /trendscan ===")
    print(f"  niches:     {[n['id'] for n in selected]}")
    print(f"  platforms:  YT={not args.skip_youtube} · TT={not args.skip_tiktok} · IG={not args.skip_instagram}")
    print(f"  lookback:   {args.lookback} days")
    print(f"  max/plat:   {args.max} posts")
    print(f"  apify est:  ~${est:.2f}")
    print(f"  yt quota:   ~{len(selected) * 2 * 100} units (of 10,000/day free)")

    if args.dry_run:
        print("\n[dry-run — not firing]")
        return

    # Output dir
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out_dir = OUTPUT_BASE / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    # Scan in parallel — but limit to 3 concurrent to be safe with rate limits
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(scan_niche, n, args): n["id"] for n in selected}
        for fut in as_completed(futs):
            results.append(fut.result())

    elapsed = time.time() - t0

    # Save raw data
    raw = {
        "timestamp": datetime.now().isoformat(),
        "args": vars(args),
        "scan_duration_sec": round(elapsed, 1),
        "niches": results,
    }
    raw_path = out_dir / "raw_data.json"
    raw_path.write_text(json.dumps(raw, indent=2, default=str))

    # Quick stats
    total = sum(len(n["posts"]) for n in results)
    by_plat = {}
    for n in results:
        for p in n["posts"]:
            by_plat[p["platform"]] = by_plat.get(p["platform"], 0) + 1

    print(f"\n=== DONE in {elapsed:.0f}s ===")
    print(f"  total posts: {total}")
    for plat, c in by_plat.items():
        print(f"    {plat}: {c}")
    print(f"\n  raw data: {raw_path}")
    print(f"  → next: invoke /trendscan in Claude Code to synthesize the trend brief")


if __name__ == "__main__":
    main()
