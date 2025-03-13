.PHONY: start-hello start-goodbye start-math start-all stop help start-runtime install-deps cli interactive runtime-cli check-agents restart kill-port clean-ports check-ports setup-venv test test-cov demo lint flake8 mypy autoflake isort autopep8 format check-format ui-deps ui-dev ui-build ui-start start-full

# Default target
all: start-all

# Set up virtual environment and install dependencies
setup-venv:
	@echo "Setting up virtual environment..."
	python -m venv .venv
	@echo "Virtual environment created at .venv/"
	@echo "To activate it, run: source .venv/bin/activate"
	@echo "Installing dependencies into virtual environment..."
	. .venv/bin/activate && pip install -r requirements.txt
	@echo "To check the Semantic Kernel version:"
	@echo "source .venv/bin/activate && pip show semantic-kernel"

# Install dependencies for the runtime
install-deps:
	@echo "Installing Semantic Kernel and other dependencies..."
	@if [ -d ".venv" ]; then \
		echo "Using virtual environment..."; \
		. .venv/bin/activate && pip install -r requirements.txt; \
	else \
		echo "No virtual environment found, installing globally (consider running 'make setup-venv' first)..."; \
		pip install -r requirements.txt; \
	fi

# Install UI dependencies
ui-deps:
	@echo "Installing UI dependencies..."
	cd ui && npm install

# Start the UI in development mode
ui-dev:
	@echo "Starting UI in development mode on http://localhost:3000..."
	cd ui && npm run dev

# Build the UI for production
ui-build:
	@echo "Building UI for production..."
	cd ui && npm run build

# Start the built UI
ui-start:
	@echo "Starting built UI on http://localhost:3000..."
	cd ui && npm run start

# Start all components including UI
start-full: start-all ui-dev
	@echo "All components including UI are running!"

# Check if particular ports are in use
check-ports:
	@echo "Checking if ports are in use..."
	@if lsof -i:5003 > /dev/null 2>&1; then \
		echo "⚠️  Port 5003 (Runtime) is in use"; \
	else \
		echo "✅ Port 5003 (Runtime) is available"; \
	fi
	@if lsof -i:5001 > /dev/null 2>&1; then \
		echo "⚠️  Port 5001 (Hello Agent) is in use"; \
	else \
		echo "✅ Port 5001 (Hello Agent) is available"; \
	fi
	@if lsof -i:5002 > /dev/null 2>&1; then \
		echo "⚠️  Port 5002 (Goodbye Agent) is in use"; \
	else \
		echo "✅ Port 5002 (Goodbye Agent) is available"; \
	fi
	@if lsof -i:5004 > /dev/null 2>&1; then \
		echo "⚠️  Port 5004 (Math Agent) is in use"; \
	else \
		echo "✅ Port 5004 (Math Agent) is available"; \
	fi
	@if lsof -i:3000 > /dev/null 2>&1; then \
		echo "⚠️  Port 3000 (UI) is in use"; \
	else \
		echo "✅ Port 3000 (UI) is available"; \
	fi

# Kill processes using specific ports
kill-port:
	@echo "Killing processes using ports 5003, 5001, 5002, 5004, and 3000..."
	-lsof -ti:5003 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5001 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5002 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5004 | xargs kill -9 2>/dev/null || true
	-lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@echo "Ports should now be free"

# Clean up all ports used by our services
clean-ports: kill-port
	@echo "Ports have been cleaned, waiting for sockets to close..."
	@sleep 2
	@$(MAKE) check-ports

# Check if agents are running
check-agents:
	@echo "Checking if agents are already running..."
	@if pgrep -f "python hello_agent.py" > /dev/null; then \
		echo "Hello Agent is already running."; \
	else \
		echo "Hello Agent is not running, starting it..."; \
		cd agents/hello_agent && python hello_agent.py & \
		echo "Hello Agent started on http://localhost:5001"; \
	fi
	@if pgrep -f "dotnet run" | grep -q goodbye_agent; then \
		echo "Goodbye Agent is already running."; \
	else \
		echo "Goodbye Agent is not running, starting it..."; \
		cd agents/goodbye_agent && dotnet run & \
		echo "Goodbye Agent started on http://localhost:5002"; \
	fi

