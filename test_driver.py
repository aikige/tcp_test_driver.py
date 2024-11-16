#!/usr/bin/env python3
import socket
import threading
import datetime
import time

class TestLogger:
    def write(self, message, info: str = ''):
        if message[-1] not in '\r\n':
            message += '\n'
        print(message, end='')

class StandardLogger(TestLogger):
    def __init__(self, filename: str = 'test', timestamp: bool = True):
        if timestamp:
            filename = filename + datetime.datetime.now().strftime('_%Y%m%d%H%M%S.log')
        self.file = open(filename, mode='w')

    def write(self, message, info: str = ''):
        if message[-1] not in '\r\n':
            message += '\n'
        message = f"{str(time.time_ns())}:{info}:{message}"
        print(message, end='')
        self.file.write(message)

    def close(self):
        self.file.close()

class TestTarget:
    RECV_UNIT = 4096
    def __init__(self, id='', hostname='127.0.0.1', port=8000, logger=TestLogger()):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rx_buffer = []
        self.wait_targets = []
        self.event = threading.Event()
        self.id = id
        self.hostname = hostname
        self.port = port
        self.thread = threading.Thread(target=self.receiver, daemon=True)
        self.logger = logger
        self.found_str = None

    def start(self) -> bool:
        print("start")
        try:
            self.socket.connect((self.hostname, self.port))
        except socket.error as e:
            self.log(str(e), f"ER:{self.id}")
            return False
        self.active = True
        self.thread.start()
        return True

    def log(self, message: str, info: str = ''):
        self.logger.write(message, info)

    def receiver(self):
        while self.active:
            try:
                line = self.socket.recv(self.RECV_UNIT).decode()
            except socket.error as e:
                if self.active:
                    self.log(f"{str(e)}", f"ER:{self.id}")
                break
            self.rx_buffer.append(line)
            self.log(line, f"RX:{self.id}")
            for target in self.wait_targets:
                if target in line:
                    self.found_str = line
                    self.event.set()
                    break

    def send_str(self, message: str):
        self.log(message, f"TX:{self.id}")
        self.socket.send(message.encode())

    def send(self, message: bytes):
        self.log(message.decode(), f"TX:{self.id}")
        self.socket.send(message)

    def find_str_in_rx(self, target: str, count: int = 1) -> int:
        for line in self.rx_buffer:
            if target in line:
                count -= 1
                if count == 0:
                    self.found_str = line
                    break
        return count

    def wait_str(self, target: str, count: int = 1, timeout=None) -> bool:
        count = self.find_str_in_rx(target, count)
        self.wait_targets.append(target)
        while count > 0:
            result = self.event.wait(timeout)
            if not result:
                return False
            count -= 1
        return True

    def flush_rx(self):
        self.rx_buffer = []

    def stop(self):
        if self.active:
            self.active = False
            self.socket.close()
            self.rx_buffer = []
            self.event.set()
            #self.thread.join()

    def sleep(self, duration):
        time.sleep(duration)

if __name__ == '__main__':
    import sys
    port = 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    logger = StandardLogger()
    target = TestTarget(port=port, logger=logger)
    if target.start():
        message = b'GET / HTTP/1.1\r\n'
        message += b'\r\n'
        target.send(message)
        if target.wait_str('OK', timeout=2):
            target.sleep(2)
            target.log('Found:' + target.found_str)
        else:
            target.log('Failed')
        target.stop()
