.PHONY: start-hello start-goodbye start-math start-all stop help start-runtime install-deps cli interactive runtime-cli check-agents restart kill-port clean-ports check-ports setup-venv test test-cov demo lint flake8 mypy autoflake isort autopep8 format check-format ui-deps ui-dev ui-build ui-start start-backend start-frontend install-rag-deps

# Default target
all: start-all

# =======================================
# Setup and Installation
# =======================================

# Complete first-time setup for development (both backend and frontend)
setup: check-dependencies setup-venv install-deps install-rag-deps ui-deps
	@echo "✅ Complete setup finished. You can now start the system with 'make start-all'"

# Check if required dependencies are installed
check-dependencies:
	@echo "Checking required dependencies..."
	@if ! command -v python3 &> /dev/null; then echo "❌ Python 3 is not installed"; exit 1; fi
	@if ! command -v pip3 &> /dev/null; then echo "❌ pip3 is not installed"; exit 1; fi
	@if ! command -v node &> /dev/null; then echo "❌ Node.js is not installed"; exit 1; fi
	@if ! command -v npm &> /dev/null; then echo "❌ npm is not installed"; exit 1; fi
	@echo "✅ All required dependencies are installed"

# Set up a Python virtual environment
setup-venv:
	@echo "Setting up Python virtual environment..."
	@python3 -m venv .venv || (echo "❌ Failed to create virtual environment"; exit 1)
	@echo "✅ Virtual environment created at .venv"
	@echo "To activate: source .venv/bin/activate"

# Install Python dependencies
install-deps:
	@echo "Installing Python dependencies..."
	@pip3 install -r requirements.txt || (echo "❌ Failed to install dependencies"; exit 1)
	@echo "✅ Python dependencies installed"

# Install RAG API dependencies
install-rag-deps:
	@echo "Installing RAG API dependencies..."
	@pip3 install -r ragapi/requirements.txt || (echo "❌ Failed to install RAG dependencies"; exit 1)
	@echo "✅ RAG API dependencies installed"

# Install UI dependencies
ui-deps:
	@echo "Installing UI dependencies..."
	@cd ui && npm install || (echo "❌ Failed to install UI dependencies"; exit 1)
	@echo "✅ UI dependencies installed"

# =======================================
# Development UI Commands
# =======================================

# Start UI in development mode
ui-dev:
	@echo "Starting UI in development mode..."
	@cd ui && npm run dev

# Build the UI for production
ui-build:
	@echo "Building UI for production..."
	@cd ui && npm run build

# Start the built UI
ui-start:
	@echo "Starting built UI..."
	@cd ui && npm run start

# =======================================
# Service Management
# =======================================

# Start everything (backend and frontend)
start-all: clean-ports start-backend start-frontend
	@echo "✅ All services started (backend + frontend)"

# Start only backend services
start-backend: start-hello start-goodbye start-math start-runtime start-proxy start-rag
	@echo "✅ Backend services started"

# Start only frontend
start-frontend:
	@echo "Starting UI in development mode..."
	@cd ui && npm run dev &
	@echo "✅ Frontend UI started on http://localhost:3000"

# =======================================
# Individual Service Control
# =======================================

# Start Hello Agent
start-hello:
	@echo "Starting Hello Agent..."
	@if lsof -i:5103 > /dev/null 2>&1; then \
		echo "⚠️  Port 5103 is already in use. Killing existing process..."; \
		lsof -ti:5103 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	@cd agents/hello_agent && PYTHONUNBUFFERED=1 python hello_agent.py &
	@echo "✅ Hello Agent started on http://localhost:5103"

# Start Goodbye Agent
start-goodbye:
	@echo "Starting Goodbye Agent..."
	@if lsof -i:5101 > /dev/null 2>&1; then \
		echo "⚠️  Port 5101 is already in use. Killing existing process..."; \
		lsof -ti:5101 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	@cd agents/goodbye_agent && dotnet run --urls http://localhost:5101 &
	@echo "✅ Goodbye Agent started on http://localhost:5101"

# Start Math Agent
start-math:
	@echo "Starting Math Agent..."
	@if lsof -i:5100 > /dev/null 2>&1; then \
		echo "⚠️  Port 5100 is already in use. Killing existing process..."; \
		lsof -ti:5100 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	@cd agents/math_agent && PYTHONUNBUFFERED=1 python math_agent.py &
	@echo "✅ Math Agent started on http://localhost:5100"

# Start the runtime API
start-runtime:
	@echo "Starting Runtime API..."
	@if lsof -i:5002 > /dev/null 2>&1; then \
		echo "⚠️  Port 5002 is already in use. Killing existing process..."; \
		lsof -ti:5002 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	PYTHONUNBUFFERED=1 python -m uvicorn runtime.api:app --host 0.0.0.0 --port 5002 &
	@echo "✅ Runtime API started on http://localhost:5002"

