#!/usr/bin/env python3
"""
This module implements TestTarget class that can be used to test TCP/IP services.
"""
import socket
import threading
import datetime
import time

class TestLogger:
    """ The default and minumum Logger for TestTarget. """
    def write(self, message: str, info: str = ''):
        """ Write logging.

        Args:
            message str: string to be logged.
            info str: supplemental information for loggin.
        """
        if len(message) == 0:
            message = '\n'
        elif message[-1] not in '\r\n':
            message += '\n'
        print(message, end='')

class StandardLogger(TestLogger):
    """ The Logger that stores logs into file with timestamp. """
    def __init__(self, filename: str = 'test', timestamp: bool = True):
        if timestamp:
            filename = filename + datetime.datetime.now().strftime('_%Y%m%d%H%M%S')
        filename += '.log'
        self.file = open(filename, mode='w', encoding='utf-8')

    def write(self, message, info: str = ''):
        """ Write log message to standard output and file. """
        if len(message) == 0:
            message = '\n'
        elif message[-1] not in '\r\n':
            message += '\n'
        message = f"{str(time.time_ns())}:{info}:{message}"
        print(message, end='')
        self.file.write(message)

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None

    def __del__(self):
        self.close()

class TargetConnector:
    """ Interface definition for TargetConnector. """
    def __init__(self, logger=None):
        self.logger = logger
    def log(self, message, info):
        if isinstance(self.logger, TestLogger):
            self.logger.write(message, info)
    def open(self) -> bool:
        return True
    def recv_str(self) -> str|None:
        return None
    def send_str(self, message: str):
        pass
    def send(self, message: bytes):
        pass
    def close(self):
        pass

class TargetConnectorTCP(TargetConnector):
    RECV_UNIT = 4096
    def __init__(self, hostname='127.0.0.1', port=8080, logger=None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.hostname = hostname
        self.port = port
        self.logger = logger
        self.connected = False
        super().__init__(logger)

    def open(self) -> bool:
        try:
            self.socket.connect((self.hostname, self.port))
        except socket.error as e:
            self.log(str(e), 'ER:tcp')
            return False
        return True

    def recv_str(self) -> str|None:
        try:
            return self.socket.recv(self.RECV_UNIT).decode()
        except socket.error as e:
            if self.connected:
                self.log(str(e), 'ER:tcp')
            return None

    def send_str(self, message: str):
        try:
            self.socket.send(message.encode())
        except socket.error as e:
            if self.connected:
                self.log(str(e), 'ER:tcp')

    def send(self, message: bytes):
        try:
            self.socket.send(message)
        except socket.error as e:
            if self.connected:
                self.log(str(e), 'ER:tcp')

    def close(self):
        self.connected = False
        self.socket.close()

class TestTarget:
    def __init__(self, name='', connector=TargetConnectorTCP(), logger=TestLogger()):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rx_buffer = []
        self.wait_strings = []
        self.name = name
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.receiver, daemon=True)
        self.logger = logger
        self.found_str = None
        self.active = False
        self.connector = connector
        self.connector.logger = logger
        # Option for internal behaviors.
        self.flush_before_wait = False  # When this attribute is True, force flush_rx before wait string(s).
        self.split_lines = False        # When this attribute is True, split received data into lines.

    def start(self) -> bool:
        """ Start receiver thread. """
        self.log('start receiver', f"--:{self.name}")
        if not self.connector.open():
            self.log('failed to connect', f"ER:{self.name}")
            return False
        self.active = True
        self.thread.start()
        return True

    def log(self, message: str, info: str = ''):
        """ Write message to logger. """
        self.lock.acquire()
        self.logger.write(message, info)
        self.lock.release()

    def receiver(self):
        while self.active:
            data = self.connector.recv_str()
            if data is None:
                if self.active:
                    self.log('failed to receive', f"ER:{self.name}")
                break
            self.log(data, f"RX:{self.name}")
            if self.split_lines:
                for line in data.splitlines():
                    self.rx_buffer.append(line)
            else:
                self.rx_buffer.append(data)
            for string in self.wait_strings:
                if string in data:
                    self.found_str = data
                    self.event.set()
                    break
        self.log('receiver stopped', f"--:{self.name}")

    def send(self, message: bytes):
        """ Send byte-stream to socket (with log). """
        self.log(message.decode(), f"TX:{self.name}")
        self.connector.send(message)

    def send_str(self, message: str):
        """ Send string to socket (with log). """
        self.log(message, f"TX:{self.name}")
        self.connector.send_str(message)

    def find_str(self, string: str, count: int = 1) -> int:
        self.found_str = None
        for line in self.rx_buffer:
            if string in line:
                count -= 1
                if count == 0:
                    self.found_str = line
                    break
        return count

    def find_multi_str(self, strings: list) -> bool:
        for line in self.rx_buffer:
            for string in strings:
                if string in line:
                    self.found_str = line
                    return True
        return False

    def wait_str(self, string: str, count: int = 1, timeout=None) -> bool:
        if self.flush_before_wait:
            self.flush_rx()
        count = self.find_str(string, count)
        self.event.clear()
        self.wait_strings.append(string)
        while count > 0 and self.active:
            result = self.event.wait(timeout)
            if not result:
                result = False
                break
            count -= 1
        self.wait_strings = []
        return result

    def wait_multi_str(self, strings: list, timeout=None) -> bool:
        if self.flush_before_wait:
            self.flush_rx()
        elif self.find_multi_str(strings):
            return True
        self.event.clear()
        self.wait_strings = strings
        result = self.event.wait(timeout)
        self.wait_strings = []
        return result

    def flush_rx(self):
        self.rx_buffer = []

    def stop(self):
        """ Stops running receiver. """
        if self.active:
            self.active = False
            self.connector.close()
            self.rx_buffer = []
            self.event.set()
            #self.thread.join()

    def sleep(self, duration):
        time.sleep(duration)

if __name__ == '__main__':
    l = StandardLogger()
    c = TargetConnectorTCP(hostname='www.google.com', port=80)
    target = TestTarget(connector=c, logger=l)
    if target.start():
        target.send_str('GET / HTTP/1.1\r\n\r\n')
        if target.wait_str('</html>', timeout=2):
            target.sleep(0.1)
            target.log('=== Success (1) ===')
        else:
            target.log('=== Fail ===')
        target.split_lines = True
        target.flush_before_wait = True
        target.send_str('GET /search HTTP/1.1\r\n\r\n')
        if target.wait_multi_str(['</html>', '</HTML>'], timeout=2):
            target.log('=== Success (2) ===')
            target.find_multi_str(['</html>', '</HTML>'])
            target.log('--- Found:' + target.found_str)
        else:
            target.log('=== Fail ===')
        target.stop()
    else:
        target.log('=== Connection Failed ===')
