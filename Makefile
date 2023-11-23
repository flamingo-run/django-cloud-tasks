setup:
	@pip install -U pip poetry

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
	@echo "Checking safety and integrity ..."
	poetry check
	poetry run safety check

lint:
	@echo "Checking code style ..."
	poetry run ruff format --check .
	poetry run ruff check .

style:
	@echo "Applying code style ..."
	poetry run ruff format .
	poetry run ruff . --fix

unit:
	@echo "Running unit tests ..."
	ENV=test poetry run pytest test

clean:
	@rm -rf .coverage coverage.xml dist/ build/ *.egg-info/

publish:
	@make clean
	@printf "\nPublishing lib"
	@make setup
	@poetry config pypi-token.pypi $(PYPI_API_TOKEN)
	@poetry publish --build
	@make clean


.PHONY: lint publish clean unit test dependencies setup
