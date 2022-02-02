import contextlib
import io
import json
import logging
import logging.config
import os
import time
import unittest

import freezegun

import sprockets_logging


class LogTests(unittest.TestCase):

    maxDiff = None

    @staticmethod
    def expected_console_config(level):
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'incremental': False,
            'formatters': {
                'file': {
                    '()': 'sprockets_logging._LogFormatter',
                    'format': ("%(asctime)s %(levelname)-8s "
                               "%(name)s %(message)s")
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                    'level': level,
                    'formatter': 'file',
                },
            },
            'root': {
                'level': level,
                'handlers': ['console']
            }
        }

    @staticmethod
    def expected_jsonscribe_config(level):
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'incremental': False,
            'filters': {
                'defaultsetter': {
                    '()': 'jsonscribe.AttributeSetter',
                },
            },
            'formatters': {
                'jsonlines': {
                    '()': 'sprockets_logging._JSONFormatter',
                    'include_fields': [
                        'name',
                        'levelname',
                        'asctime',
                        'message',
                        'context',
                        'module',
                        'exc_info',
                    ],
                    'use_loggly_names': True,
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                    'filters': ['defaultsetter'],
                    'formatter': 'jsonlines',
                },
            },
            'root': {
                'level': level,
                'handlers': ['console'],
            }
        }

    def test_console_config_with_debug_on(self):
        self.assertEqual(
            sprockets_logging.config(level=logging.DEBUG,
                                     use_jsonscribe=False),
            self.expected_console_config(logging.DEBUG))

    def test_console_config_with_debug_off(self):
        self.assertEqual(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=False),
            self.expected_console_config(logging.INFO))

    def test_jsonscribe_config_with_debug_on(self):
        self.assertEqual(
            sprockets_logging.config(logging.DEBUG, use_jsonscribe=True),
            self.expected_jsonscribe_config(logging.DEBUG))

    def test_jsonscribe_config_with_debug_off(self):
        self.assertEqual(
            sprockets_logging.config(logging.ERROR, use_jsonscribe=True),
            self.expected_jsonscribe_config(logging.ERROR))


@freezegun.freeze_time('2020-01-01')
class ContextTests(unittest.TestCase):

    def setUp(self):
        sprockets_logging._context.clear()
        self.addCleanup(sprockets_logging._context.clear)

    def test_console(self):
        logging.config.dictConfig(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=False))

        # no context
        with record_log_lines() as lines:
            logging.info('abc')
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S,000', time.localtime())
        self.assertEqual(
            lines,
            [f'{timestamp} INFO     root abc'])  # noqa: E501

        # populated context
        sprockets_logging.set_context('key_a', 'value_a')

        # update existing key
        sprockets_logging.set_context('key_b', 'original_b')
        sprockets_logging.set_context('key_b', 'value_b')

        sprockets_logging.set_context('this_is_empty', '')  # not be included
        with record_log_lines() as lines:
            logging.info('abc')

        # roughly mimic how logging sets a record's timestamp
        self.assertEqual(
            lines,
            [f'{timestamp} INFO     root abc [key_a value_a] [key_b value_b]'])  # noqa: E501

    def test_jsonscribe(self):
        logging.config.dictConfig(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=True))

        # no context
        expected = {
            'asctime': '2020-01-01T00:00:00.000000+0000',
            'context': None,
            'excinfo': None,
            'levelname': 'INFO',
            'message': 'abc',
            'module': 'test_log',
            'name': 'root',
        }
        with record_log_lines() as lines:
            logging.info('abc')
        self.assertEqual(
            [json.loads(line) for line in lines],
            [expected])

        # populated context
        sprockets_logging.set_context('key_a', 'value_a')

        # update existing key
        sprockets_logging.set_context('key_b', 'original_b')
        sprockets_logging.set_context('key_b', 'value_b')

        # should be excluded
        sprockets_logging.set_context('this_is_empty', '')
        expected['context'] = {
            'key_a': 'value_a',
            'key_b': 'value_b',
        }
        with record_log_lines() as lines:
            logging.info('abc')
        self.assertEqual(
            [json.loads(line) for line in lines],
            [expected])


