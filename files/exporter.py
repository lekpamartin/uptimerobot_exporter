# FROM https://github.com/hnrd/uptimerobot_exporter/blob/master/exporter.py
# Updated by Martin LEKPA

import argparse
import http.server
import os


import requests


def _escape_strings(data: dict):
    """
    Escape a give string with quotes with a single backslash regarding to the prometheus format description
    https://github.com/prometheus/docs/blob/main/content/docs/instrumenting/exposition_formats.md#text-format-details

    From the docs:
    label_value can be any sequence of UTF-8 characters, but the backslash (\\), double-quote ("), and line feed (\n)
    characters have to be escaped as \\, \", and \n, respectively.

    :param data: python dictionary containing strings
    :return: dict which contains strings with correctly escaped quotes
    """
    translate_map = str.maketrans({
        "\\": "\\\\",
        '"': '\\"',
        "\n":  "\\n",
    })

    escape_dict = data
    for key in escape_dict:
        if type(escape_dict.get(key)) is str:
            escape_dict[key] = escape_dict[key].translate(translate_map)
    return escape_dict


# Monitors
def _fetch_paginated(offset, api_key):
    params = {
        'api_key': api_key,
        'format': 'json',
        'response_times': 1,
        'response_times_limit': 1,
        'offset': offset,
    }

    return requests.post(
        'https://api.uptimerobot.com/v2/getMonitors',
        data=params,
    ).json()


def fetch_data(api_key):
    monitors = {'monitors': []}
    offset = 0
    response = _fetch_paginated(offset, api_key)
    for monitor in response['monitors']:
        monitors['monitors'].append(_escape_strings(monitor))

    while response['monitors']:
        offset = offset + 50
        response = _fetch_paginated(offset, api_key)
        for monitor in response['monitors']:
            monitors['monitors'].append(_escape_strings(monitor))
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

        result += f'uptimerobot_status{{c1_name="{item.get("friendly_name")}",c2_url="{item.get("url")}"' \
                  f',c3_type="{item.get("type")}",c4_sub_type="{item.get("sub_type")}",' \
                  f'c5_keyword_type="{item.get("keyword_type")}",c6_keyword_value="{item.get("keyword_value")}",' \
                  f'c7_http_username="{item.get("http_username")}",c8_port="{item.get("port")}",' \
                  f'c9_interval="{item.get("interval")}"}} {value}\n'

        if item.get('status', 0) == 2 and item.get('response_times'):
            result += f'uptimerobot_response_time{{name="{item.get("friendly_name")}",type="{item.get("type")}",' \
                      f'url="{item.get("url")}"}} {item.get("response_times").pop().get("value")}\n'

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
    result = f'uptimerobot_accountdetails{{name="{data["email"]}",monitor_limit="{data["monitor_limit"]}",' \
             f'monitor_interval="{data["monitor_interval"]}",up_monitors="{data["up_monitors"]}",' \
             f'down_monitors="{data["down_monitors"]}",paused_monitors="{data["paused_monitors"]}"}} 1\n'

    return result


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
        result += f'uptimerobot_psp{{c1_name="{item.get("friendly_name")}",c2_custom_url="{item.get("custom_url")}",' \
                  f'c3_standard_url="{item.get("standard_url")}",c4_monitors="{item.get("monitors")}",' \
                  f'c5_sort="{item.get("sort")}"}} {item.get("status")}\n'
    return result


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
