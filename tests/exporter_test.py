# SPDX-FileCopyrightText: 2022 Robin Schneider <ro.schneider@senec.com>
#
# SPDX-License-Identifier: Apache-2.0

import unittest
from unittest import mock

from files import exporter

MONITOR = {
    "id": 42,
    "friendlyName": "My site",
    "url": "https://example.com",
    "type": "KEYWORD",
    "status": "UP",
    "interval": 300,
    "keywordType": "ALERT_EXISTS",
    "keywordValue": 'say "hi"',
    "port": None,
    "lastDayUptimes": {
        "bucketSize": 3600,
        "histogram": [{"timestamp": 1, "uptime": 100}, {"timestamp": 2, "uptime": 99}],
    },
}


def _response(status=200, json=None, headers=None):
    resp = mock.Mock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.text = ""
    resp.json.return_value = json
    return resp


class EscapeTest(unittest.TestCase):
    def test_escape_backslash(self):
        self.assertEqual(exporter._escape_label_value(r"test\sdf"), r"test\\sdf")

    def test_escape_quote(self):
        self.assertEqual(exporter._escape_label_value('"test"'), '\\"test\\"')

    def test_escape_newline(self):
        self.assertEqual(exporter._escape_label_value("test\ntest"), r"test\ntest")

    def test_escape_all_special_chars(self):
        self.assertEqual(
            exporter._escape_label_value(
                'One backslash \\ and one ASCII newline \n and one double-quote ".'
            ),
            'One backslash \\\\ and one ASCII newline \\n and one double-quote \\".',
        )

    def test_none_and_lists(self):
        self.assertEqual(exporter._escape_label_value(None), "")
        self.assertEqual(exporter._escape_label_value([1, 2]), "1,2")


