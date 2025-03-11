# Testing Guide for Agent Runtime

This document provides guidance on testing the Agent Runtime system, including unit tests, test coverage, and best practices.

## Test Structure

The test suite is organized into several modules:

- `tests/test_agent_runtime.py`: Tests for the core `AgentRuntime` and `AgentPlugin` classes
- `tests/test_group_chat.py`: Tests for the `AgentGroupChat` and `AgentTerminationStrategy` classes
- `tests/test_api.py`: Tests for the FastAPI endpoints in `api/runtime_api.py`
- `tests/test_cli.py`: Tests for the CLI functionality in `cli/runtime.py`

## Running Tests

### Running All Tests

```bash
# Using the Makefile (recommended)
make test

# Using pytest directly
python -m pytest
```

### Running Tests with Coverage

```bash
# Using the Makefile (recommended)
make test-cov

# Using pytest directly
python -m pytest --cov=runtime --cov=api --cov=cli --cov-report=term-missing
```

### Running Specific Tests

While the Makefile doesn't have targets for specific tests, you can use pytest directly:

```bash
# Run tests in a specific file
python -m pytest tests/test_api.py

# Run a specific test class
python -m pytest tests/test_agent_runtime.py::TestAgentPlugin

# Run a specific test method
python -m pytest tests/test_agent_runtime.py::TestAgentRuntime::test_process_query
```

## Test Fixtures

The test suite uses several fixtures to set up test environments:

### Global Fixtures (in `conftest.py`)

- Configuration for pytest-asyncio to use session-scoped event loops

### Agent Runtime Fixtures

- `mock_kernel`: Creates a mock Semantic Kernel for testing
- `runtime`: Creates an `AgentRuntime` instance with the mock kernel

### Group Chat Fixtures

- `mock_agents`: Creates mock agent plugins for testing group chat
- `group_chat`: Creates an `AgentGroupChat` instance with mock agents

### API Fixtures

- `client`: Creates a FastAPI test client
- `mock_runtime`: Creates a mock `AgentRuntime` for API testing

### CLI Fixtures

- `runner`: Creates a Click test runner for CLI testing

## Testing Async Code

Many of the tests involve asynchronous code. We use `pytest-asyncio` to handle async tests:

```python
@pytest.mark.asyncio
async def test_async_function():
    # Test async code here
    result = await some_async_function()
    assert result == expected_value
```

## Mocking Strategies

### Mocking Semantic Kernel

The tests mock the Semantic Kernel to avoid making actual API calls:

```python
@pytest.fixture
def mock_kernel():
    """Create a mock Semantic Kernel for testing."""
    mock = MagicMock()
    
    # Mock the chat service
    mock_chat_service = MagicMock()
    mock_chat_service.get_chat_message_contents = AsyncMock(return_value="Test response")
    mock.get_service.return_value = mock_chat_service
    
    # Mock the function registry
    mock.register_function = MagicMock()
    
    return mock
```

### Mocking FastAPI Dependencies

The API tests mock the FastAPI dependency injection:

```python
def test_query(self, client, mock_runtime):
    """Test that the query endpoint works."""
    # Override the get_runtime dependency
    app.dependency_overrides[get_runtime] = lambda: mock_runtime
    
    try:
        response = client.post("/api/query", json={"query": "Test query"})
        assert response.status_code == 200
        # Additional assertions...
    finally:
        # Clean up the override
        app.dependency_overrides.clear()
```

### Mocking CLI Commands

The CLI tests use Click's test runner to simulate command execution:

```python
def test_cli_query(self, runner):
    """Test that the CLI query command works."""
    with patch("cli.runtime.send_query") as mock_send_query:
        mock_send_query.return_value = {"content": "Test response"}
        
        # Run the CLI command
        result = runner.invoke(cli, ["query", "Test query"])
        
        # Check that the command was successful
        assert result.exit_code == 0
        assert "Test response" in result.output
```

## Testing Streaming Responses

Testing streaming responses requires special handling:

