# Contributing
## Development Setup
```
python3.9 -m venv env
. env/bin/activate
pip install -e '.[tests]'
```

## Running Tests
```
coverage run
```

## Versioning
- Update `version` in `setup.cfg`
- Update `CHANGELOG.md`
- Commit and tag changes