# Start the Hello Agent (Python)
start-hello:
	@echo "Starting Hello Agent..."
	@if lsof -i:5001 > /dev/null 2>&1; then \
		echo "⚠️  Port 5001 is already in use. Killing existing process..."; \
		lsof -ti:5001 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	cd agents/hello_agent && python hello_agent.py &
	@echo "Hello Agent started on http://localhost:5001"

# Start the Goodbye Agent (.NET)
start-goodbye:
	@echo "Starting Goodbye Agent..."
	@if lsof -i:5002 > /dev/null 2>&1; then \
		echo "⚠️  Port 5002 is already in use. Killing existing process..."; \
		lsof -ti:5002 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	cd agents/goodbye_agent && dotnet run &
	@echo "Goodbye Agent started on http://localhost:5002"

# Start the Math Agent (Python)
start-math:
	@echo "Starting Math Agent..."
	@if lsof -i:5004 > /dev/null 2>&1; then \
		echo "⚠️  Port 5004 is already in use. Killing existing process..."; \
		lsof -ti:5004 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	cd agents/math_agent && python math_agent.py &
	@echo "Math Agent started on http://localhost:5004"

# Start the Agent Runtime
start-runtime:
	@echo "Starting Agent Runtime..."
	@if lsof -i:5003 > /dev/null 2>&1; then \
		echo "⚠️  Port 5003 is already in use. Killing existing process..."; \
		lsof -ti:5003 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	PYTHONUNBUFFERED=1 python api.py &
	@echo "Runtime started on http://localhost:5003"

# Start both agents and the runtime
start-all: start-hello start-goodbye start-math start-runtime
	@echo "All backend components are running!"

# Start all components in the background and launch CLI (main command for users)
interactive: clean-ports
	@echo "Starting all backend services..."
	@$(MAKE) start-all
	@echo "Starting CLI interface..."
	./cli.py interactive

# Start all components including the UI (web-based interface)
interactive-web: clean-ports
	@echo "Starting all backend services..."
	@$(MAKE) start-all
	@echo "Starting UI..."
	$(MAKE) ui-dev

# Restart all components
restart: stop clean-ports
	@echo "Restarting all components..."
	@sleep 2
	@$(MAKE) start-all

# Stop all components - more thoroughly
stop:
	@echo "Stopping all processes..."
	@echo "Stopping NextJS UI app..."
	-pkill -f "next dev" 2>/dev/null || true
	-pkill -f "next start" 2>/dev/null || true
	
	@echo "Stopping Flask apps (Hello Agent, Math Agent, and Runtime)..."
	-pkill -f "python hello_agent.py" 2>/dev/null || true
	-pkill -f "python math_agent.py" 2>/dev/null || true
	-pkill -f "runtime_api.py" 2>/dev/null || true
	-pkill -f "api.py" 2>/dev/null || true
	
	@echo "Stopping .NET apps (Goodbye Agent)..."
	-pkill -f "dotnet run" 2>/dev/null || true
	-pkill -f "GoodbyeAgent" 2>/dev/null || true
	
	@echo "Cleaning up any remaining processes on our ports..."
	@$(MAKE) kill-port
	
	@echo "All components stopped"

# Check status of all components - more thoroughly
status:
	@echo "Checking status of all components..."
	@echo "Checking by process name:"
	@if pgrep -f "python hello_agent.py" > /dev/null; then \
		echo "Hello Agent (process): RUNNING"; \
	else \
		echo "Hello Agent (process): STOPPED"; \
	fi
	@if pgrep -f "dotnet run" | grep -q goodbye_agent; then \
		echo "Goodbye Agent (process): RUNNING"; \
	else \
		echo "Goodbye Agent (process): STOPPED"; \
	fi
	@if pgrep -f "python runtime_api.py" > /dev/null; then \
		echo "Runtime (process): RUNNING"; \
	else \
		echo "Runtime (process): STOPPED"; \
	fi
	
	@echo "\nChecking by port availability:"
	@if lsof -i:5001 > /dev/null 2>&1; then \
		echo "Port 5001 (Hello Agent): IN USE"; \
	else \
		echo "Port 5001 (Hello Agent): AVAILABLE"; \
	fi
	@if lsof -i:5002 > /dev/null 2>&1; then \
		echo "Port 5002 (Goodbye Agent): IN USE"; \
	else \
		echo "Port 5002 (Goodbye Agent): AVAILABLE"; \
	fi
	@if lsof -i:5003 > /dev/null 2>&1; then \
		echo "Port 5003 (Runtime): IN USE"; \
	else \
		echo "Port 5003 (Runtime): AVAILABLE"; \
	fi