class FormatTest(unittest.TestCase):
    def test_status_values(self):
        for status, value in [
            ("UP", 0),
            ("STARTED", 1),
            ("PAUSED", 2),
            ("DOWN", 3),
            ("LOOKS_DOWN", 3),
            ("?", 3),
        ]:
            self.assertEqual(exporter._status_value(status), value)

    def test_format_monitor(self):
        out = exporter.format_prometheus(
            [MONITOR], {42: {"summary": {"avg": 120, "min": 80, "max": 300}}}
        )
        self.assertIn(
            'uptimerobot_status{c1_name="My site",c2_url="https://example.com",c3_type="KEYWORD",'
            'c4_sub_type="",c5_keyword_type="ALERT_EXISTS",c6_keyword_value="say \\"hi\\"",'
            'c7_http_username="",c8_port="",c9_interval="300"} 0\n',
            out,
        )
        self.assertIn('c10_days="1"} 99.5\n', out)
        self.assertIn(
            'uptimerobot_response_time{name="My site",type="KEYWORD",url="https://example.com"} 120\n',
            out,
        )
        self.assertIn("uptimerobot_response_time_max{", out)

    def test_format_monitor_without_stats(self):
        out = exporter.format_prometheus([{"friendlyName": "x", "status": "PAUSED"}])
        self.assertIn("} 2\n", out)
        self.assertNotIn("uptimerobot_uptime{", out)
        self.assertNotIn("uptimerobot_response_time{", out)

    def test_format_accountdetails(self):
        monitors = [
            {"status": "UP"},
            {"status": "DOWN"},
            {"status": "PAUSED"},
            {"status": "UP"},
        ]
        out = exporter.format_prometheus_accountdetails(
            {"email": "a@b.c", "monitorLimit": 50, "monitorsCount": 4}, monitors
        )
        self.assertIn('up_monitors="2",down_monitors="1",paused_monitors="1"} 1\n', out)
        self.assertIn('uptimerobot_monitors{state="down"} 1\n', out)
        self.assertIn("uptimerobot_monitor_limit 50\n", out)

    def test_format_psp(self):
        out = exporter.format_prometheus_psp(
            [
                {
                    "friendlyName": "Status",
                    "urlKey": "abc",
                    "monitorIds": [1, 2],
                    "status": "ENABLED",
                }
            ]
        )
        self.assertIn(
            'uptimerobot_psp{c1_name="Status",c2_custom_url="",'
            'c3_standard_url="https://stats.uptimerobot.com/abc",c4_monitors="1,2"} 1\n',
            out,
        )


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.client = exporter.UptimeRobotClient("key")
        self.get = mock.patch.object(self.client.session, "get").start()
        self.addCleanup(mock.patch.stopall)

    def test_bearer_auth(self):
        self.assertEqual(self.client.session.headers["Authorization"], "Bearer key")

    def test_pagination_follows_cursor_only(self):
        self.get.side_effect = [
            _response(
                json={
                    "data": [{"id": 1}],
                    "nextLink": "https://evil.example/monitors?limit=200&cursor=1",
                }
            ),
            _response(json={"data": [{"id": 2}], "nextLink": None}),
        ]
        self.assertEqual(self.client.fetch_monitors(), [{"id": 1}, {"id": 2}])
        self.assertEqual(self.get.call_count, 2)
        (url,) = self.get.call_args.args
        self.assertEqual(url, "https://api.uptimerobot.com/v3/monitors")
        self.assertEqual(
            self.get.call_args.kwargs["params"], {"limit": 200, "cursor": "1"}
        )

    def test_rate_limit(self):
        self.get.return_value = _response(429, headers={"Retry-After": "30"})
        with self.assertRaises(exporter.ApiError) as ctx:
            self.client.fetch_user()
        self.assertEqual(ctx.exception.retry_after, 30)

    def test_error_response(self):
        self.get.return_value = _response(
            401, json={"message": "Invalid token.", "code": "003-005"}
        )
        with self.assertRaises(exporter.ApiError):
            self.client.fetch_monitors()

    def test_invalid_json(self):
        resp = _response()
        resp.json.side_effect = ValueError()
        self.get.return_value = resp
        with self.assertRaises(exporter.ApiError):
            self.client.fetch_user()


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.client = mock.Mock()
        self.client.fetch_monitors.return_value = [MONITOR]
        self.client.fetch_user.return_value = {"email": "a@b.c", "monitorLimit": 50}
        self.client.fetch_psps.return_value = []

    def test_cache(self):
        collector = exporter.Collector(self.client, cache_ttl=60)
        first = collector.collect()
        collector.collect()
        self.assertIn("uptimerobot_up 1\n", first)
        self.assertEqual(self.client.fetch_monitors.call_count, 1)
        self.client.fetch_response_time.assert_not_called()

    def test_response_times_enabled(self):
        self.client.fetch_response_time.return_value = {"summary": {"avg": 10}}
        out = exporter.Collector(self.client, response_times=True).collect()
        self.client.fetch_response_time.assert_called_once_with(42, 3600)
        self.assertIn("uptimerobot_response_time{", out)

    def test_backoff_on_rate_limit(self):
        self.client.fetch_monitors.side_effect = exporter.ApiError(
            "rate limit", retry_after=60
        )
        collector = exporter.Collector(self.client, cache_ttl=0)
        self.assertIn("uptimerobot_up 0\n", collector.collect())
        self.assertIn("uptimerobot_up 0\n", collector.collect())
        self.assertEqual(self.client.fetch_monitors.call_count, 1)


class ArgsTest(unittest.TestCase):
    def test_env(self):
        env = {
            "UPTIMEROBOT_API_KEY": "k",
            "UPTIMEROBOT_SERVER_PORT": "1234",
            "UPTIMEROBOT_RESPONSE_TIMES": "true",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            args = exporter.parse_args([])
        self.assertEqual(
            (args.apikey, args.server_port, args.response_times), ("k", 1234, True)
        )

    def test_missing_key(self):
        with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(
            SystemExit
        ):
            exporter.parse_args([])


if __name__ == "__main__":
    unittest.main()
