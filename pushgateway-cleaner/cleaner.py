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
BASE_URL = f"http://{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}"

# Pushgateway exposes push time (name may be pushgateway_metric_push_time_seconds or push_time_seconds)
PUSH_TIME_PATTERN = re.compile(
    r"(?:pushgateway_metric_)?push_time_seconds\{([^}]*)\}\s+([\d.eE+-]+)"
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
    # URL path: /metrics/job/<job>/instance/<instance>/<ln>/<lv>/...
    parts = ["/metrics/job", urllib.parse.quote(job, safe="")]
    if labels.get("instance") is not None:
        parts.extend(["instance", urllib.parse.quote(labels["instance"], safe="")])
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
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return True
        print(f"[cleaner] DELETE {path} failed: {e.code}", flush=True)
        return False
    except Exception as e:
        print(f"[cleaner] DELETE {path} error: {e}", flush=True)
        return False


def run_once(now: float) -> int:
    try:
        body = fetch_metrics()
    except Exception as e:
        print(f"[cleaner] fetch metrics failed: {e}", flush=True)
        return 0
    deleted = 0
    for m in PUSH_TIME_PATTERN.finditer(body):
        label_str, value_str = m.group(1), m.group(2)
        try:
            push_ts = float(value_str)
        except ValueError:
            continue
        if now - push_ts <= STALE_SECONDS:
            continue
        labels = parse_labels(label_str)
        path = labels_to_delete_path(labels)
        if not path:
            continue
        if delete_group(path):
            deleted += 1
            print(f"[cleaner] deleted stale group: {path}", flush=True)
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