@contextlib.contextmanager
def record_log_lines():
    handler = logging.root.handlers[0]
    original_stream = handler.stream
    lines = []
    try:
        new_stream = io.StringIO()
        handler.stream = new_stream
        yield lines
        new_stream.seek(0)
        lines.extend(new_stream.read().splitlines())
    finally:
        handler.stream = original_stream


class EnvVarTests(unittest.TestCase):

    def setUp(self):
        self.addCleanup(self.replace_environ, os.environ.copy())
        for key in 'DEBUG', 'ENVIRONMENT', 'LOG_FORMAT':
            os.environ.pop(key, None)

    @staticmethod
    def replace_environ(env):
        os.environ.clear()
        os.environ.update(env)

    def test_debug_true(self):
        os.environ['DEBUG'] = 'true'
        self.assertEqual(
            sprockets_logging.config(level=logging.DEBUG,
                                     use_jsonscribe=False),
            sprockets_logging.config(use_jsonscribe=False))

    def test_debug_false(self):
        os.environ['DEBUG'] = 'false'
        self.assertEqual(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=False),
            sprockets_logging.config(use_jsonscribe=False))

    def test_environment_development(self):
        os.environ['ENVIRONMENT'] = 'development'
        self.assertEqual(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=False),
            sprockets_logging.config(level=logging.INFO))

    def test_environment_not_development(self):
        for environment in ('testing', 'staging', 'production'):
            os.environ['ENVIRONMENT'] = environment
            self.assertEqual(
                sprockets_logging.config(level=logging.INFO,
                                         use_jsonscribe=True),
                sprockets_logging.config(level=logging.INFO))

    def test_log_format_ignored_when_falsy(self):
        os.environ['LOG_FORMAT'] = ''
        os.environ['ENVIRONMENT'] = 'development'
        self.assertEqual(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=False),
            sprockets_logging.config(level=logging.INFO))
        os.environ['ENVIRONMENT'] = 'production'
        self.assertEqual(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=True),
            sprockets_logging.config(level=logging.INFO))

        os.environ.pop('LOG_FORMAT')
        os.environ['ENVIRONMENT'] = 'development'
        self.assertEqual(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=False),
            sprockets_logging.config(level=logging.INFO))
        os.environ['ENVIRONMENT'] = 'production'
        self.assertEqual(
            sprockets_logging.config(level=logging.INFO, use_jsonscribe=True),
            sprockets_logging.config(level=logging.INFO))

    def test_log_format_plain(self):
        os.environ['LOG_FORMAT'] = 'plain'
        for value in ('development', 'testing', 'staging', 'production'):
            os.environ['ENVIRONMENT'] = value
            self.assertEqual(
                sprockets_logging.config(level=logging.INFO,
                                         use_jsonscribe=False),
                sprockets_logging.config(level=logging.INFO))

    def test_log_format_json(self):
        os.environ['LOG_FORMAT'] = 'json'
        for value in ('development', 'testing', 'staging', 'production'):
            os.environ['ENVIRONMENT'] = value
            self.assertEqual(
                sprockets_logging.config(level=logging.INFO,
                                         use_jsonscribe=True),
                sprockets_logging.config(level=logging.INFO))

    def test_log_format_invalid(self):
        for value in ('jason', 'vanilla', 'pretty', 'color'):
            os.environ['LOG_FORMAT'] = value
            with self.assertRaisesRegex(
                    ValueError, 'LOG_FORMAT may be either "json" or "plain"'):
                sprockets_logging.config()


class StrToBoolTests(unittest.TestCase):
    def test_true(self):
        for value in ('1', 'y', 'yes', 'true'):
            self.assertEqual(
                True, sprockets_logging._strtobool(value.lower()))
            self.assertEqual(
                True, sprockets_logging._strtobool(value.upper()))

    def test_false(self):
        for value in ('0', 'n', 'no', 'false'):
            self.assertEqual(
                False, sprockets_logging._strtobool(value.lower()))
            self.assertEqual(
                False, sprockets_logging._strtobool(value.upper()))
        self.assertEqual(
            False, sprockets_logging._strtobool(None))

    def test_unhandled(self):
        for value in ('maybe', '2'):
            with self.assertRaises(ValueError):
                sprockets_logging._strtobool(value)
