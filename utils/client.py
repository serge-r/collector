#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO: test https connection
from __future__ import unicode_literals
import json
import sys
import os

# python 2 or 3 compatability(test with 2.6 and 3.6)
try:
    from urllib2 import urlopen, Request, URLError, HTTPError
except:
    from urllib.request import urlopen, Request, URLError, HTTPError

TOKEN='toketokentokentokentokentokne'
URL='http://localhost:8000/api/collector/'


def sendRequest(hostname, command, result):
    '''
    Send request to NetBox server with auth and json
    '''
    headers = {"Content-Type": "application/json",
                "Authorization": "Token %s" % TOKEN}

    sendData = {"Hostname": hostname,
                "Command": command,
                "Data": result
                }
    
    url = Request(URL, data=json.dumps(sendData).encode('utf8'),  headers=headers) #, method='POST')
    try:
        f = urlopen(url)
        return (f.read().decode('utf-8'))
    except HTTPError as e:
        # print(e.code)
        # print(e.reason)
        return (e.read().decode('utf-8'))
    except URLError as e:
        result = json.dumps({"result": False, "detail": "Cannot connect: %s" % e.reason})
        return result


def main():
    if len(sys.argv) < 3:
        print("Usage %s <hostname> <command>" % os.path.basename(__file__))
        print("This will be read from standart input and sent it to server")
        return
    
    hostname = sys.argv[1]
    command = sys.argv[2]
    result = sys.stdin.read()

    result = sendRequest(hostname, command, result)
    print(result)


if __name__ == '__main__':
    main()

