.PHONY: help start stop restart logs clean ps status url build vm-start vm-stop vm-status

GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
NC     := \033[0m

MACHINE_NAME := course-vm

help:
	@echo "$(GREEN)Jupyter Notebook Environment (Podman)$(NC)"
	@echo ""
	@echo "$(YELLOW)First time setup:$(NC)"
	@echo "  make vm-start   - Start the Podman machine"
	@echo "  make build      - Build the Jupyter image"
	@echo "  make start      - Start Jupyter Lab"
	@echo ""
	@echo "$(YELLOW)Daily usage:$(NC)"
	@echo "  make vm-start   - Start the Podman machine"
	@echo "  make start      - Start Jupyter Lab"
	@echo "  make stop       - Stop Jupyter Lab"
	@echo "  make vm-stop    - Stop the Podman machine"
	@echo ""
	@echo "$(YELLOW)Other commands:$(NC)"
	@echo "  make restart    - Restart Jupyter Lab"
	@echo "  make logs       - View Jupyter Lab logs"
	@echo "  make ps         - Show running containers"
	@echo "  make status     - Check environment status"
	@echo "  make url        - Show Jupyter Lab URL"
	@echo "  make clean      - Remove containers and volumes"
	@echo "  make vm-status  - Show Podman machine status"
	@echo ""

# === VM Management ===

vm-start:
	@echo "$(YELLOW)Stopping any running Podman machines (only one can run at a time on macOS)...$(NC)"
	@for vm in $$(podman machine list --format '{{.Name}}:{{.Running}}' | grep ':true' | cut -d: -f1 | sed 's/\*$$//'); do \
		if [ "$$vm" != "$(MACHINE_NAME)" ]; then \
			echo "Stopping $$vm..."; \
			podman machine stop $$vm; \
		fi; \
	done
	@echo "$(GREEN)Starting Podman machine '$(MACHINE_NAME)'...$(NC)"
	@podman machine start $(MACHINE_NAME) || true
	@podman system connection default $(MACHINE_NAME)
	@echo "$(GREEN)Machine started and set as default connection.$(NC)"

vm-stop:
	@echo "$(YELLOW)Stopping Podman machine '$(MACHINE_NAME)'...$(NC)"
	podman machine stop $(MACHINE_NAME)
	@echo "$(GREEN)Machine stopped.$(NC)"

vm-status:
	@echo "$(GREEN)Podman machines:$(NC)"
	@podman machine list
	@echo ""
	@echo "$(GREEN)Active connection:$(NC)"
	@podman system connection list

# === Container Management ===

start:
	@echo "$(GREEN)Checking Podman machine connection...$(NC)"
	@if podman machine inspect $(MACHINE_NAME) --format '{{.State}}' 2>/dev/null | grep -q "running"; then \
		echo "$(GREEN)✓ Podman machine '$(MACHINE_NAME)' is running$(NC)"; \
	else \
		echo "$(RED)✗ Podman machine '$(MACHINE_NAME)' is not running$(NC)"; \
		echo "$(YELLOW)  Run: make vm-start$(NC)"; \
		exit 1; \
	fi
	@mkdir -p notebooks data
	@echo "$(GREEN)Starting Jupyter Lab environment...$(NC)"
	podman-compose up -d
	@sleep 5
	@echo "$(GREEN)✓ Environment started$(NC)"
	@make url

stop:
	@echo "$(YELLOW)Stopping Jupyter Lab environment...$(NC)"
	podman-compose down
	@echo "$(GREEN)✓ Environment stopped$(NC)"

restart: stop start

logs:
	podman-compose logs -f jupyter

ps:
	@echo "$(GREEN)Running containers:$(NC)"
	podman-compose ps

status:
	@echo "$(GREEN)Environment Status:$(NC)"
	@podman-compose ps
	@echo ""
	@if [ -n "$$(podman-compose ps -q jupyter 2>/dev/null)" ]; then \
		echo "$(GREEN)✓ Jupyter Lab is running$(NC)"; \
		curl -s http://localhost:8888/lab > /dev/null && echo "$(GREEN)✓ Jupyter Lab is healthy$(NC)" || echo "$(YELLOW)⚠ Jupyter Lab is initializing...$(NC)"; \
	else \
		echo "$(RED)✗ Jupyter Lab is not running$(NC)"; \
	fi

url:
	@echo ""
	@echo "$(GREEN)Jupyter Lab is available at:$(NC)"
	@echo "$(YELLOW)  http://localhost:8888/lab$(NC)"
	@echo ""

clean:
	@echo "$(RED)Removing containers and volumes...$(NC)"
	podman-compose down -v
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

build:
	@echo "$(GREEN)Building Docker image for Podman...$(NC)"
	BUILDAH_FORMAT=docker podman-compose build --no-cache
	@echo "$(GREEN)✓ Build complete$(NC)"
