#!/usr/bin/env python3
"""
Alertmanager webhook adapter: receives webhooks and forwards to Dooray channels.
"""
import json
import os
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler


PORT = int(os.environ.get("PORT", "9095"))


def format_alert_message(payload: dict) -> str:
    status = payload.get("status", "firing")
    is_resolved = status == "resolved"
    lines = []
    lines.append("✅ [해결됨]" if is_resolved else "🚨 [알림]")
    lines.append(f"상태: {'해결' if is_resolved else '발생'}")
    lines.append("")

    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        severity = (labels.get("severity") or "unknown").upper()
        alertname = labels.get("alertname", "Unknown")
        instance = labels.get("instance", "")
        summary = annotations.get("summary") or annotations.get("message", "-")
        description = annotations.get("description", "")

        lines.append(f"[{severity}] {alertname}")
        if instance:
            lines.append(f"대상: {instance}")
        lines.append(f"요약: {summary}")
        if description:
            lines.append(description)
        lines.append("---")

    return "\n".join(lines)


def build_dooray_body(payload: dict, severity: str) -> dict:
    text = format_alert_message(payload)
    is_resolved = (payload.get("status") or "") == "resolved"
    color = "red" if severity == "critical" else "warning"

    return {
        "botName": "Alertmanager (해결)" if is_resolved else f"Alertmanager ({severity})",
        "text": text.strip(),
        "attachments": [
            {
                "title": "알림 해제" if is_resolved else f"[{severity.upper()}] 알림",
                "text": payload.get("externalURL", "") and f"Prometheus: {payload['externalURL']}" or "",
                "color": "good" if is_resolved else color,
            }
        ],
    }


def forward_to_dooray(dooray_url: str, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        dooray_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 200 and resp.status < 300:
                return
            raise urllib.error.HTTPError(
                dooray_url, resp.status, resp.read().decode(), resp.headers, None
            )
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Dooray {e.code}: {e.read().decode()}")
    except urllib.error.URLError as e:
        raise RuntimeError(str(e.reason))


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        receiver = (payload.get("receiver") or "").lower()
        is_critical = "critical" in receiver
        is_warning = "warning" in receiver

        # 같은 채널 사용을 위한 fallback 로직:
        # 1. severity별 URL이 있으면 우선 사용
        # 2. 없으면 기본 DOORAY_HOOK_URL 사용
        # 3. 그것도 없으면 다른 severity URL 사용 (같은 채널로 보내기)
        dooray_url = None
        if is_critical:
            dooray_url = os.environ.get("DOORAY_HOOK_URL_CRITICAL")
        elif is_warning:
            dooray_url = os.environ.get("DOORAY_HOOK_URL_WARNING")
        
        # fallback: 기본 URL 또는 다른 severity URL 사용 (같은 채널 지원)
        if not dooray_url:
            dooray_url = os.environ.get("DOORAY_HOOK_URL")
        if not dooray_url:
            dooray_url = os.environ.get("DOORAY_HOOK_URL_CRITICAL") or os.environ.get("DOORAY_HOOK_URL_WARNING")

        if not dooray_url:
            print(f"No Dooray URL configured for receiver: {receiver}", flush=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        severity = "critical" if is_critical else "warning"
        dooray_body = build_dooray_body(payload, severity)

        try:
            forward_to_dooray(dooray_url, dooray_body)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            print(f"Dooray forward error: {e}", flush=True)
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b"Dooray forward failed")

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)


def main():
    server = HTTPServer(("", PORT), WebhookHandler)
    print(f"Dooray webhook adapter listening on {PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
