# Simple TCP/IP Test Driver

`test_driver.py` provides utility features to create test program that manipulates TCP/IP server programs.

[Tera Term]:https://teratermproject.github.io/
In the case of Japan, [Tera Term] is widely used as environment for this purpose, but it can not be used for the test cases that needs to control multiple servers.

The `test_driver.py` will provide similar scripting utilities as Tera Term Macro for multiple connection use cases.

## Basic Usage with Sample Code

Following code can be used to demonstrate HTTP GET operation.
```python
from test_driver import TestTarget

# Create test target for local HTTP host.
target = TestTarget(hostname='localhost', port=8080) 

# The 'start()' method initiates client connection and
# starts receiver thread that dumps received string via a Logger.
if target.start():
    # Send HTTP request.
    target.send(b'GET / HTTP/1.1\r\n\r\n')
    target.sleep(2)
    target.close()
```
