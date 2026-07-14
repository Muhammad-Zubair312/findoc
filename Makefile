.PHONY: up down bootstrap logs test lint format

up:
	docker-compose up -d

down:
	docker-compose down

bootstrap:
	bash scripts/bootstrap.sh

logs:
	docker-compose logs -f --tail=200

test:
	docker-compose run --rm backend pytest -v
	docker-compose run --rm frontend npm run type-check

lint:
	docker-compose run --rm backend ruff check .
	docker-compose run --rm backend mypy app
	docker-compose run --rm frontend npm run lint

format:
	docker-compose run --rm backend ruff format .
	docker-compose run --rm backend ruff check --fix .
