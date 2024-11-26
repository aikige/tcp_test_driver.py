#!/usr/bin/env python3
################################################################################
# Simple CUI implemented by TestTarget.
################################################################################

from test_driver import StandardLogger, TcpClientConnector, TestTarget
from argparse import ArgumentParser

parser = ArgumentParser()
h = 'hostname for TCP connection'
parser.add_argument('-n', '--hostname', type=str, default='localhost', help=h)
h = 'TCP port number for TCP connection'
parser.add_argument('-p', '--port', type=int, default=8080, help=h)
h = 'when this option is set, script uses CR+LF as new line, otherwise uses LF'
parser.add_argument('-c', '--crlf', action='store_true', help=h)
h = 'when this option is set, script ignores blank line'  
parser.add_argument('-i', '--ignore-blank', action='store_true', help=h)
args = parser.parse_args()

if args.crlf:
    newline = '\r\n'
else:
    newline = '\n'
c = TcpClientConnector(hostname=args.hostname, port=args.port)
with StandardLogger('log/cui') as l, TestTarget(connector=c, logger=l) as target:
    while True:
        line = input('cui> ')
        if args.ignore_blank and len(line) == 0:
            continue
        target.send_str(line + newline)
