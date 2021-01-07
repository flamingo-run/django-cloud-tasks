![Github CI](https://github.com/flamingo-run/django-cloud-tasks/workflows/Github%20CI/badge.svg)
[![Maintainability](https://api.codeclimate.com/v1/badges/4e211a8dc7a2520873c6/maintainability)](https://codeclimate.com/github/flamingo-run/django-cloud-tasks/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/4e211a8dc7a2520873c6/test_coverage)](https://codeclimate.com/github/flamingo-run/django-cloud-tasks/test_coverage)
[![python](https://img.shields.io/badge/python-3.8-blue.svg)]()

# Django Cloud Tasks

Powered by [GCP Pilot](https://github.com/flamingo-run/gcp-pilot).

## APIs

The following APIs must be enabled in your project(s):

- [Cloud Tasks API](https://console.cloud.google.com/marketplace/product/google/cloudtasks.googleapis.com)
- [Cloud Scheduler API](https://console.cloud.google.com/marketplace/product/google/cloudscheduler.googleapis.com)
- [Admin SDK API](https://console.cloud.google.com/marketplace/product/google/admin.googleapis.com)

## How it works

![image](https://user-images.githubusercontent.com/9717144/100749131-00cce780-33c3-11eb-8f2a-b465bc0a45bb.png)

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
