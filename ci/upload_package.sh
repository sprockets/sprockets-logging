#!/usr/bin/env sh
set -e
rm -rf dist
python setup.py sdist
twine upload dist/*