# Start the proxy API
start-proxy:
	@echo "Starting API Proxy..."
	@if lsof -i:5001 > /dev/null 2>&1; then \
		echo "⚠️  Port 5001 is already in use. Killing existing process..."; \
		lsof -ti:5001 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	PYTHONUNBUFFERED=1 python -m uvicorn api.proxy_api:app --host 0.0.0.0 --port 5001 &
	@echo "✅ API Proxy started on http://localhost:5001"

# Start the RAG API
start-rag:
	@echo "Starting RAG API..."
	@if lsof -i:5003 > /dev/null 2>&1; then \
		echo "⚠️  Port 5003 is already in use. Killing existing process..."; \
		lsof -ti:5003 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	PYTHONUNBUFFERED=1 python -m uvicorn ragapi.main:app --host 0.0.0.0 --port 5003 &
	@echo "✅ RAG API started on http://localhost:5003"

# =======================================
# Interactive Interfaces
# =======================================

# Start all backend components and launch CLI
interactive: clean-ports
	@echo "Starting all backend services..."
	@$(MAKE) start-backend
	@echo "Starting CLI..."
	@cd cli && python client.py

# Start all backend components and launch web UI
interactive-web: clean-ports
	@echo "Starting all services..."
	@$(MAKE) start-all

# =======================================
# Service Management
# =======================================

# Restart all components
restart: stop clean-ports
	@echo "Restarting all components..."
	@$(MAKE) start-all
	@echo "✅ All services restarted"

# Stop all running components
stop:
	@echo "Stopping all components..."
	@pkill -f "uvicorn .*.api:app" 2>/dev/null || true
	@pkill -f "python .*.py" 2>/dev/null || true
	@pkill -f "dotnet .*.dll" 2>/dev/null || true
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || true  # UI port
	@lsof -ti:5001 | xargs kill -9 2>/dev/null || true  # API Proxy
	@lsof -ti:5002 | xargs kill -9 2>/dev/null || true  # Runtime API
	@lsof -ti:5003 | xargs kill -9 2>/dev/null || true  # RAG API
	@lsof -ti:5100 | xargs kill -9 2>/dev/null || true  # Math Agent
	@lsof -ti:5101 | xargs kill -9 2>/dev/null || true  # Goodbye Agent
	@lsof -ti:5103 | xargs kill -9 2>/dev/null || true  # Hello Agent
	@echo "✅ All components stopped"

# Check status of all components
status:
	@echo "Checking status of all components..."
	@echo ""
	@echo "UI (Port 3000):"
	@if lsof -i:3000 > /dev/null 2>&1; then echo "  ✅ Running"; else echo "  ❌ Not running"; fi
	@echo ""
	@echo "API Proxy (Port 5001):"
	@if lsof -i:5001 > /dev/null 2>&1; then echo "  ✅ Running"; else echo "  ❌ Not running"; fi
	@echo ""
	@echo "Runtime API (Port 5002):"
	@if lsof -i:5002 > /dev/null 2>&1; then echo "  ✅ Running"; else echo "  ❌ Not running"; fi
	@echo ""
	@echo "RAG API (Port 5003):"
	@if lsof -i:5003 > /dev/null 2>&1; then echo "  ✅ Running"; else echo "  ❌ Not running"; fi
	@echo ""
	@echo "Agents:"
	@echo "  Math Agent (Port 5100):"
	@if lsof -i:5100 > /dev/null 2>&1; then echo "    ✅ Running"; else echo "    ❌ Not running"; fi
	@echo "  Goodbye Agent (Port 5101):"
	@if lsof -i:5101 > /dev/null 2>&1; then echo "    ✅ Running"; else echo "    ❌ Not running"; fi
	@echo "  Hello Agent (Port 5103):"
	@if lsof -i:5103 > /dev/null 2>&1; then echo "    ✅ Running"; else echo "    ❌ Not running"; fi

# =======================================
# Port Management
# =======================================

# Check if ports are available
check-ports:
	@echo "Checking port availability..."
	@for port in 3000 5001 5002 5003 5100 5101 5103; do \
		if lsof -i:$$port > /dev/null 2>&1; then \
			echo "⚠️  Port $$port is in use."; \
			PORTS_IN_USE=1; \
		else \
			echo "✅ Port $$port is available."; \
		fi; \
	done; \
	if [ "$$PORTS_IN_USE" = "1" ]; then \
		echo "Some ports are in use. Run 'make clean-ports' to free them."; \
		exit 1; \
	fi

# Kill processes using required ports
kill-port:
	@echo "Killing processes on required ports..."
	@for port in 3000 5001 5002 5003 5100 5101 5103; do \
		if lsof -i:$$port > /dev/null 2>&1; then \
			echo "Killing process on port $$port"; \
			lsof -ti:$$port | xargs kill -9 2>/dev/null || true; \
		fi; \
	done
	@echo "✅ All port conflicts resolved"

