setup:
	@pip install -U pip poetry
	@poetry config pypi-token.pypi $(PYPI_API_TOKEN)

dependencies:
	@make setup
	@poetry install --no-root

update:
	@poetry update

test:
	@make check
	@make lint
	@make unit

check:
	@poetry check

lint:
	@echo "Checking code style ..."
	@poetry run pylint django_cloud_tasks sample_project

unit:
	@echo "Running unit tests ..."
	ENV=test poetry run coverage run sample_project/manage.py test --no-input

clean:
	@rm -rf .coverage coverage.xml dist/ build/ *.egg-info/

publish:
	@make clean
	@printf "\nPublishing lib"
	@make setup
	@poetry publish --build
	@make clean


.PHONY: lint publish clean unit test dependencies setup
