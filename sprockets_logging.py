import contextvars
import logging
import os
import typing

import jsonscribe


_context = {}


_JSONSCRIBE_ENVS = {
    'testing',
    'staging',
    'production',
}


def set_context(key, value):
    global _context

    if key not in _context:
        _context[key] = contextvars.ContextVar(key, default=None)

    _context[key].set(value)


class _LogFormatter(logging.Formatter):
    def format(self, record):
        parts = [super().format(record)]

        for key, cvar in _context.items():
            value = cvar.get()
            if value:
                parts.append(f'[{key} {value}]')

        return ' '.join(parts)


class _JSONFormatter(jsonscribe.JSONFormatter):
    def format(self, record):
        context = {}
        for key, cvar in _context.items():
            value = cvar.get()
            if value:
                context[key] = value
        if context:
            record.context = context
        return super().format(record)


def config(level: typing.Optional[int] = None,
           use_jsonscribe: typing.Optional[bool] = None) -> dict:
    """Build the `logging.config.dictConfig` config dict

    :param level: logging level to use (ex. ``logging.INFO``). When ``None``,
        the environment variable ``DEBUG`` is used to set the level to either
        ``logging.DEBUG`` or ``logging.INFO``

    :param use_jsonscribe: indicates logs should be written using jsonscribe.
        When ``None``, the environment variable ``ENVIRONMENT`` determines:
        ``True`` if the environment is ``testing``, ``staging``, or
        ``production``.

    :return: a :class:`dict` ready to be passed into
        :func:`logging.config.dictConfig`

    """
    if level is None:
        debug = _strtobool(os.environ.get('DEBUG', ''))
        level = logging.DEBUG if debug else logging.INFO

    if use_jsonscribe is None:
        log_format = os.environ.get('LOG_FORMAT')
        if log_format:
            if log_format == 'plain':
                use_jsonscribe = False
            elif log_format == 'json':
                use_jsonscribe = True
            else:
                raise ValueError('LOG_FORMAT may be either "json" or "plain"')
        else:
            use_jsonscribe = os.environ.get('ENVIRONMENT') in _JSONSCRIBE_ENVS

    if use_jsonscribe:
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
                    '()': f'{__name__}._JSONFormatter',
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
    else:
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'incremental': False,
            'formatters': {
                'file': {
                    '()': f'{__name__}._LogFormatter',
                    'format': ' '.join([
                        '%(asctime)s',
                        '%(levelname)-8s',
                        '%(name)s',
                        '%(message)s'
                    ])
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


def _strtobool(value: typing.Optional[str]) -> bool:
    if not value:
        return False
    value = value.strip().lower()
    if value in ('0', 'n', 'no', 'false'):
        return False
    elif value in ('1', 'y', 'yes', 'true'):
        return True
    else:
        raise ValueError('cannot determine bool: "{value}"')
