# FROM https://github.com/hnrd/uptimerobot_exporter/blob/master/exporter.py
# Updated by Martin LEKPA

import argparse
import http.server
import os


import requests


def fetch_data(api_key):
    params = {
        'api_key': api_key,
        'format': 'json',
        'response_times': 1,
        'response_times_limit': 1,
    }
    req = requests.post(
        'https://api.uptimerobot.com/v2/getMonitors',
        data=params,
    )
    return req.json()

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


def format_prometheus(data):
    result = ''
    for item in data:
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
            0 if item.get('status', 0) == 2 else 1,
        )
        if item.get('status', 0) == 2:
            result += 'uptimerobot_response_time{{name="{}",type="{}",url="{}"}} {}\n'.format(
                item.get('friendly_name'),
                item.get('type'),
                item.get('url'),
                item.get('response_times').pop().get('value'),
            )
    return result


class ReqHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        answer = fetch_data(api_key)
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(
            format_prometheus(answer.get('monitors')).encode('utf-8')
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
