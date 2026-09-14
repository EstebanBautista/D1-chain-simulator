# D1 chain simulator - environment operation.
#
# Run `make` with no arguments to see every available command.

.DEFAULT_GOAL := help
.PHONY: help up start down destroy shell exec test test-unit test-integration \
        logs ps require-running

COMPOSE := docker compose

help: ## Show this help
	@echo ""
	@echo "  D1 Chain Simulator - two stores and a central site"
	@echo ""
	@echo "  make up            Build the images and start the whole system in the background"
	@echo "  make start         Alias for 'make up'"
	@echo "  make down          DESTRUCTIVE. Stop and remove containers, networks, VOLUMES and orphans."
	@echo "                     This wipes BOTH store databases AND the central database: every"
	@echo "                     recorded sale is lost and the seed data is recreated on the next"
	@echo "                     'make up'."
	@echo "  make destroy       Alias for 'make down'"
	@echo "  make shell CONTAINER=<name>"
	@echo "                     Open an interactive shell inside a running container."
	@echo "                     Example: make shell CONTAINER=store-1-register-1"
	@echo "  make exec          Alias for 'make shell'"
	@echo "  make logs          Follow the logs of every service"
	@echo "  make logs CONTAINER=store-1-sync"
	@echo "                     Follow one service only. Use this to watch the batching:"
	@echo "                     each batch logs how many invoices went out and why."
	@echo "  make ps            Show the state of every service"
	@echo "  make test          Run the unit tests and the integration tests"
	@echo "  make test-unit     Run only the unit tests (backend, gateway, forwarder, central API)"
	@echo "  make test-integration"
	@echo "                     Run only the integration tests, from a register of each store"
	@echo ""
	@echo "  --- Stores -------------------------------------------------------"
	@echo "  Store 1, register 1:  http://localhost:8081"
	@echo "  Store 1, register 2:  http://localhost:8082"
	@echo "  Store 2, register 1:  http://localhost:8083"
	@echo "  Store 2, register 2:  http://localhost:8084"
	@echo ""
	@echo "  You reach a store's web site THROUGH one of its registers, the way a"
	@echo "  cashier does. Neither frontend container publishes a host port."
	@echo ""
	@echo "  Store 1 backend:   http://localhost:18000/health   (docs at /docs)"
	@echo "  Store 2 backend:   http://localhost:18001/health   (docs at /docs)"
	@echo "  Store 1 database:  localhost:55432                 (user/db 'store')"
	@echo "  Store 2 database:  localhost:55433                 (user/db 'store')"
	@echo ""
	@echo "  --- Central site (head office) -----------------------------------"
	@echo "  Dashboard:         http://localhost:8080"
	@echo "  Central API:       http://localhost:18100/health   (docs at /docs)"
	@echo "  Central database:  localhost:33306                 (user/db 'central', MySQL)"
	@echo ""
	@echo "  Host ports avoid the usual 5432, 8000 and 3306 so they do not clash"
	@echo "  with a PostgreSQL, API or MySQL you may already be running. Change"
	@echo "  them in .env."
	@echo ""
	@echo "  NOTE: fase 1 uses some of these same ports. Do not run both phases"
	@echo "  at once - run 'make down' in fase1/completo first."
	@echo ""
	@echo "  A sale takes up to about a minute to reach the dashboard: stores ship"
	@echo "  in batches of 10 invoices or every 60 seconds, whichever comes first."
	@echo "  See BATCH_MAX_AGE_SECONDS in .env to shorten it for a demonstration."
	@echo ""

up: ## Build and start everything in the background
	$(COMPOSE) up -d --build

start: up

down: ## Stop and remove containers, networks, volumes and orphans
	$(COMPOSE) down -v --remove-orphans

destroy: down

shell: ## Open a shell inside a container: make shell CONTAINER=store-1-register-1
ifndef CONTAINER
	@echo "Error: CONTAINER is required."
	@echo "Usage: make shell CONTAINER=<name>"
	@echo ""
	@echo "Available containers:"
	@echo "  Store 1: store-1-register-1, store-1-register-2, store-1-backend,"
	@echo "           store-1-frontend, store-1-postgres, store-1-sync"
	@echo "  Store 2: store-2-register-1, store-2-register-2, store-2-backend,"
	@echo "           store-2-frontend, store-2-postgres, store-2-sync"
	@echo "  Central: central-api, central-web, central-mysql"
	@echo "  External: payment-gateway"
	@exit 1
endif
	@$(COMPOSE) exec $(CONTAINER) sh -c 'command -v bash >/dev/null && exec bash || exec sh'

exec: shell

# The tests run inside the running containers, so they need the environment up.
# Failing here with a clear message beats a confusing "service not running"
# error from Compose, and keeps each target single-purpose: 'test' tests, it
# does not deploy.
require-running:
	@$(COMPOSE) ps --status running --services 2>/dev/null | grep -q . || { \
		echo "Error: the environment is not running."; \
		echo "Start it first with 'make up', then run the tests again."; \
		exit 1; \
	}

test: test-unit test-integration ## Run the full test suite

test-unit: require-running ## Run the unit tests inside the service containers
	@echo "==> Store backend unit tests"
	@$(COMPOSE) exec -T store-1-backend python -m pytest app -q
	@echo "==> Payment gateway unit tests"
	@$(COMPOSE) exec -T payment-gateway python -m pytest app -q
	@echo "==> Forwarder unit tests"
	@$(COMPOSE) exec -T store-1-sync python -m pytest app -q
	@echo "==> Central API unit tests"
	@$(COMPOSE) exec -T central-api python -m pytest app -q

test-integration: require-running ## Run the integration tests from a register of each store
	@echo "==> Integration tests from store-1-register-1"
	@$(COMPOSE) exec -T store-1-register-1 python integration_tests.py
	@echo "==> Integration tests from store-2-register-1"
	@$(COMPOSE) exec -T store-2-register-1 python integration_tests.py
	@echo "==> Consolidation tests (store to head office)"
	@$(COMPOSE) exec -T store-1-sync python -m app.consolidation_tests
	@echo "==> Delivery resilience (head office unavailable)"
	@./scripts/resilience_test.sh

logs: ## Follow the logs of every service, or of one: make logs CONTAINER=store-1-sync
ifdef CONTAINER
	$(COMPOSE) logs -f $(CONTAINER)
else
	$(COMPOSE) logs -f
endif

ps: ## Show the state of every service
	$(COMPOSE) ps
