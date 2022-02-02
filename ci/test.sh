#!/usr/bin/env sh
set -e
pip install -e '.[tests]'

flake8

coverage run
coverage report

python setup.py sdist
