# sprockets-logging
Opinionated logging for Python applications

Features:
- Enable debug logging with the `DEBUG` env var
- Outputs logs in structured `json` or `plain` text format (configurable with the `LOG_FORMAT` environment variable)
- Automatically enables json log ouput when the `ENVRIONMENT` env var is `testing`, `staging`, or `production`
- Support for using [contextvars](https://docs.python.org/3/library/contextvars.html) to include arbitrary data on all log entries

## Environment Variables
| Name         | Accepted Values                                                          | Description                              |
|--------------|--------------------------------------------------------------------------|------------------------------------------|
| `DEBUG`      | `0`, `n`, `no`, `false` to disable<br> `1`, `y`, `yes`, `true` to enable | toggle logging of `debug` level messages |
| `LOG_FORMAT` | `json` for structured JSON<br> `plain` for plain text                     | format to output log messages as         |

## Usage Example
This example demonstrates how contextvars appear with the default plain text log format.

```python
import asyncio
import logging
import logging.config

import sprockets_logging

LOGGER = logging.getLogger('test')


async def first_func():
    sprockets_logging.set_context('func', 'first')
    for i in range(1, 4):
        await asyncio.sleep(i)
        LOGGER.info('first_func iteration %d', i)


async def second_func():
    sprockets_logging.set_context('func', 'second')
    sprockets_logging.set_context('something', 'else')
    for i in range(1, 4):
        await asyncio.sleep(i)
        LOGGER.info('second_func iteration %d', i)


async def main():
    logging.config.dictConfig(sprockets_logging.config())
    sprockets_logging.set_context('func', 'main')
    LOGGER.info('start')
    await asyncio.gather(first_func(), second_func())
    LOGGER.info('end')


if __name__ == '__main__':
    asyncio.run(main())
```

**Output:**
```
2022-03-16 20:09:18,965 INFO     test start [func main]
2022-03-16 20:09:19,968 INFO     test first_func iteration 1 [func first]
2022-03-16 20:09:19,968 INFO     test second_func iteration 1 [func second] [something else]
2022-03-16 20:09:21,970 INFO     test first_func iteration 2 [func first]
2022-03-16 20:09:21,971 INFO     test second_func iteration 2 [func second] [something else]
2022-03-16 20:09:24,973 INFO     test first_func iteration 3 [func first]
2022-03-16 20:09:24,973 INFO     test second_func iteration 3 [func second] [something else]
2022-03-16 20:09:24,973 INFO     test end [func main]
```
