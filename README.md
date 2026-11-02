# uptimerobot.com prometheus exporter

[![Docker Image CI](https://github.com/lekpamartin/uptimerobot_exporter/actions/workflows/dockerimage.yml/badge.svg)](https://github.com/lekpamartin/uptimerobot_exporter/actions/workflows/dockerimage.yml)

![Grafana Dashboard](dashboards/dashboard.PNG?raw=true "Grafana Dashboard")

Exports all your uptimerobot.com checks for prometheus scraping,
so you can use external, third-party checks in your monitoring setup.

The exporter uses the [UptimeRobot v3 API](https://uptimerobot.com/api/v3/).

## Rate limits

UptimeRobot limits API usage (10 requests/minute on the free plan, `monitor_limit × 2`
on paid plans). Each refresh of the exporter costs 3 requests (monitors, account,
public status pages), plus one request per up monitor when response times are enabled.

API results are cached for `UPTIMEROBOT_CACHE_TTL` seconds (default: 60), so several
Prometheus servers or a short `scrape_interval` do not multiply API calls. When
UptimeRobot answers with HTTP 429, the exporter waits for the `Retry-After` delay
before calling the API again and exposes `uptimerobot_up 0` meanwhile.

On the free plan, monitors are checked every 5 minutes, so `scrape_interval: 5m`
is enough.

## Requirements

- Python 3.8+
- [requests](https://requests.readthedocs.io/)

## Running

Accepted parameters (argument / environment variable):

| Argument                 | Environment variable               | Default                          | Description                                                                                         |
| ------------------------ | ---------------------------------- | -------------------------------- | --------------------------------------------------------------------------------------------------- |
| `apikey`                 | `UPTIMEROBOT_API_KEY`              | (required)                       | Your API key, see [Integrations & API](https://dashboard.uptimerobot.com/integrations). A read-only key is enough. |
| `--server_name`          | `UPTIMEROBOT_SERVER_NAME`          | `0.0.0.0`                        | Address to bind the HTTP server to                                                                  |
| `--server_port`          | `UPTIMEROBOT_SERVER_PORT`          | `9705`                           | Port to bind the HTTP server to                                                                     |
| `--cache_ttl`            | `UPTIMEROBOT_CACHE_TTL`            | `60`                             | Seconds during which API results are reused                                                         |
| `--response_times`       | `UPTIMEROBOT_RESPONSE_TIMES`       | `false`                          | Export response times (one extra API request per up monitor)                                        |
| `--response_time_window` | `UPTIMEROBOT_RESPONSE_TIME_WINDOW` | `3600`                           | Window in seconds used to compute min/avg/max response times                                        |
| `--api_url`              | `UPTIMEROBOT_API_URL`              | `https://api.uptimerobot.com/v3` | API base URL                                                                                        |

Metrics are served on `/metrics`.

### Docker

The image is published as a
[GitHub package](https://github.com/lekpamartin/uptimerobot_exporter/pkgs/container/uptimerobot_exporter)
on the GitHub Container Registry, for amd64, arm/v6, arm/v7 and arm64:

| Tag              | Content                              |
| ---------------- | ------------------------------------ |
| `latest`         | last commit on `master`              |
| `X.Y.Z`, `X.Y`   | releases (git tags `vX.Y.Z`)         |
| `sha-<commit>`   | a given commit                       |

The image is based on the official `python` Alpine image, without pip, runs as a
non-root user and is scanned with [Trivy](https://trivy.dev/) before being published.

The image is also available on Docker Hub as `lekpamartin/uptimerobot_exporter`.

```bash
docker pull ghcr.io/lekpamartin/uptimerobot_exporter:latest
docker run -d --name uptimerobot_exporter -e 'UPTIMEROBOT_API_KEY=your_uptime_robot_api_key' -p 9705:9705 --read-only ghcr.io/lekpamartin/uptimerobot_exporter:latest
```

Pin a release tag (e.g. `ghcr.io/lekpamartin/uptimerobot_exporter:1.0.0`) instead of `latest` in production.

#### docker-compose

```yaml
services:
  exporter:
    image: ghcr.io/lekpamartin/uptimerobot_exporter:latest
    restart: unless-stopped
    environment:
      UPTIMEROBOT_API_KEY: your_uptime_robot_api_key
    ports:
      - 9705:9705
    read_only: true
```

#### Building the image

No QEMU emulation is needed to build for another architecture.

```bash
# Build for the local platform
./build.sh

# Build for all platforms and push lekpamartin/uptimerobot_exporter:1.2.3 to Docker Hub
docker login
./build.sh 1.2.3 push
```

`IMAGE_NAME` and `PLATFORMS` environment variables override the image name and platforms.

### Others

```bash
pip install requests
python files/exporter.py -h
```

## Exported data

| Metric                                                                  | Description                                                                                       |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `uptimerobot_status`                                                    | Monitor status: 0 = up, 1 = not checked yet, 2 = paused, 3 = down. Labels: name, url, type, keyword, interval… |
| `uptimerobot_uptime{c10_days="1"}`                                      | Uptime percentage over the last 24 hours                                                          |
| `uptimerobot_response_time`, `_min`, `_max`                             | Average, minimum and maximum response time (ms), only with `UPTIMEROBOT_RESPONSE_TIMES=true`      |
| `uptimerobot_accountdetails`                                            | Account details (email, monitor limit, number of up/down/paused monitors) as labels               |
| `uptimerobot_monitors{state}`                                           | Number of up, down and paused monitors                                                            |
| `uptimerobot_monitor_limit`                                             | Maximum number of monitors                                                                        |
| `uptimerobot_psp`                                                       | Public status pages (1 = enabled, 0 = paused)                                                     |
| `uptimerobot_up`                                                        | 1 if the last API query succeeded                                                                 |
| `uptimerobot_scrape_duration_seconds`                                   | Duration of the API queries                                                                       |

### Migration from the v2 API based versions

- Monitor types are now names (`HTTP`, `KEYWORD`, `PING`…) instead of numbers.
- `uptimerobot_response_time` is disabled by default (see rate limits) and is now an average over `UPTIMEROBOT_RESPONSE_TIME_WINDOW`.
- `uptimerobot_accountdetails` no longer has the `monitor_interval` label, `uptimerobot_psp` no longer has `c5_sort`.

## Grafana / Prometheus

1. Deploy exporter
2. Add target in prometheus
3. Add prometheus Data source in grafana
4. Import a Grafana dashboard and pick your Prometheus data source in the `Data source` variable:
   - Grafana 13+: [dashboards/grafana-v2.json](dashboards/grafana-v2.json) (dashboard schema v2):
     overview (exporter status, up/down/paused monitors, 24h uptime, monitor quota),
     monitors table, status history, uptime and response times, public status pages
     and exporter health. Filter by exporter instance, monitor type and monitor.
   - Older Grafana versions: [dashboards/grafana.json](dashboards/grafana.json) (or ID 9955)

   Enjoy !!!

## Docs

Forked from https://github.com/hnrd/uptimerobot_exporter.git