# Clean up ports and verify they're free
clean-ports: kill-port
	@echo "Verifying ports are free..."
	@for port in 3000 5001 5002 5003 5100 5101 5103; do \
		if lsof -i:$$port > /dev/null 2>&1; then \
			echo "⚠️  Failed to free port $$port."; \
			exit 1; \
		else \
			echo "✅ Port $$port is free."; \
		fi; \
	done
	@echo "All ports are free."

# =======================================
# Demo and Testing
# =======================================

# Run a quick demonstration
demo:
	@echo "Running quick demo of agent capabilities..."
	@echo "1. Hello Agent: Testing greeting in French..."
	@curl -s -X POST -H "Content-Type: application/json" \
		-d '{"messageId":"test-msg-1","conversationId":"test-conv","senderId":"user","recipientId":"hello-agent","content":"Say hello in French"}' \
		http://localhost:5103/api/message
	@echo "\n\n2. Goodbye Agent: Testing farewell in Spanish..."
	@curl -s -X POST -H "Content-Type: application/json" \
		-d '{"messageId":"test-msg-2","conversationId":"test-conv","senderId":"user","recipientId":"goodbye-agent","content":"Say goodbye in Spanish"}' \
		http://localhost:5101/api/message
	@echo "\n\n3. Math Agent: Testing calculation..."
	@curl -s -X POST -H "Content-Type: application/json" \
		-d '{"messageId":"test-msg-3","conversationId":"test-conv","senderId":"user","recipientId":"math-agent","content":"What is 42 * 73?"}' \
		http://localhost:5100/api/message
	@echo "\n\nDemo complete! All agents are functioning."

# Run tests
test:
	pytest -xvs tests/

# Run tests with coverage
test-cov:
	pytest --cov=runtime --cov=api --cov=ragapi tests/

# =======================================
# Code Quality
# =======================================

# Run all linters
lint: flake8 mypy

# Run flake8
flake8:
	flake8 runtime/ api/ ragapi/ agents/ tests/

# Run mypy
mypy:
	mypy runtime/ api/ ragapi/

# Run autoflake
autoflake:
	autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place --exclude=__init__.py runtime api ragapi agents tests

# Run isort
isort:
	isort runtime api ragapi agents tests

# Run autopep8
autopep8:
	autopep8 --in-place --recursive runtime api ragapi agents tests

# Check formatting without modifying files
check-format:
	@echo "Checking code format without modifying files..."
	@isort --check-only runtime api ragapi agents tests || (echo "❌ isort check failed"; exit 1)
	@autopep8 --diff --recursive runtime api ragapi agents tests | grep -q . && (echo "❌ autopep8 check failed"; exit 1) || echo "✅ autopep8 check passed"

# Run all formatters
format: autoflake isort autopep8
	@echo "✅ Code formatting complete"

# =======================================
# Help
# =======================================

# Help command
help:
	@echo "Agent Runtime System Commands:"
	@echo "  make setup           - Complete first-time setup (backend + frontend)"
	@echo "  make check-dependencies - Verify required tools are installed"
	@echo "  make start-all       - Start everything (backend + frontend)"
	@echo "  make start-backend   - Start only backend services"
	@echo "  make start-frontend  - Start only frontend UI"
	@echo "  make restart         - Restart all components"
	@echo "  make stop            - Stop all running components"
	@echo ""
	@echo "Individual Service Control:"
	@echo "  make start-hello     - Start Hello Agent"
	@echo "  make start-goodbye   - Start Goodbye Agent"
	@echo "  make start-math      - Start Math Agent"
	@echo "  make start-runtime   - Start Runtime API"
	@echo "  make start-proxy     - Start API Proxy"
	@echo "  make start-rag       - Start RAG API"
	@echo ""
	@echo "UI Commands:"
	@echo "  make ui-deps         - Install UI dependencies"
	@echo "  make ui-dev          - Start the UI in development mode (foreground)"
	@echo "  make ui-build        - Build the UI for production"
	@echo "  make ui-start        - Start the built UI"
	@echo ""
	@echo "Interactive Commands:"
	@echo "  make interactive     - Start backend components and launch CLI"
	@echo "  make interactive-web - Start all components (backend + frontend)"
	@echo ""
	@echo "Port Management:"
	@echo "  make check-ports     - Check if required ports are available"
	@echo "  make kill-port       - Kill processes using required ports"
	@echo "  make clean-ports     - Kill processes and verify ports are free"
	@echo ""
	@echo "Testing and Demo:"
	@echo "  make demo            - Run a quick demo of the system's functionality"
	@echo "  make test            - Run all tests"
	@echo "  make test-cov        - Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint            - Run all linters (flake8 and mypy)"
	@echo "  make format          - Run all formatters"
	@echo "  make check-format    - Check code formatting without modifying files" 