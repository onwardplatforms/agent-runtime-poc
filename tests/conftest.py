#!/usr/bin/env python3

import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure pytest-asyncio to use session scope for event loops


def pytest_configure(config):
    """Configure pytest-asyncio to use session scope for event loops."""
    config.option.asyncio_default_fixture_loop_scope = "session"

# No need to define a custom event_loop fixture anymore
# The built-in one from pytest-asyncio will be used with the configured scope
