.PHONY: start-hello start-goodbye start-all test-hello test-goodbye test-all stop help start-runtime install-deps cli interactive runtime-cli check-agents restart kill-port clean-ports check-ports test-group-chat setup-venv

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

# Kill processes using specific ports
kill-port:
	@echo "Killing processes using ports 5003, 5001, and 5002..."
	-lsof -ti:5003 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5001 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5002 | xargs kill -9 2>/dev/null || true
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
		cd samples/hello_agent && python hello_agent.py & \
		echo "Hello Agent started on http://localhost:5001"; \
	fi
	@if pgrep -f "dotnet run" | grep -q goodbye_agent; then \
		echo "Goodbye Agent is already running."; \
	else \
		echo "Goodbye Agent is not running, starting it..."; \
		cd samples/goodbye_agent && dotnet run & \
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
	cd samples/hello_agent && python hello_agent.py &
	@echo "Hello Agent started on http://localhost:5001"

# Start the Goodbye Agent (.NET)
start-goodbye:
	@echo "Starting Goodbye Agent..."
	@if lsof -i:5002 > /dev/null 2>&1; then \
		echo "⚠️  Port 5002 is already in use. Killing existing process..."; \
		lsof -ti:5002 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	cd samples/goodbye_agent && dotnet run &
	@echo "Goodbye Agent started on http://localhost:5002"

# Start the Agent Runtime
start-runtime:
	@echo "Starting Agent Runtime..."
	@if lsof -i:5003 > /dev/null 2>&1; then \
		echo "⚠️  Port 5003 is already in use. Killing existing process..."; \
		lsof -ti:5003 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	PYTHONUNBUFFERED=1 python runtime_api.py &
	@echo "Runtime started on http://localhost:5003"

# Start both agents and the runtime
start-all: start-hello start-goodbye start-runtime
	@echo "All components are running!"

# Restart all components
restart: stop clean-ports
	@echo "Restarting all components..."
	@sleep 2
	@$(MAKE) start-all

# Start CLI interface only (assumes runtime is already running)
cli:
	@echo "Starting CLI interface..."
	./runtime.py interactive

# Start CLI interface with minimal logging (assumes runtime is already running)
cli-quiet: cli

# Run both runtime and CLI in one terminal with logs visible (for development)
runtime-cli:
	@echo "Starting Agent Runtime in foreground mode..."
	@if lsof -i:5003 > /dev/null 2>&1; then \
		echo "⚠️  Port 5003 is already in use. Killing existing process..."; \
		lsof -ti:5003 | xargs kill -9 2>/dev/null || true; \
		sleep 1; \
	fi
	PYTHONUNBUFFERED=1 python runtime_api.py

# Start all components in the background and launch CLI (main command for users)
interactive: clean-ports
	@echo "Checking if agents are already running..."
	@if ! lsof -i:5001 > /dev/null 2>&1; then \
		echo "Starting Hello Agent..."; \
		cd samples/hello_agent && python hello_agent.py & \
		echo "Hello Agent started on http://localhost:5001"; \
	else \
		echo "Hello Agent is already running."; \
	fi
	
	@if ! lsof -i:5002 > /dev/null 2>&1; then \
		echo "Starting Goodbye Agent..."; \
		cd samples/goodbye_agent && dotnet run & \
		echo "Goodbye Agent started on http://localhost:5002"; \
	else \
		echo "Goodbye Agent is already running."; \
	fi
	
	@if ! lsof -i:5003 > /dev/null 2>&1; then \
		echo "Starting Agent Runtime..."; \
		PYTHONUNBUFFERED=1 python runtime_api.py & \
		echo "Runtime started on http://localhost:5003"; \
		sleep 2; \
	else \
		echo "Runtime is already running."; \
	fi
	
	@echo "Starting CLI interface..."
	./runtime.py interactive

# Start all components in the background and launch CLI with minimal logging
interactive-quiet: interactive

# Test Hello Agent with curl
test-hello:
	@echo "Testing Hello Agent..."
	curl -X POST http://localhost:5001/api/message \
		-H "Content-Type: application/json" \
		-d '{"messageId": "test-msg-1", "conversationId": "test-conv", "senderId": "tester", "recipientId": "hello-agent", "content": "Say hello in Spanish", "timestamp": "2023-03-10T12:00:00Z", "type": "Text"}' | jq
	@echo "\n"

# Test Goodbye Agent with curl
test-goodbye:
	@echo "Testing Goodbye Agent..."
	curl -X POST http://localhost:5002/api/message \
		-H "Content-Type: application/json" \
		-d '{"messageId": "test-msg-2", "conversationId": "test-conv", "senderId": "tester", "recipientId": "goodbye-agent", "content": "Say goodbye in French", "timestamp": "2023-03-10T12:00:00Z", "type": 0}' | jq
	@echo "\n"

# Test the runtime
test-runtime:
	@echo "Testing Agent Runtime..."
	curl -X POST http://localhost:5003/api/query \
		-H "Content-Type: application/json" \
		-d '{"query": "Say hello in Spanish and then say goodbye in French", "user_id": "tester", "verbose": true}' | jq
	@echo "\n"

# Test group chat with multiple agents
test-group-chat:
	@echo "Testing group chat with multiple agents..."
	./runtime.py group "hello-agent,goodbye-agent" "Please provide a greeting and a farewell"
	@echo "\n"

# Test all agents and runtime
test-all: test-hello test-goodbye test-runtime test-group-chat

# Stop all components - more thoroughly
stop:
	@echo "Stopping all processes..."
	@echo "Stopping Flask apps (Hello Agent and Runtime)..."
	-pkill -f "python hello_agent.py" 2>/dev/null || true
	-pkill -f "runtime_api.py" 2>/dev/null || true
	
	@echo "Stopping .NET apps (Goodbye Agent)..."
	-pkill -f "dotnet run" 2>/dev/null || true
	-pkill -f "GoodbyeAgent" 2>/dev/null || true
	
	@echo "Cleaning up any remaining processes on our ports..."
	-lsof -ti:5003 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5001 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5002 | xargs kill -9 2>/dev/null || true
	
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
	@echo "Available commands:"
	@echo "  make install-deps  - Install dependencies for the runtime"
	@echo "  make check-ports   - Check if the ports needed are available"
	@echo "  make kill-port     - Kill processes using our required ports"
	@echo "  make clean-ports   - Kill processes and verify ports are free"
	@echo "  make start-hello   - Start the Hello Agent"
	@echo "  make start-goodbye - Start the Goodbye Agent"
	@echo "  make start-runtime - Start the Agent Runtime"
	@echo "  make start-all     - Start both agents and the runtime"
	@echo "  make restart       - Restart all components (with port checking)"
	@echo "  make interactive   - Start all components and launch the CLI interface (RECOMMENDED)"
	@echo "  make cli           - Start the CLI interface only (assumes runtime is running)"
	@echo "  make runtime-cli   - Run runtime in foreground with visible logs (for development)"
	@echo "  make test-hello    - Test the Hello Agent"
	@echo "  make test-goodbye  - Test the Goodbye Agent"
	@echo "  make test-runtime  - Test the runtime"
	@echo "  make test-group-chat - Test group chat with multiple agents"
	@echo "  make test-all      - Test all components"
	@echo "  make status        - Check the status of all components"
	@echo "  make stop          - Stop all running components" 