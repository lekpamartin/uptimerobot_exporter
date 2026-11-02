# FROM https://github.com/hnrd/uptimerobot_exporter/blob/master/exporter.py
# Updated by Martin LEKPA
#
# Uses the UptimeRobot v3 API: https://uptimerobot.com/api/v3/

import argparse
import http.server
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests

API_URL = "https://api.uptimerobot.com/v3"
PAGE_LIMIT = 200
REQUEST_TIMEOUT = 30

# Values kept identical to the v2 based exporter so existing dashboards keep working:
# 0 = up, 1 = not checked yet, 2 = paused, 3 = down
STATUS_VALUES = {
    "UP": 0,
    "STARTED": 1,
    "PAUSED": 2,
    "LOOKS_DOWN": 3,
    "DOWN": 3,
}

log = logging.getLogger("uptimerobot_exporter")


class ApiError(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


def _escape_label_value(value: Any) -> str:
    """
    Escape a label value regarding to the prometheus format description
    https://github.com/prometheus/docs/blob/main/content/docs/instrumenting/exposition_formats.md#text-format-details

    From the docs:
    label_value can be any sequence of UTF-8 characters, but the backslash (\\), double-quote ("), and line feed (\n)
    characters have to be escaped as \\, \", and \n, respectively.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ",".join(str(v) for v in value)
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _sample(name: str, labels: Dict[str, Any], value: Any) -> str:
    label_str = ",".join(f'{k}="{_escape_label_value(v)}"' for k, v in labels.items())
    return f"{name}{{{label_str}}} {value}\n"


def _header(name: str, help_text: str, metric_type: str = "gauge") -> str:
    return f"# HELP {name} {help_text}\n# TYPE {name} {metric_type}\n"


class UptimeRobotClient:
    def __init__(self, api_key: str, api_url: str = API_URL):
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "uptimerobot_exporter",
            }
        )

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            resp = self.session.get(
                f"{self.api_url}{path}", params=params, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException as exc:
            raise ApiError(f"GET {path} failed: {exc}") from exc

        if resp.status_code == 429:
            retry_after = None
            try:
                retry_after = float(resp.headers.get("Retry-After", ""))
            except ValueError:
                pass
            raise ApiError(f"GET {path}: rate limit exceeded", retry_after)
        if resp.status_code != 200:
            raise ApiError(f"GET {path}: HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise ApiError(f"GET {path}: invalid JSON response") from exc

    def get_paginated(self, path: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {"limit": PAGE_LIMIT}
        while True:
            page = self.get(path, params)
            if not isinstance(page, dict) or "data" not in page:
                raise ApiError(f"GET {path}: unexpected response: {str(page)[:300]}")
            items.extend(page["data"])
            # Only the cursor is taken from nextLink, the URL itself is never followed
            cursor = parse_qs(urlparse(page.get("nextLink") or "").query).get("cursor")
            if not cursor:
                return items
            params = {"limit": PAGE_LIMIT, "cursor": cursor[0]}

    def fetch_monitors(self) -> List[Dict[str, Any]]:
        return self.get_paginated("/monitors")

    def fetch_psps(self) -> List[Dict[str, Any]]:
        return self.get_paginated("/psps")

    def fetch_user(self) -> Dict[str, Any]:
        return self.get("/user/me")

    def fetch_response_time(self, monitor_id: Any, window: int) -> Dict[str, Any]:
        start = datetime.now(timezone.utc) - timedelta(seconds=window)
        return self.get(
            f"/monitors/{monitor_id}/stats/response-time",
            {"from": start.strftime("%Y-%m-%dT%H:%M:%SZ")},
        )


def _status_value(status: Any) -> int:
    return STATUS_VALUES.get(str(status).upper(), 3)


def _monitor_labels(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "c1_name": item.get("friendlyName"),
        "c2_url": item.get("url"),
        "c3_type": item.get("type"),
        "c4_sub_type": "",
        "c5_keyword_type": item.get("keywordType"),
        "c6_keyword_value": item.get("keywordValue"),
        "c7_http_username": item.get("httpUsername"),
        "c8_port": item.get("port"),
        "c9_interval": item.get("interval"),
    }


def _last_day_uptime(item: Dict[str, Any]) -> Optional[float]:
    histogram = (item.get("lastDayUptimes") or {}).get("histogram") or []
    values = [b["uptime"] for b in histogram if b.get("uptime") is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def format_prometheus(
    data: List[Dict[str, Any]],
    response_times: Optional[Dict[Any, Dict[str, Any]]] = None,
) -> str:
    response_times = response_times or {}
    status = _header(
        "uptimerobot_status",
        "Monitor status (0 = up, 1 = not checked yet, 2 = paused, 3 = down).",
    )
    uptime = _header(
        "uptimerobot_uptime", "Monitor uptime percentage over the last c10_days."
    )
    rt = _header(
        "uptimerobot_response_time", "Monitor average response time in milliseconds."
    )
    rt_min = _header(
        "uptimerobot_response_time_min",
        "Monitor minimum response time in milliseconds.",
    )
    rt_max = _header(
        "uptimerobot_response_time_max",
        "Monitor maximum response time in milliseconds.",
    )

    for item in data:
        labels = _monitor_labels(item)
        status += _sample(
            "uptimerobot_status", labels, _status_value(item.get("status"))
        )

        last_day = _last_day_uptime(item)
        if last_day is not None:
            uptime += _sample("uptimerobot_uptime", {**labels, "c10_days": 1}, last_day)

        summary = (response_times.get(item.get("id")) or {}).get("summary") or {}
        rt_labels = {
            "name": item.get("friendlyName"),
            "type": item.get("type"),
            "url": item.get("url"),
        }
        if summary.get("avg") is not None:
            rt += _sample("uptimerobot_response_time", rt_labels, summary["avg"])
        if summary.get("min") is not None:
            rt_min += _sample(
                "uptimerobot_response_time_min", rt_labels, summary["min"]
            )
        if summary.get("max") is not None:
            rt_max += _sample(
                "uptimerobot_response_time_max", rt_labels, summary["max"]
            )

    return status + uptime + rt + rt_min + rt_max


def format_prometheus_accountdetails(
    data: Dict[str, Any], monitors: List[Dict[str, Any]]
) -> str:
    counts = {"up": 0, "down": 0, "paused": 0}
    for item in monitors:
        value = _status_value(item.get("status"))
        if value == 0:
            counts["up"] += 1
        elif value == 2:
            counts["paused"] += 1
        elif value == 3:
            counts["down"] += 1

    result = _header("uptimerobot_accountdetails", "UptimeRobot account details.")
    result += _sample(
        "uptimerobot_accountdetails",
        {
            "name": data.get("email"),
            "monitor_limit": data.get("monitorLimit"),
            "monitors_count": data.get("monitorsCount"),
            "up_monitors": counts["up"],
            "down_monitors": counts["down"],
            "paused_monitors": counts["paused"],
        },
        1,
    )
    result += _header("uptimerobot_monitors", "Number of monitors by state.")
    for state, count in counts.items():
        result += _sample("uptimerobot_monitors", {"state": state}, count)
    if data.get("monitorLimit") is not None:
        result += _header("uptimerobot_monitor_limit", "Maximum number of monitors.")
        result += f"uptimerobot_monitor_limit {data['monitorLimit']}\n"
    return result


def format_prometheus_psp(data: List[Dict[str, Any]]) -> str:
    result = _header(
        "uptimerobot_psp", "Public status page status (1 = enabled, 0 = paused)."
    )
    for item in data:
        result += _sample(
            "uptimerobot_psp",
            {
                "c1_name": item.get("friendlyName"),
                "c2_custom_url": item.get("customDomain"),
                "c3_standard_url": f"https://stats.uptimerobot.com/{item.get('urlKey')}",
                "c4_monitors": item.get("monitorIds"),
            },
            1 if str(item.get("status")).upper() == "ENABLED" else 0,
        )
    return result


class Collector:
    """Fetches the API at most once per cache_ttl and backs off when rate limited."""

    def __init__(
        self,
        client: UptimeRobotClient,
        cache_ttl: float = 60,
        response_times: bool = False,
        response_time_window: int = 3600,
    ):
        self.client = client
        self.cache_ttl = cache_ttl
        self.response_times = response_times
        self.response_time_window = response_time_window
        self.lock = threading.Lock()
        self.cached: Optional[str] = None
        self.cached_at = 0.0
        self.blocked_until = 0.0

    def _fetch(self) -> str:
        monitors = self.client.fetch_monitors()
        user = self.client.fetch_user()
        psps = self.client.fetch_psps()

        response_times: Dict[Any, Dict[str, Any]] = {}
        if self.response_times:
            for item in monitors:
                if _status_value(item.get("status")) != 0:
                    continue
                response_times[item.get("id")] = self.client.fetch_response_time(
                    item.get("id"), self.response_time_window
                )

        return (
            format_prometheus(monitors, response_times)
            + format_prometheus_accountdetails(user, monitors)
            + format_prometheus_psp(psps)
        )

    def collect(self) -> str:
        with self.lock:
            now = time.time()
            if self.cached is not None and now - self.cached_at < self.cache_ttl:
                return self.cached + self._up(1, 0)
            if now < self.blocked_until:
                log.warning(
                    "Rate limited by UptimeRobot, retrying in %ds",
                    self.blocked_until - now,
                )
                return self._up(0, 0)

            start = time.time()
            try:
                body = self._fetch()
            except ApiError as exc:
                log.error("%s", exc)
                if exc.retry_after is not None:
                    self.blocked_until = time.time() + exc.retry_after
                else:
                    self.blocked_until = time.time() + min(self.cache_ttl, 60)
                return self._up(0, time.time() - start)

            self.cached = body
            self.cached_at = time.time()
            return body + self._up(1, self.cached_at - start)

    @staticmethod
    def _up(value: int, duration: float) -> str:
        return (
            _header(
                "uptimerobot_up", "Whether the last UptimeRobot API query succeeded."
            )
            + f"uptimerobot_up {value}\n"
            + _header(
                "uptimerobot_scrape_duration_seconds",
                "Duration of the UptimeRobot API queries.",
            )
            + f"uptimerobot_scrape_duration_seconds {duration:.3f}\n"
        )


class ReqHandler(http.server.BaseHTTPRequestHandler):
    collector: Collector

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/metrics":
            body = self.collector.collect().encode("utf-8")
            content_type = "text/plain; version=0.0.4; charset=utf-8"
            status = 200
        elif path == "/":
            body = (
                b"<html><head><title>UptimeRobot Exporter</title></head><body>"
                b'<h1>UptimeRobot Exporter</h1><p><a href="/metrics">Metrics</a></p>'
                b"</body></html>"
            )
            content_type = "text/html; charset=utf-8"
            status = 200
        else:
            body = b"Not Found\n"
            content_type = "text/plain; charset=utf-8"
            status = 404

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes", "on")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Export all check results from uptimerobot.com for prometheus scraping."
    )
    parser.add_argument(
        "apikey",
        nargs="?",
        default=os.environ.get("UPTIMEROBOT_API_KEY"),
        help="Your uptimerobot.com API key (env: UPTIMEROBOT_API_KEY).",
    )
    parser.add_argument(
        "--server_name",
        "-s",
        default=os.environ.get("UPTIMEROBOT_SERVER_NAME", "0.0.0.0"),
        help="Server address to bind to (env: UPTIMEROBOT_SERVER_NAME).",
    )
    parser.add_argument(
        "--server_port",
        "-p",
        default=int(os.environ.get("UPTIMEROBOT_SERVER_PORT", "9705")),
        type=int,
        help="Port to bind to (env: UPTIMEROBOT_SERVER_PORT).",
    )
    parser.add_argument(
        "--cache_ttl",
        default=float(os.environ.get("UPTIMEROBOT_CACHE_TTL", "60")),
        type=float,
        help="Seconds during which API results are reused between scrapes (env: UPTIMEROBOT_CACHE_TTL).",
    )
    parser.add_argument(
        "--response_times",
        action="store_true",
        default=_env_bool("UPTIMEROBOT_RESPONSE_TIMES"),
        help="Export response times. Costs one extra API request per up monitor "
        "(env: UPTIMEROBOT_RESPONSE_TIMES).",
    )
    parser.add_argument(
        "--response_time_window",
        default=int(os.environ.get("UPTIMEROBOT_RESPONSE_TIME_WINDOW", "3600")),
        type=int,
        help="Window in seconds used to compute response times (env: UPTIMEROBOT_RESPONSE_TIME_WINDOW).",
    )
    parser.add_argument(
        "--api_url",
        default=os.environ.get("UPTIMEROBOT_API_URL", API_URL),
        help="UptimeRobot API base URL (env: UPTIMEROBOT_API_URL).",
    )
    args = parser.parse_args(argv)
    if not args.apikey:
        parser.error("an API key is required (argument or UPTIMEROBOT_API_KEY)")
    return args


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = parse_args()

    ReqHandler.collector = Collector(
        UptimeRobotClient(args.apikey, args.api_url),
        cache_ttl=args.cache_ttl,
        response_times=args.response_times,
        response_time_window=args.response_time_window,
    )
    httpd = http.server.ThreadingHTTPServer(
        (args.server_name, args.server_port), ReqHandler
    )
    log.info("Listening on %s:%d", args.server_name, args.server_port)
    httpd.serve_forever()