```python
@pytest.mark.asyncio
async def test_stream_process_query(self, runtime, mock_kernel):
    """Test that stream_process_query streams responses correctly."""
    # Mock the streaming functionality
    mock_chat_service = MagicMock()
    mock_chat_service.get_streaming_chat_message_contents = AsyncMock(side_effect=Exception("Test error"))
    mock_kernel.get_service.return_value = mock_chat_service
    
    # Process a query
    chunks = []
    async for chunk in runtime.stream_process_query("Test query", "test-conversation"):
        chunks.append(chunk)
    
    # Check the chunks
    assert len(chunks) >= 2
    assert chunks[0]["chunk"] == "Processing with Semantic Kernel..."
    assert chunks[0]["complete"] is False
    assert chunks[-1]["complete"] is True
```

## Current Warnings and How to Fix Them

The test suite previously showed two types of warnings that have now been fixed:

### 1. Coroutine Warnings in Streaming Tests (FIXED)

These warnings occurred in the `test_stream_process_query` and `test_stream_process_query_error` tests. They were related to how we mocked the streaming functionality in Semantic Kernel.

**Root Cause**: In the `runtime/agent_runtime.py` file, there was an `async for` loop that iterated over the result of `chat_service.get_streaming_chat_message_contents()`. Our mock implementation didn't properly handle the async iteration protocol.

**Fix Applied**: The `stream_process_query` method in `agent_runtime.py` was modified to properly handle both async iterators and coroutines:

```python
# Get the streaming content
streaming_content = chat_service.get_streaming_chat_message_contents(
    chat_history=chat_history,
    settings=settings,
    kernel=self.kernel
)

# Check if it's an async iterator or a coroutine
if hasattr(streaming_content, '__aiter__'):
    # It's an async iterator, use async for
    async for chunk in streaming_content:
        # ... process chunk ...
else:
    # It's a coroutine, await it and then process
    result_chunks = await streaming_content
    # ... process result ...
```

### 2. Pytest-Asyncio Configuration Warning (FIXED)

```
PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
```

This warning was related to the pytest-asyncio configuration.

**Root Cause**: The warning occurred because we weren't explicitly setting the `asyncio_default_fixture_loop_scope` option in our pytest configuration.

**Fix Applied**: A `pytest.ini` file was created in the project root with:

```ini
[pytest]
asyncio_mode = strict
asyncio_default_fixture_loop_scope = session
```

## Known Issues and Workarounds

There are currently no known issues with the test suite. All tests are passing without warnings.

## Test Coverage

The current test coverage is:

- `runtime/agent_runtime.py`: 66%
- `api/runtime_api.py`: 61%
- `cli/runtime.py`: 32%

Areas that need improved test coverage:

1. Error handling in the API endpoints
2. CLI interactive mode
3. Direct agent calling functionality
4. Streaming response handling

## Adding New Tests

When adding new tests, follow these guidelines:

1. Place tests in the appropriate test module based on what you're testing
2. Use fixtures to set up test environments
3. Mock external dependencies to avoid actual API calls
4. For async tests, use the `@pytest.mark.asyncio` decorator
5. Clean up any resources created during tests

## Continuous Integration

The test suite is designed to be run in a CI environment. When setting up CI, make sure to:

1. Install all dependencies from `requirements.txt`
2. Run tests with coverage reporting
3. Fail the build if test coverage drops below a certain threshold

## Debugging Tests

If a test is failing, you can use the following strategies to debug:

1. Run the specific failing test with the `-v` flag for verbose output
2. Add print statements to see what's happening
3. Use the `--pdb` flag to drop into the debugger on failure:

```bash
python -m pytest tests/test_file.py::TestClass::test_method -v --pdb
```

## Best Practices

1. Keep tests focused on a single functionality
2. Use descriptive test names that explain what's being tested
3. Use fixtures to avoid duplicating setup code
4. Mock external dependencies to make tests faster and more reliable
5. Test both success and error cases
6. Aim for high test coverage, especially for critical functionality 