# Help command
help:
	@echo "Agent Runtime System Commands:"
	@echo "  make install-deps    - Install dependencies for the runtime"
	@echo "  make setup-venv      - Set up a Python virtual environment and install dependencies"
	@echo "  make start-all       - Start all backend agents and the runtime"
	@echo "  make interactive     - Start all backend components and launch the CLI interface"
	@echo "  make restart         - Restart all components (with port checking)"
	@echo "  make stop            - Stop all running components"
	@echo ""
	@echo "UI Commands:"
	@echo "  make ui-deps         - Install UI dependencies"
	@echo "  make ui-dev          - Start the UI in development mode"
	@echo "  make ui-build        - Build the UI for production"
	@echo "  make ui-start        - Start the built UI"
	@echo "  make start-full      - Start all backend components and the UI"
	@echo "  make interactive-web - Start backends and launch the web UI"
	@echo ""
	@echo "Utility Commands:"
	@echo "  make check-ports     - Check if the ports needed are available"
	@echo "  make kill-port       - Kill processes using our required ports"
	@echo "  make clean-ports     - Kill processes and verify ports are free"
	@echo "  make cli             - Start the CLI interface only (assumes runtime is running)"
	@echo "  make status          - Check the status of all components"
	@echo "  make demo            - Run a quick demonstration of the system's functionality"
	@echo "  make test            - Run all tests"
	@echo "  make test-cov        - Run tests with coverage"
	@echo ""
	@echo "Code Quality Commands:"
	@echo "  make lint            - Run all linters (flake8 and mypy)"
	@echo "  make format          - Run all formatters (autoflake, isort, autopep8)"
	@echo "  make check-format    - Check code formatting without modifying files (for CI)"

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v

# Run tests with coverage
test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=runtime --cov=api --cov=cli --cov-report=term-missing -v

# Demonstrate the system's functionality
demo:
	@echo "Demonstrating Agent Runtime functionality..."
	@echo "\nTesting Hello Agent..."
	curl -X POST http://localhost:5001/api/message \
		-H "Content-Type: application/json" \
		-d '{"messageId": "demo-msg-1", "conversationId": "demo-conv", "senderId": "demo", "recipientId": "hello-agent", "content": "Say hello in Spanish", "timestamp": "2023-03-10T12:00:00Z", "type": "Text"}' | jq
	@echo "\nTesting Goodbye Agent..."
	curl -X POST http://localhost:5002/api/message \
		-H "Content-Type: application/json" \
		-d '{"messageId": "demo-msg-2", "conversationId": "demo-conv", "senderId": "demo", "recipientId": "goodbye-agent", "content": "Say goodbye in French", "timestamp": "2023-03-10T12:00:00Z", "type": 0}' | jq
	@echo "\nTesting Runtime with both agents..."
	./cli.py --group "hello-agent,goodbye-agent" --query "Say hello in Spanish and say goodbye in French"

# Code Quality Commands
lint: flake8 mypy

flake8:
	@echo "Running flake8..."
	flake8 runtime/ cli/ api/ tests/

mypy:
	@echo "Running mypy..."
	mypy runtime/ cli/ api/ tests/

autoflake:
	@echo "Running autoflake to remove unused imports..."
	autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive runtime/ cli/ api/ tests/

isort:
	@echo "Running isort to sort imports..."
	isort runtime/ cli/ api/ tests/

autopep8:
	@echo "Running autopep8 to fix PEP8 style issues..."
	autopep8 --in-place --aggressive --aggressive --recursive runtime/ cli/ api/ tests/

check-format:
	@echo "Checking code formatting without modifying files..."
	@echo "Checking imports with isort..."
	isort --check-only runtime/ cli/ api/ tests/
	@echo "Checking style with autopep8..."
	autopep8 --exit-code --diff --recursive runtime/ cli/ api/ tests/
	@echo "Checking unused imports and variables with autoflake..."
	autoflake --check --remove-all-unused-imports --remove-unused-variables --recursive runtime/ cli/ api/ tests/
	@echo "Format check complete."

format: autoflake isort autopep8
	@echo "Code formatting complete." 