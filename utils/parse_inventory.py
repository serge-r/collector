#!/usr/bin/env python

import sys
import clitable
from pprint import pprint

input_file = sys.stdin.read()

cli_table = clitable.CliTable('index', '../cli_templates')

attributes = {'Command': sys.argv[1]}
print(attributes)

cli_table.ParseCmd(input_file, attributes)
keys = cli_table.header.values

# print(cli_table)

result = [dict(zip(keys,row)) for row in cli_table]

pprint(result)
print("Count: {}".format(len(result)))
