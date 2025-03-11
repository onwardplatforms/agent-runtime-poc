#!/usr/bin/env python3

import sys
import os
import argparse

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the CLI from the cli module
from cli.runtime import cli, group

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Agent Runtime CLI")
    parser.add_argument("--group", type=str, help="Use group chat with specific agents (comma-separated)")
    parser.add_argument("--query", type=str, help="Query to send")
    
    args, remaining = parser.parse_known_args()
    
    # If --group and --query are provided, use group chat
    if args.group and args.query:
        # Call the group command directly
        ctx = cli.make_context('cli', ['group', args.group, args.query])
        cli.invoke(ctx)
    else:
        # Call the CLI with the command line arguments
        cli() 