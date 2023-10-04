# FROM https://github.com/hnrd/uptimerobot_exporter/blob/master/exporter.py
# Updated by Martin LEKPA

import argparse
import http.server
import os


import requests





## Monitors
def _fetch_paginated(offset, api_key):
    params = {
        'api_key': api_key,
        'format': 'json',
        'response_times': 1,
        'response_times_limit': 1,
        'custom_uptime_ratios': "1-7-30",
        'offset': offset,
    }
    return requests.post(
        'https://api.uptimerobot.com/v2/getMonitors',
        data=params,
    ).json()

def fetch_data(api_key):
    monitors = {'monitors':[]}
    offset = 0
    response = _fetch_paginated(offset, api_key)
    for monitor in response['monitors']:
        monitors['monitors'].append(monitor)

    while response['monitors']:
        offset = offset + 50
        response = _fetch_paginated(offset, api_key)
        for monitor in response['monitors']:
            monitors['monitors'].append(monitor)
    return monitors

def format_prometheus(data):
    result = ''
    for item in data:
        if item.get('status') == 0:
           value = 2
        elif item.get('status') == 1:
           value = 1
        elif item.get('status') == 2:
           value = 0
        else:
           value = 3
        result += 'uptimerobot_status{{c1_name="{}",c2_url="{}",c3_type="{}",c4_sub_type="{}",c5_keyword_type="{}",c6_keyword_value="{}",c7_http_username="{}",c8_port="{}",c9_interval="{}"}} {}\n'.format(
            item.get('friendly_name'),
            item.get('url'),
            item.get('type'),
            item.get('sub_type'),
            item.get('keyword_type'),
            item.get('keyword_value'),
            item.get('http_username'),
            item.get('port'),
            item.get('interval'),
            value,
        )
        if item.get('status', 0) == 2 and item.get('response_times'):
            result += 'uptimerobot_response_time{{name="{}",type="{}",url="{}"}} {}\n'.format(
                item.get('friendly_name'),
                item.get('type'),
                item.get('url'),
                item.get('response_times').pop().get('value'),
            )

        uptimes = item.get('custom_uptime_ratio').split('-')
        result += format_prometheus_uptime(item, 1, uptimes[0])
        result += format_prometheus_uptime(item, 7, uptimes[1])
        result += format_prometheus_uptime(item, 30, uptimes[2])
    return result

def format_prometheus_uptime(item, days, uptime):
    result = 'uptimerobot_uptime{{c1_name="{}",c2_url="{}",c3_type="{}",c4_sub_type="{}",c5_keyword_type="{}",c6_keyword_value="{}",c7_http_username="{}",c8_port="{}",c9_interval="{}",c10_days="{}"}} {}\n'.format(
        item.get('friendly_name'),
        item.get('url'),
        item.get('type'),
        item.get('sub_type'),
        item.get('keyword_type'),
        item.get('keyword_value'),
        item.get('http_username'),
        item.get('port'),
        item.get('interval'),
        days,
        float(uptime),
    )
    return result



## getAccountDetails
def fetch_accountdetails(api_key):
    params = {
        'api_key': api_key,
        'format': 'json',
    }
    req = requests.post(
        'https://api.uptimerobot.com/v2/getAccountDetails',
        data=params,
    )
    return req.json()


def format_prometheus_accountdetails(data):
    result = 'uptimerobot_accountdetails{name="%s",monitor_limit="%s",monitor_interval="%s",up_monitors="%s",down_monitors="%s",paused_monitors="%s"} 1\n' %(data['email'],data['monitor_limit'],data['monitor_interval'],data['up_monitors'],data['down_monitors'],data['paused_monitors'])
    return result

## End



## public status pages
def fetch_psp(api_key):
    params = {
        'api_key': api_key,
        'format': 'json',
    }
    req = requests.post(
        'https://api.uptimerobot.com/v2/getPSPs',
        data=params,
    )
    return req.json()


def format_prometheus_psp(data):
  result = ''
  for item in data:
    result += 'uptimerobot_psp{{c1_name="{}",c2_custom_url="{}",c3_standard_url="{}",c4_monitors="{}",c5_sort="{}"}} {}\n'.format(item.get('friendly_name'),item.get('custom_url'),item.get('standard_url'),item.get('monitors'),item.get('sort'),item.get('status'))
  return result

## End






class ReqHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        answer = fetch_data(api_key)
        accountdetails = fetch_accountdetails(api_key)
        psp = fetch_psp(api_key)
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(
            format_prometheus(answer.get('monitors')).encode('utf-8')
        )
        self.wfile.write(
            format_prometheus_accountdetails(accountdetails.get('account')).encode('utf-8')
        )
        self.wfile.write(
            format_prometheus_psp(psp.get('psps')).encode('utf-8')
        )


if __name__ == '__main__':
    if 'UPTIMEROBOT_API_KEY' in os.environ:
        api_key = os.environ.get('UPTIMEROBOT_API_KEY')
        server_name = os.environ.get('UPTIMEROBOT_SERVER_NAME', '0.0.0.0')
        server_port = int(os.environ.get('UPTIMEROBOT_SERVER_PORT', '9705'))
    else:
        parser = argparse.ArgumentParser(
            description='Export all check results from uptimerobot.txt'
                        'for prometheus scraping.'
        )
        parser.add_argument(
            'apikey',
            help='Your uptimerobot.com API key. See account details.'
        )
        parser.add_argument(
            '--server_name', '-s',
            default='0.0.0.0',
            help='Server address to bind to.'
        )
        parser.add_argument(
            '--server_port', '-p',
            default=9705,
            type=int,
            help='Port to bind to.'
        )
        args = parser.parse_args()
        api_key = args.apikey
        server_name = args.server_name
        server_port = args.server_port

    httpd = http.server.HTTPServer((server_name, server_port), ReqHandler)
    httpd.serve_forever()
