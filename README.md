# uptimerobot.com prometheus exporter 

![Grafana Dashboard](dashboards/dashboard.PNG?raw=true "Grafana Dashboard")

Exports all your uptimerobot.com checks for prometheus scraping,
so you can use external, third-party checks in your monitoring setup.

If you do not have a pro account, any scrape interval shorter than
`scrape_interval: 5m` for this exporter will a) produce duplicated data
and b) misuse uptimerobots API.

## Requirements

* Python
* [requests](http://www.python-requests.org/en/master/)

## Running

Accepted parameters:

* api_key: Your uptimerobot.com API key. See section 'API Settings' in [your account details](https://uptimerobot.com/dashboard#mySettings).
* server_name (optional): Name to bind the HTTP server to. Default: 0.0.0.0
* server_port (optional): Port to bind the HTTP server to. Default: 9705

You can either pass script arguments (run `python exporter.py -h` for an explanation)
or set the following environment variables:

* `UPTIMEROBOT_API_KEY`
* `UPTIMEROBOT_SERVER_NAME`
* `UPTIMEROBOT_SERVER_PORT`

## Docker

```bash
docker run -d --name uptimerobot_exporter -e 'UPTIMEROBOT_API_KEY=your_uptime_robot_api_key' -p 9705:9705 --read-only lekpamartin/uptimerobot_exporter
```

## docker-compose

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


## Docs
Forked from https://github.com/hnrd/uptimerobot_exporter.git
