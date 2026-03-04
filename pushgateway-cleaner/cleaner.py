#!/usr/bin/env python3
"""
Pushgateway cleaner: deletes metric groups that have not been pushed for more than
STALE_SECONDS (default 60). Runs periodically.
"""
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error


PUSHGATEWAY_HOST = os.environ.get("PUSHGATEWAY_HOST", "pushgateway")
PUSHGATEWAY_PORT = int(os.environ.get("PUSHGATEWAY_PORT", "9091"))
STALE_SECONDS = int(os.environ.get("STALE_SECONDS", "60"))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "20"))
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
BASE_URL = f"http://{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}"

# Pushgateway uses exactly "push_time_seconds" (see storage/diskmetricstore.go)
# Match line like: push_time_seconds{job="x",instance=""} 1.73e+09
PUSH_TIME_PATTERN = re.compile(
    r"push_time_seconds\s*\{([^}]*)\}\s+([\d.eE+-]+)"
)
PUSH_TIME_LINE = re.compile(
    r"^\s*push_time_seconds\s*\{([^}]*)\}\s+([\d.eE+-]+)"
)


def parse_labels(label_str: str) -> dict[str, str]:
    """Parse Prometheus label string into dict. e.g. job=\"a\",instance=\"b\" -> {job: a, instance: b}"""
    labels = {}
    for part in label_str.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').replace('\\"', '"')
        labels[k] = v
    return labels


def labels_to_delete_path(labels: dict) -> str | None:
    """Build DELETE path /metrics/job/<job>/instance/<instance>/... from labels. job is required."""
    job = labels.get("job")
    if not job:
        return None
    # Grouping key is from URL labels only. Push to /metrics/job/X has key {job:X}; push to
    # /metrics/job/X/instance/Y has key {job:X, instance:Y}. So only add instance to path when non-empty.
    parts = ["/metrics/job", urllib.parse.quote(job, safe="")]
    instance = labels.get("instance")
    if instance:
        parts.extend(["instance", urllib.parse.quote(instance, safe="")])
    for k, v in sorted(labels.items()):
        if k in ("job", "instance"):
            continue
        parts.extend([urllib.parse.quote(k, safe=""), urllib.parse.quote(str(v), safe="")])
    return "/".join(parts)


def fetch_metrics() -> str:
    req = urllib.request.Request(f"{BASE_URL}/metrics")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="replace")


def delete_group(path: str) -> bool:
    """Send DELETE for the given path. Returns True if deleted or already gone (404)."""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[cleaner] DELETE {path} -> HTTP {e.code} body: {body}", flush=True)
        if e.code == 404:
            return True
        return False
    except Exception as e:
        print(f"[cleaner] DELETE {path} error: {e}", flush=True)
        return False


def delete_group_with_fallback(labels: dict) -> bool:
    """Delete by path from labels. If instance is empty, try both /job/X and /job/X/instance/."""
    path = labels_to_delete_path(labels)
    if not path:
        return False
    if delete_group(path):
        return True
    # Push may have used /job/X/instance/ (empty instance); try that if we only sent /job/X
    if not labels.get("instance") and path.count("/") == 3:  # /metrics/job/X
        path_with_instance = f"{path}/instance/"
        if delete_group(path_with_instance):
            return True
    return False


def run_once(now: float) -> int:
    try:
        body = fetch_metrics()
    except Exception as e:
        print(f"[cleaner] fetch metrics failed: {e}", flush=True)
        return 0

    matches = list(PUSH_TIME_PATTERN.finditer(body))
    if not matches:
        for line in body.splitlines():
            m = PUSH_TIME_LINE.match(line)
            if m:
                matches.append(m)
    if not matches and "push_time" in body:
        # Metric might be in different format (e.g. different spacing)
        print(f"[cleaner] push_time found in body but regex did not match. Sample:\n{body[:800]}", flush=True)
    elif not matches:
        if DEBUG:
            print(f"[cleaner] no push_time_seconds groups found (empty or no pushes yet)", flush=True)
        return 0

    deleted = 0
    stale_count = 0
    for m in matches:
        label_str, value_str = m.group(1), m.group(2)
        try:
            push_ts = float(value_str)
        except ValueError:
            continue
        age = now - push_ts
        if age <= STALE_SECONDS:
            if DEBUG:
                print(f"[cleaner] skip (age={age:.0f}s <= {STALE_SECONDS}s): {label_str}", flush=True)
            continue
        stale_count += 1
        labels = parse_labels(label_str)
        path = labels_to_delete_path(labels)
        if not path:
            if DEBUG:
                print(f"[cleaner] no path for labels: {labels}", flush=True)
            continue
        if DEBUG:
            print(f"[cleaner] deleting stale (age={age:.0f}s): {path}", flush=True)
        if delete_group_with_fallback(labels):
            deleted += 1
            print(f"[cleaner] deleted: {path}", flush=True)
        else:
            print(f"[cleaner] delete failed (see above): {path}", flush=True)

    # Always log run summary so logs show activity every CHECK_INTERVAL
    print(f"[cleaner] run: {len(matches)} groups, {stale_count} stale, {deleted} deleted", flush=True)
    return deleted


def main():
    print(
        f"[cleaner] Pushgateway {PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}, "
        f"stale > {STALE_SECONDS}s, check every {CHECK_INTERVAL}s",
        flush=True,
    )
    while True:
        try:
            now = time.time()
            run_once(now)
        except Exception as e:
            print(f"[cleaner] run error: {e}", flush=True)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
