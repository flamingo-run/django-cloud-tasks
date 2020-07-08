![Github CI](https://github.com/joaodaher/django-cloud-tasks-py/workflows/Github%20CI/badge.svg)
[![Maintainability](https://api.codeclimate.com/v1/badges/b21079c0b64dcb8e2c46/maintainability)](https://codeclimate.com/github/joaodaher/django-cloud-tasks/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/b21079c0b64dcb8e2c46/test_coverage)](https://codeclimate.com/github/joaodaher/django-cloud-tasks/test_coverage)
[![python](https://img.shields.io/badge/python-3.8-blue.svg)]()

# Django Cloud Tasks


## Setup

### As an application (when contributing)

- Install packages:

```
    make dependencies
```


- If you have changed the package dependencies in Pipfile:

```
    make update
```

### As a package (when inside another application)

- In the application's pyproject.toml, add the remote private repository and the package with version:
```
[packages]
django-google-cloud-tasks = {version="<version>"}
```

- During development, if you wish to install from a local source (in order to test integration with ease):
```
    # inside the application
    poetry run pip install /<path>/<to>/<django-cloud-tasks>
```

## Tests

To run tests:

```
make test
```


## Version

Use [Semantic versioning](https://semver.org/).
