#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from argparse import ArgumentParser,FileType
from os.path import expanduser
from pprint import pprint
import json
import sys

# python 2 or 3 comparability(tested with 2.6 and 3.6)
try:
    from urllib2 import urlopen, Request, URLError, HTTPError, HTTPErrorProcessor, build_opener, quote
except ImportError:
    from urllib.request import urlopen, Request, URLError, HTTPError, HTTPErrorProcessor, build_opener, quote


# For colorize terminal output
class Bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# This class needs for correct processing HTTP-redirects
class MyHTTPErrorProcessor(HTTPErrorProcessor):

    def http_response(self, request, response):
        code, msg, hdrs = response.code, response.msg, response.info()

        # only add this line to stop 302 redirection.
        if code == 302: return response

        if not (200 <= code < 300):
            response = self.parent.error(
                'http', request, response, code, msg, hdrs)
        return response

    https_response = http_response


def _get_connect_info(args):
    if args.token and args.url:
        return args.token, args.url

    params = []

    tokenfile = expanduser('~') + "/.fpntoken"
    try:
        with open(tokenfile, 'r') as file:
            for line in file:
                params.append(line.split('='))
    except Exception as e:
        print("Cannot open file ~/.fpntoken. %s" % e)
        print("Please, provide credentials as ARGS --token and --url")
        print("Or pun it into ~/.fpntoken like that")
        print("TOKEN=blablablablalba")
        print("URL=http://netbox.loc/")
        exit(1)

    res = dict(params)
    return res.get('TOKEN').rstrip(), res.get('URL').rstrip()


def _get_cmd_list(args):
    print(Bcolors.HEADER + "Getting command list from server..." + Bcolors.ENDC)

    send_data = {"action": "get_help"}
    url = 'api/collector/'

    result = json.loads(_send_request(args, url, send_data))

    if result['result']:
        cmd = result['detail']
        for key in cmd:
            print('Command: %s%s%s' % (Bcolors.BOLD, key, Bcolors.ENDC))
            print("\t%s" % (cmd[key]))

    sys.exit(0)


def _sync_device(args):
    print(Bcolors.HEADER + "Will sync device" + Bcolors.ENDC)

    url = 'api/collector/'

    send_data = {'action': 'sync',
                            'data': [
                                {'hostname': args.hostname, 'command': args.commandname, 'data': args.data.read()}
                            ]}

    result = json.loads(_send_request(args, url, send_data))

    print(Bcolors.BOLD + "Result: " + Bcolors.ENDC + "%s" % result['result'])
    print(Bcolors.BOLD + "Reason: " + Bcolors.ENDC + "%s" % result['detail'])

    if not result['result']:
        exit(1)


def _list_api(args):
    print(Bcolors.HEADER + "Will get info from API" + Bcolors.ENDC)
    url = 'api/'
    if args.field:
        for item in args.field:
            url += item + '/'
        print(Bcolors.BOLD + "API URL: " + Bcolors.ENDC + "%s\n" % url)
    result = json.loads(_send_request(args,url))

    if not result.get('results'):
        for key in result.keys():
            print(key)
    else:
        content = result.get('results')
        for item in content:
            for key in item.keys():
                print("%s\t\t%s" % (key, item[key]))


def _search_api(args):
    if not args.query:
        print("Nothing to search")
        exit(0)
    url = 'api/dcim/devices/?q=%s&limit=0' % quote(args.query)
    output = json.loads(_send_request(args, url))

    if not output.get('results'):
        for key in output.keys():
            print(key)
    else:
        result = output['results']
        _out_result(result)


def _add_args():
    """
    Init command-line args
    """
    parser = ArgumentParser()
    parser.add_argument('-t', '--token', action='store', help="Token auth string")
    parser.add_argument('-u', '--url', action='store', help="Netbox main URL (with ending /)")

    # Sync
    subparsers = parser.add_subparsers()
    sync_parser = subparsers.add_parser('sync',
                                        help='Syncing a one device')
    sync_parser.add_argument('hostname', action='store',
                             help='Host in netbox, which need to be syncing')
    sync_parser.add_argument('commandname', action='store',
                             help='Command, which contain information about a device.')
    sync_parser.add_argument('data', nargs='?', type=FileType('r'),
                             default=sys.stdin, help="Output of command")
    sync_parser.set_defaults(func=_sync_device)

    # List
    list_parser = subparsers.add_parser('ls',
                                        help='List netbox API content')
    list_parser.add_argument('field', nargs='*',
                             help='List API fields')
    list_parser.set_defaults(func=_list_api)

    # Multy-sync
    mulsync_parser = subparsers.add_parser('mulsync',
                                           help='Syncing a multiple device')
    mulsync_parser.add_argument('data', nargs='?', type=FileType('r'),
                                default=sys.stdin, help="Json data, contains a host,command, data values")
    mulsync_parser.add_argument('-f', '--filter', action='store', help='Filter string')

    # Search
    search_parser = subparsers.add_parser('search',
                                         help='Find a device by name, id, asset_tag, etc')
    search_parser.add_argument('query',
                               help="String, what you want to search")
    search_parser.set_defaults(func=_search_api)

    # CMDList
    commands_parser = subparsers.add_parser('cmd_list', help='Get a list of all available commands from server')
    commands_parser.set_defaults(func=_get_cmd_list)

    args = parser.parse_args()
    return args


def _send_request(args, url, send_data=None):
    """
    Send request to NetBox server with auth and json
    """

    token, base_url = _get_connect_info(args)
    url = base_url + url

    headers = {"Content-Type": "application/json",
               "Authorization": "Token %s" % token}

    opener = build_opener(MyHTTPErrorProcessor)
    if send_data:
        result_url = Request(url, data=json.dumps(send_data).encode('utf8'), headers=headers)
    else:
        result_url = Request(url, headers=headers)
    try:
        f = opener.open(result_url)
        code = f.getcode()
        if code == 200:
            return f.read().decode('utf-8')
        else:
            print(Bcolors.FAIL + "URL error" + Bcolors.ENDC)
            print(Bcolors.BOLD + "Server return HTTP Code: " + Bcolors.ENDC + "%s" % code)
            exit(1)

    except HTTPError as e:
        print(Bcolors.FAIL + "Connection error" + Bcolors.ENDC)
        print(Bcolors.BOLD + "Code: " + Bcolors.ENDC + "%s" % e.code)
        print(Bcolors.BOLD + "Reason: " + Bcolors.ENDC + "%s" % e.reason)
        if e.code != 404:
            print(Bcolors.BOLD + "Server returns: " + Bcolors.ENDC + "%s" % e.read().decode('utf-8'))
        exit(1)
    except URLError as e:
        print(Bcolors.FAIL + "Connection error" + Bcolors.ENDC)
        print(Bcolors.BOLD + "Reason: " + Bcolors.ENDC + "%s" % e)
        exit(1)


def _out_result(result):
    keys = ['name', 'device_role', 'site', 'rack', 'position', 'asset_tag']

    for item in result:
        print("Item:")
        for key in keys:
            data = item[key]
            if type(data) == dict:
                data = data['name']
            print("\t%s%s%s: %s" % (Bcolors.BOLD, key, Bcolors.ENDC, data))


def main():
    args = _add_args()
    try:
        args.func(args)
    except AttributeError:
        print("Error while processing agr function")
        pass


if __name__ == '__main__':
    main()

