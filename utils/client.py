#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO: test https connection

import json
import sys
import os
# python 2 or 3 compatability
try:
    from httplib import HTTPConnection
except ModuleNotFoundError:
    from http.client import HTTPConnection

TOKEN='tokentokentokentokentokentokentoken'
URL='localhost:8000'


def sendRequest(hostname, command, result, vendor='Linux'):
    ''' Send request to collector
        may be will need use a urllib and not hardcode
        a 'collector/' URL
    '''
    headers = {"Content-Type": "appliction/json",
                "Authorization": "Token %s" % TOKEN}

    sendData = {"Hostname": hostname,
                "Command": command,
                "Data": result
                }
    try:
        conn = HTTPConnection(URL)
        conn.request('POST','/collector/', json.dumps(sendData), headers)
        response = conn.getresponse()
        # print(response.status, response.reason)
        return response.read().decode()
    except Exception as e:
        print("Error while connect: %s" % e)
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage %s <hostname> <command>" % os.path.basename(__file__))
        print("This will be read from standart input and sent it to server")
        return
    
    hostname = sys.argv[1]
    command = sys.argv[2]
    result = sys.stdin.read()

    # print(result)

    result = sendRequest(hostname, command, result)
    print(result)

if __name__ == '__main__':
    main()
