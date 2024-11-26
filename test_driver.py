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
    def write(self, message: str, info: str):
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

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

class StandardLogger(TestLogger):
    """ The Logger that stores logs into file with timestamp. """
    def __init__(self, filename: str = 'test', timestamp: bool = True):
        if timestamp:
            filename = filename + datetime.datetime.now().strftime('_%Y%m%d%H%M%S')
        filename += '.log'
        self.file = open(filename, mode='w', encoding='utf-8')
        self.lock = threading.Lock()

    def write(self, message, info: str = ''):
        """ Write log message to standard output and file. """
        if len(message) == 0:
            message = '\n'
        elif message[-1] not in '\r\n':
            message += '\n'
        message = f"{str(time.time_ns())}:{info}:{message}"
        with self.lock:
            print(message, end='')
            self.file.write(message)

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None

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

class TcpClientConnector(TargetConnector):
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
    class Logger:
        def __init__(self, name, logger):
            self.logger = logger
            self.name = name
        def write(self, message: str, info: str):
            info += ':' + self.name
            self.logger.write(message, info)

    def __init__(self, name='', connector=TcpClientConnector(), logger=TestLogger()):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger = self.Logger(name, logger)
        self.rx_buffer = []
        self.wait_strings = []
        self.semaphore = threading.Semaphore(0)
        self.thread = threading.Thread(target=self.receiver, daemon=True)
        self.found_str = None
        self.active = False
        self.connector = connector
        self.connector.logger = logger
        # When flush_before_wait attribute is True, force flush_rx before wait string(s).
        self.flush_before_wait = False
        # When split_lines attribute is True, split received data into lines.
        self.split_lines = False

    def __enter__(self):
        if not self.start():
            raise RuntimeError('Failed to start TestTarget')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        return False

    def start(self) -> bool:
        """ Start receiver thread. """
        if not self.connector.open():
            self.log('failed to connect', 'ER')
            return False
        self.active = True
        self.thread.start()
        return True

    def log(self, message: str, info: str = ''):
        """ Write message to logger. """
        self.logger.write(message, info)

    def receiver(self):
        self.log('receiver started', '--')
        while self.active:
            data = self.connector.recv_str()
            if data is None:
                if self.active:
                    self.log('failed to receive', 'ER')
                break
            if self.split_lines:
                lines = data.splitlines()
            else:
                lines = [data]
            if self.wait_strings is None:
                # Waiting any
                self.semaphore.release()
                self.found_str = lines[0]
                self.rx_buffer.extend(lines)
                continue
            for line in lines:
                self.log(line, 'RX')
                self.rx_buffer.append(line)
                for string in self.wait_strings:
                    if string in line:
                        self.found_str = line
                        self.semaphore.release()
                        break
        self.log('receiver stopped', '--')

    def send(self, message: bytes):
        """ Send byte-stream to socket (with log). """
        self.log(message.decode(), 'TX')
        self.connector.send(message)

    def send_str(self, message: str):
        """ Send string to socket (with log). """
        self.log(message, 'TX')
        self.connector.send_str(message)

    def __find_multi_str(self, strings: list, lines: list):
        self.found_str = None
        for line in lines:
            for string in strings:
                if string in line:
                    self.found_str = line
                    return True
        return False

    def find_str(self, string: str, count: int = 1) -> int:
        self.found_str = None
        for line in self.rx_buffer:
            if string in line:
                count -= 1
                if count == 0:
                    self.found_str = line
                    break
        return count

    def find_multi_str(self, strings: list, lines: list = None) -> bool:
        return self.__find_multi_str(list, self.rx_buffer)

    def __flush_semaphore(self):
        while self.semaphore.acquire(blocking=False):
            self.log('discard event', 'WR')
            pass

    def wait_any(self, timeout=None):
        if len(self.rx_buffer) > 0:
            self.found_str = self.rx_buffer[0]
            return True
        self.__flush_semaphore()
        self.wait_strings = None
        result = self.semaphore.acquire(timeout=timeout)
        self.wait_strings = []
        return result

    def wait_str(self, string: str, count: int = 1, timeout=None) -> bool:
        if self.flush_before_wait:
            self.flush_rx()
        count = self.find_str(string, count)
        self.__flush_semaphore()    # for safe.
        self.wait_strings.append(string)
        while count > 0 and self.active:
            result = self.semaphore.acquire(timeout=timeout)
            if not result:
                result = False
                break
            count -= 1
        self.wait_strings = []
        return result

    def wait_multi_str(self, strings: list, timeout=None) -> bool:
        if self.flush_before_wait:
            self.flush_rx()
        elif self.__find_multi_str(strings, self.rx_buffer):
            return True
        self.__flush_semaphore()    # for safe.
        self.wait_strings = strings
        result = self.semaphore.acquire(timeout=timeout)
        self.wait_strings = []
        return result

    def flush_rx(self):
        self.rx_buffer = []

    def stop(self):
        """ Stops running receiver. """
        if self.active:
            self.active = False
            self.connector.close()
            self.thread.join()
            self.rx_buffer = []

    def sleep(self, duration):
        time.sleep(duration)

if __name__ == '__main__':
    ############################################################################
    # Demonstrate API with HTTP request
    ############################################################################
    from argparse import ArgumentParser
    parser = ArgumentParser()
    H = 'hostname for TCP connection'
    parser.add_argument('-n', '--hostname', type=str, default='www.google.com', help=H)
    H = 'port number for TCP connection'
    parser.add_argument('-p', '--port', type=int, default=80, help=H)
    args = parser.parse_args()
    c = TcpClientConnector(hostname=args.hostname, port=args.port)
    with StandardLogger() as l, TestTarget(connector=c, logger=l) as target:
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
            target.log('--- Found:' + target.found_str)
        else:
            target.log('=== Fail ===')
