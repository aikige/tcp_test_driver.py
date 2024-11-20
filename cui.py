#!/usr/bin/env python3
################################################################################
# Simple CUI implemented by TestTarget.
################################################################################

from test_driver import StandardLogger, TcpClientConnector, TestTarget
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('-p', '--port', type=int, default=8080)
parser.add_argument('-n', '--hostname', type=str, default='localhost')
args = parser.parse_args()

c = TcpClientConnector(hostname=args.hostname, port=args.port)
with StandardLogger('log/cui') as l, TestTarget(connector=c, logger=l) as target:
    while True:
        line = input('cui> ')
        if len(line) > 0:
            target.send_str(line + '\n')
