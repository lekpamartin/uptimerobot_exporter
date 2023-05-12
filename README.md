# uptimerobot.com prometheus exporter

[![Docker Image Version (latest semver)](https://img.shields.io/docker/v/lekpamartin/uptimerobot_exporter)](https://hub.docker.com/r/lekpamartin/uptimerobot_exporter/tags)

![Grafana Dashboard](dashboards/dashboard.PNG?raw=true "Grafana Dashboard")

Exports all your uptimerobot.com checks for prometheus scraping,
so you can use external, third-party checks in your monitoring setup.

If you do not have a pro account, any scrape interval shorter than
`scrape_interval: 5m` for this exporter will a) produce duplicated data
and b) misuse uptimerobots API.

## Requirements

- Python
- [requests](http://www.python-requests.org/en/master/)

## Running

Accepted parameters:

- api_key: Your uptimerobot.com API key. See section 'API Settings' in [your account details](https://uptimerobot.com/dashboard#mySettings).
- server_name (optional): Name to bind the HTTP server to. Default: 0.0.0.0
- server_port (optional): Port to bind the HTTP server to. Default: 9705

### Docker

```bash
docker run -d --name uptimerobot_exporter -e 'UPTIMEROBOT_API_KEY=your_uptime_robot_api_key' -p 9705:9705 --read-only lekpamartin/uptimerobot_exporter
```

#### docker-compose

Example compose file:

    version: '2.1'

    services:
      exporter:
        image: lekpamartin/uptimerobot_exporter
        restart: unless-stopped
        environment:
          UPTIMEROBOT_API_KEY: your_uptime_robot_api_key
        ports:
          - 9705:9705
        read_only: true

### Others

You can either pass script arguments (run `python exporter.py -h` for an explanation)
or set the following environment variables:

- `UPTIMEROBOT_API_KEY`
- `UPTIMEROBOT_SERVER_NAME`
- `UPTIMEROBOT_SERVER_PORT`

## Exported data

- number of down monitors : down_monitors
- number of up monitors : up_monitors
- number of paused monitors : paused_monitors
- Maximum monitor : monitor_limit
- Monitor status (Monitors) : name, url, type, [keyword], [keyword_value], interval, status (color change with status)
- Responste time : Minimum (min), maximum (max), average (avg) and current
- public status page (psp)

## Grafana / Prometheus

1. Deploy exporter
2. Add target in prometheus
3. Add prometheus Data source in grafana
4. Import Grafana dashboard (import json or ID 9955)
   Enjoy !!!

## Docs

Forked from https://github.com/hnrd/uptimerobot_exporter.git
