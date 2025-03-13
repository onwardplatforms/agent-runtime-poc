#!/usr/bin/env python3

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

import click
import requests
from colorama import Fore, Style, init

# Initialize colorama
init()

# Runtime URL
RUNTIME_URL = os.environ.get("RUNTIME_URL", "http://localhost:5003")

# Debug flag
DEBUG = False


def set_debug_mode(debug: bool):
    """Set the debug mode for both CLI and runtime."""
    global DEBUG
    DEBUG = debug
    # Set environment variable for the runtime
    os.environ["AGENT_RUNTIME_DEBUG"] = "true" if debug else "false"
    if debug:
        click.echo(f"{Fore.YELLOW}Debug mode enabled{Style.RESET_ALL}")


def send_query(query: str, user_id: str = "cli-user", conversation_id: Optional[str] = None, verbose: bool = True, max_agents: Optional[int] = None) -> Dict[str, Any]:
    """Send a query to the agent runtime."""
    try:
        payload = {
            "query": query,
            "user_id": user_id,
            "verbose": True  # Always set to True to get agent information
        }

        if conversation_id:
            payload["conversation_id"] = conversation_id

        if max_agents is not None:
            payload["max_agents"] = max_agents

        response = requests.post(
            f"{RUNTIME_URL}/api/query",
            json=payload
        )
        response.raise_for_status()
        result = response.json()

        # Print agent information if available
        if "agents_used" in result and result["agents_used"]:
            for agent_id in result["agents_used"]:
                click.echo(f"\nƒ(x) calling {agent_id}...")

        # Display the response
        if "content" in result:
            click.echo(f"\nruntime → {result['content']}\n")

        return result
    except requests.exceptions.RequestException as e:
        click.echo(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}


def send_streaming_query(query: str, user_id: str = "cli-user", conversation_id: Optional[str] = None, verbose: bool = True, max_agents: Optional[int] = None) -> Dict[str, Any]:
    """Send a query to the agent runtime with streaming enabled."""
    try:
        payload = {
            "query": query,
            "user_id": user_id,
            "verbose": True,  # Always set to True to get agent information
            "stream": True    # Enable streaming
        }

        if conversation_id:
            payload["conversation_id"] = conversation_id

        if max_agents is not None:
            payload["max_agents"] = max_agents

        # Don't display the user query again since it's already displayed in the prompt
        # click.echo(f"\nyou → {query}")

        # Use stream=True to get the response as it comes
        with requests.post(
            f"{RUNTIME_URL}/api/query",
            json=payload,
            stream=True
        ) as response:
            response.raise_for_status()

            # Initialize variables to store the complete response
            complete_response = ""
            agents_used = []
            result_conversation_id = conversation_id
            processing_time = None

            # Track current agent info and response
            current_agent_id = None
            current_agent_response = ""

            # Process the streaming response
            for line in response.iter_lines():
                if not line:
                    continue

                # Remove the "data: " prefix and parse the JSON
                if line.startswith(b'data: '):
                    data_str = line[6:].decode('utf-8')

                    # Check if it's the end marker
                    if data_str == "[DONE]":
                        break

                    # Print raw data for debugging
                    if DEBUG:
                        click.echo(f"\n{Fore.MAGENTA}DEBUG RAW DATA: {data_str}{Style.RESET_ALL}")

                    try:
                        data = json.loads(data_str)

                        # Skip any debug messages or internal status updates
                        if isinstance(data, dict) and "chunk" in data and isinstance(data["chunk"], str) and data["chunk"].startswith("DEBUG:"):
                            continue

                        # Handle different types of chunks
                        if "content" in data:
                            # Text content chunk - accumulate for final display
                            chunk = data["content"]
                            if chunk:
                                complete_response += chunk
                        elif "chunk" in data:
                            # Skip internal status messages
                            if data["chunk"] in ["Starting streaming response...", "Processing with Semantic Kernel...", "Streaming complete"] or data["chunk"] is None:
                                # Check if this is the final response
                                if data.get("complete", False) and "response" in data:
                                    complete_response = data["response"]
                                    if "conversation_id" in data:
                                        result_conversation_id = data["conversation_id"]
                                    if "processing_time" in data:
                                        processing_time = data["processing_time"]
                                    if "agents_used" in data and data["agents_used"]:
                                        agents_used = data["agents_used"]
                                continue

                            # Object chunk
                            if data.get("complete", False):
                                # Final response object
                                if "response" in data:
                                    complete_response = data["response"]
                                if "conversation_id" in data:
                                    result_conversation_id = data["conversation_id"]
                                if "processing_time" in data:
                                    processing_time = data["processing_time"]
                                if "agents_used" in data and data["agents_used"]:
                                    agents_used = data["agents_used"]
                            else:
                                # Regular chunk - collect but don't display immediately
                                chunk = data["chunk"]
                                if chunk and not chunk.startswith("DEBUG:"):
                                    complete_response += chunk

                        # Handle agent calls in the desired format
                        if "agent_call" in data:
                            agent_id = data["agent_call"]
                            current_agent_id = agent_id
                            current_agent_response = ""
                            
                            # Display the query sent to the agent in the desired format
                            if "agent_query" in data:
                                click.echo(f"\nruntime to {agent_id} → {data['agent_query']}")
                                sys.stdout.flush()

                        # Handle agent responses in the desired format
                        if "agent_response" in data and "agent_id" in data:
                            agent_id = data["agent_id"]
                            response_text = data["agent_response"]
                            
                            if response_text:
                                # Only update the current_agent_id if different
                                if agent_id != current_agent_id:
                                    if current_agent_response:
                                        # Print any accumulated response from previous agent
                                        click.echo(f"\n{current_agent_id} to runtime → {current_agent_response}")
                                        sys.stdout.flush()
                                    current_agent_id = agent_id
                                    current_agent_response = ""

                                # Append to current agent response
                                current_agent_response += response_text
                                
                                # Check if we should display the accumulated response
                                # Display on sentence endings, line breaks, or if we've accumulated a lot
                                if (response_text.endswith('.') or 
                                    response_text.endswith('!') or 
                                    response_text.endswith('?') or
                                    '\n' in response_text or
                                    len(current_agent_response) > 100):
                                    click.echo(f"\n{agent_id} to runtime → {current_agent_response}")
                                    sys.stdout.flush()
                                    current_agent_response = ""

                        # Handle error
                        if "error" in data:
                            click.echo(f"\n{Fore.RED}Error: {data['error']}{Style.RESET_ALL}")
                            sys.stdout.flush()
                            return {"error": data["error"]}
                    except json.JSONDecodeError as e:
                        if verbose:
                            click.echo(f"\n{Fore.RED}Error parsing streaming response: {e}{Style.RESET_ALL}")
                            sys.stdout.flush()

            # Display any remaining agent response
            if current_agent_response:
                click.echo(f"\n{current_agent_id} to runtime → {current_agent_response}")
                sys.stdout.flush()

            # Display the final response
            if complete_response:
                click.echo(f"\nruntime to you → {complete_response.strip()}")
                sys.stdout.flush()

            # Return the complete response
            return {
                "content": complete_response,
                "conversation_id": result_conversation_id,
                "processing_time": processing_time,
                "agents_used": agents_used
            }
    except requests.exceptions.RequestException as e:
        click.echo(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}


def send_group_chat_query(query: str, agent_ids: Optional[List[str]] = None, user_id: str = "cli-user",
                          conversation_id: Optional[str] = None, max_iterations: int = 5, verbose: bool = False) -> Dict[str, Any]:
    """Send a query to the agent runtime group chat."""
    try:
        payload = {
            "query": query,
            "user_id": user_id,
            "verbose": True  # Always set to True to get agent information
        }

        if conversation_id:
            payload["conversation_id"] = conversation_id

        if agent_ids:
            payload["agent_ids"] = agent_ids

        response = requests.post(
            f"{RUNTIME_URL}/api/group-chat",
            json=payload
        )
        response.raise_for_status()
        result = response.json()

        # Print agent information if available
        if "agents_used" in result and result["agents_used"]:
            for agent_id in result["agents_used"]:
                click.echo(f"\nƒ(x) calling {agent_id}...")

        # Display the final response
        if "content" in result:
            click.echo(f"\nruntime → {result['content']}")

        return result
    except requests.exceptions.RequestException as e:
        click.echo(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}


def send_streaming_group_chat_query(query: str, agent_ids: Optional[List[str]] = None, user_id: str = "cli-user",
                                    conversation_id: Optional[str] = None, max_iterations: int = 5, verbose: bool = False) -> Dict[str, Any]:
    """Send a query to the agent runtime group chat with streaming enabled."""
    try:
        payload = {
            "query": query,
            "user_id": user_id,
            "verbose": True,  # Always set to True to get agent information
            "stream": True    # Enable streaming
        }

        if conversation_id:
            payload["conversation_id"] = conversation_id

        if agent_ids:
            payload["agent_ids"] = agent_ids

        if max_iterations:
            payload["max_iterations"] = max_iterations

        # Don't display the user query again since it's already displayed in the prompt
        # click.echo(f"\nyou → {query}")
        
        # Force debug to be True for this function to trace the issue
        local_debug = False
        if local_debug:
            click.echo(f"\n{Fore.MAGENTA}DEBUG: Sending payload to {RUNTIME_URL}/api/group-chat{Style.RESET_ALL}")
            click.echo(f"{Fore.MAGENTA}DEBUG: Payload = {json.dumps(payload)}{Style.RESET_ALL}")

        # Use stream=True to get the response as it comes
        with requests.post(
            f"{RUNTIME_URL}/api/group-chat",
            json=payload,
            stream=True
        ) as response:
            response.raise_for_status()
            
            if local_debug:
                click.echo(f"{Fore.MAGENTA}DEBUG: Response status code = {response.status_code}{Style.RESET_ALL}")

            # Initialize variables to store the complete response
            complete_response = ""
            agents_used = []
            result_conversation_id = conversation_id

            # Track current agent info and response
            current_agent_id = None
            current_agent_response = ""

            # Process the streaming response
            for line in response.iter_lines():
                if not line:
                    continue

                # Remove the "data: " prefix and parse the JSON
                if line.startswith(b'data: '):
                    data_str = line[6:].decode('utf-8')
                    
                    if local_debug:
                        click.echo(f"{Fore.MAGENTA}DEBUG: Received data = {data_str}{Style.RESET_ALL}")

                    # Check if it's the end marker
                    if data_str == "[DONE]":
                        if local_debug:
                            click.echo(f"{Fore.MAGENTA}DEBUG: End of stream marker received{Style.RESET_ALL}")
                        break

                    # Print raw data for debugging
                    if DEBUG or local_debug:
                        click.echo(f"\n{Fore.MAGENTA}DEBUG RAW DATA: {data_str}{Style.RESET_ALL}")

                    try:
                        data = json.loads(data_str)

                        # Skip any debug messages or internal status updates
                        if isinstance(data, dict) and "chunk" in data and isinstance(data["chunk"], str) and data["chunk"].startswith("DEBUG:"):
                            continue

                        # Log the data type we received for debugging
                        if local_debug:
                            click.echo(f"{Fore.MAGENTA}DEBUG: Data keys = {list(data.keys())}{Style.RESET_ALL}")

                        # Handle different types of chunks
                        if "content" in data:
                            # Text content chunk - accumulate for final display
                            chunk = data["content"]
                            if chunk and chunk not in ["Starting group chat streaming response...", "Processing with Semantic Kernel...", "Group chat streaming complete"]:
                                complete_response += chunk
                                if local_debug:
                                    click.echo(f"{Fore.MAGENTA}DEBUG: Added content chunk = {chunk}{Style.RESET_ALL}")
                        elif "chunk" in data:
                            # Skip internal status messages
                            if data["chunk"] in ["Starting group chat streaming response...", "Starting streaming response...", "Processing with Semantic Kernel...", "Streaming complete", "Group chat streaming complete"] or data["chunk"] is None:
                                # Check if this is the final response
                                if data.get("complete", False) and "response" in data:
                                    complete_response = data["response"]
                                    if local_debug:
                                        click.echo(f"{Fore.MAGENTA}DEBUG: Final response = {data['response']}{Style.RESET_ALL}")
                                    if "conversation_id" in data:
                                        result_conversation_id = data["conversation_id"]
                                    if "agents_used" in data and data["agents_used"]:
                                        agents_used = data["agents_used"]
                                continue

                            # Object chunk
                            if data.get("complete", False):
                                # Final response object
                                if "response" in data:
                                    complete_response = data["response"]
                                    if local_debug:
                                        click.echo(f"{Fore.MAGENTA}DEBUG: Final response = {data['response']}{Style.RESET_ALL}")
                                if "conversation_id" in data:
                                    result_conversation_id = data["conversation_id"]
                                if "agents_used" in data and data["agents_used"]:
                                    agents_used = data["agents_used"]
                            else:
                                # Regular chunk - accumulated for later display
                                chunk = data["chunk"]
                                if chunk and not chunk.startswith("DEBUG:") and chunk not in ["Starting group chat streaming response...", "Starting streaming response...", "Processing with Semantic Kernel...", "Streaming complete", "Group chat streaming complete"]:
                                    complete_response += chunk
                                    if local_debug:
                                        click.echo(f"{Fore.MAGENTA}DEBUG: Added chunk = {chunk}{Style.RESET_ALL}")

                        # Handle agent calls in the desired format
                        if "agent_call" in data:
                            agent_id = data["agent_call"]
                            current_agent_id = agent_id
                            current_agent_response = ""
                            
                            # Display the query sent to the agent in the desired format
                            if "agent_query" in data:
                                click.echo(f"\nruntime to {agent_id} → {data['agent_query']}")
                                sys.stdout.flush()

                        # Handle agent responses in the desired format
                        if "agent_response" in data and "agent_id" in data:
                            agent_id = data["agent_id"]
                            response_text = data["agent_response"]
                            
                            if local_debug:
                                click.echo(f"{Fore.MAGENTA}DEBUG: Agent response from {agent_id}, text = {response_text}{Style.RESET_ALL}")
                            
                            if response_text:
                                # Only update the current_agent_id if different
                                if agent_id != current_agent_id:
                                    if current_agent_response:
                                        # Print any accumulated response from previous agent
                                        click.echo(f"\n{current_agent_id} to runtime → {current_agent_response}")
                                        sys.stdout.flush()
                                    current_agent_id = agent_id
                                    current_agent_response = ""

                                # Append to current agent response
                                current_agent_response += response_text
                                
                                # Check if we should display the accumulated response
                                # Display on sentence endings, line breaks, or if we've accumulated a lot
                                if (response_text.endswith('.') or 
                                    response_text.endswith('!') or 
                                    response_text.endswith('?') or
                                    '\n' in response_text or
                                    len(current_agent_response) > 100):
                                    click.echo(f"\n{agent_id} to runtime → {current_agent_response}")
                                    sys.stdout.flush()
                                    current_agent_response = ""

                        # Handle error
                        if "error" in data:
                            click.echo(f"\n{Fore.RED}Error: {data['error']}{Style.RESET_ALL}")
                            sys.stdout.flush()
                            return {"error": data["error"]}
                    except json.JSONDecodeError as e:
                        if verbose or local_debug:
                            click.echo(f"\n{Fore.RED}Error parsing streaming response: {e}{Style.RESET_ALL}")
                            sys.stdout.flush()

            # Display any remaining agent response
            if current_agent_response:
                click.echo(f"\n{current_agent_id} to runtime → {current_agent_response}")
                sys.stdout.flush()

            # Display the final response
            if complete_response:
                # Filter out any internal status messages
                filtered_response = complete_response
                for status_msg in ["Starting group chat streaming response...", "Starting streaming response...", "Processing with Semantic Kernel...", "Streaming complete", "Group chat streaming complete"]:
                    filtered_response = filtered_response.replace(status_msg, "")
                
                # Only display if we actually have content
                if filtered_response.strip():
                    click.echo(f"\nruntime to you → {filtered_response.strip()}")
                    sys.stdout.flush()
                elif local_debug:
                    click.echo(f"{Fore.MAGENTA}DEBUG: No final response to display{Style.RESET_ALL}")
                    sys.stdout.flush()

            # Return the complete response
            return {
                "content": complete_response,
                "conversation_id": result_conversation_id,
                "agents_used": agents_used
            }
    except requests.exceptions.RequestException as e:
        click.echo(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}


def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Get conversation history from the runtime."""
    try:
        response = requests.get(f"{RUNTIME_URL}/api/conversations/{conversation_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        click.echo(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}


def list_agents() -> Dict[str, Any]:
    """List available agents from the runtime."""
    try:
        response = requests.get(f"{RUNTIME_URL}/api/agents")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        click.echo(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}


def check_runtime_status():
    """Check if the runtime is available."""
    try:
        response = requests.get(f"{RUNTIME_URL}/")
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


def parse_agent_spec(agent_spec: str) -> Dict[str, Optional[str]]:
    """Parse an agent specification string like 'agent-id:param'."""
    if ":" in agent_spec:
        agent_id, param = agent_spec.split(":", 1)
        return {agent_id: param}
    else:
        return {agent_spec: None}


def parse_agents_string(agents_string: str) -> Dict[str, Optional[str]]:
    """Parse a comma-separated list of agent specifications."""
    agent_specs = {}

    if not agents_string:
        return agent_specs

    for agent_spec in agents_string.split(","):
        agent_spec = agent_spec.strip()
        if not agent_spec:
            continue

        agent_specs.update(parse_agent_spec(agent_spec))

    return agent_specs


def display_execution_trace(trace: List[str]):
    """Display the execution trace in a readable format."""
    if not trace:
        return

    click.echo(f"\n{Fore.CYAN}Execution Trace:{Style.RESET_ALL}")
    for step in trace:
        click.echo(f"  - {step}")


def call_agent_directly(agent_specs: Dict[str, Optional[str]] = None):
    """Call one or more agents directly without going through the runtime."""
    if not agent_specs:
        click.echo(f"{Fore.RED}No agents specified.{Style.RESET_ALL}")
        return

    # First, try to get agent information from the runtime
    agents_info = {}
    runtime_available = check_runtime_status()

    if runtime_available:
        agents_response = list_agents()
        if "error" not in agents_response:
            for agent in agents_response.get("agents", []):
                agents_info[agent["id"]] = agent

    # Process each agent
    for agent_id, param in agent_specs.items():
        content = param if param else "Hello"
        
        # Display the direct call in the conversation format
        click.echo(f"\nyou → {content}")
        click.echo(f"\nruntime to {agent_id} → {content}")

        # Get agent endpoint
        endpoint = None
        if agent_id in agents_info:
            endpoint = agents_info[agent_id]["endpoint"]
            if DEBUG:
                click.echo(f"Agent: {agents_info[agent_id]['name']}")
                click.echo(f"Description: {agents_info[agent_id]['description']}")
                click.echo(f"Capabilities: {', '.join(agents_info[agent_id]['capabilities'])}")

        if not endpoint:
            # Try default endpoints based on agent ID
            if agent_id == "hello-agent":
                endpoint = "http://localhost:5001/api/message"
            elif agent_id == "goodbye-agent":
                endpoint = "http://localhost:5002/api/message"
            else:
                click.echo(f"{Fore.RED}Unknown agent ID and runtime not available to look up endpoint.{Style.RESET_ALL}")
                continue

        # Prepare message payload
        message = {
            "messageId": f"cli-msg-{int(time.time())}",
            "conversationId": f"cli-conv-{int(time.time())}",
            "senderId": "cli-user",
            "recipientId": agent_id,
            "content": content,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "Text" if agent_id != "goodbye-agent" else 0  # Special handling for .NET agent
        }

        # Send request to agent
        try:
            if DEBUG:
                click.echo(f"Sending to {endpoint}: {content}")
                
            response = requests.post(endpoint, json=message)
            response.raise_for_status()
            result = response.json()

            # Display response in the conversation format
            response_content = result.get('content', 'No content')
            click.echo(f"\n{agent_id} to runtime → {response_content}")
            click.echo(f"\nruntime to you → {response_content}")

        except requests.exceptions.RequestException as e:
            click.echo(f"{Fore.RED}Error communicating with agent {agent_id}: {e}{Style.RESET_ALL}")


def interactive_mode():
    """Start an interactive CLI session."""
    click.echo(f"\n{Fore.CYAN}=== Agent Runtime CLI ==={Style.RESET_ALL}\n")
    click.echo("Type your commands below. Special commands:")
    click.echo("  exit - Exit the CLI")
    click.echo("  status - Check the runtime status")
    click.echo("  agents - List available agents")
    click.echo("  direct <agent-id>[:<param>][,<agent-id>[:<param>]...] - Call specific agent(s) directly")
    click.echo("  group <agent-id1>[,<agent-id2>,...] <query> - Use group chat with specific agents")

    # Check runtime status
    runtime_available = check_runtime_status()
    if runtime_available:
        click.echo(f"Runtime is available at {RUNTIME_URL}")
    else:
        click.echo(f"{Fore.YELLOW}Runtime is not available. Some commands may not work.{Style.RESET_ALL}")

    # Generate a conversation ID for this session
    conversation_id = f"cli-{int(time.time())}"
    click.echo(f"Starting new conversation: {conversation_id}\n")

    while True:
        try:
            # Get user input with the new format
            user_input = click.prompt("you → ", type=str, show_default=False, prompt_suffix="")

            # Process special commands
            if user_input.lower() == "exit":
                click.echo(f"{Fore.CYAN}Exiting CLI. Goodbye!{Style.RESET_ALL}")
                break

            elif user_input.lower() == "status":
                runtime_available = check_runtime_status()
                if runtime_available:
                    click.echo(f"{Fore.GREEN}Runtime is available at {RUNTIME_URL}{Style.RESET_ALL}")
                else:
                    click.echo(f"{Fore.RED}Runtime is not available.{Style.RESET_ALL}")

            elif user_input.lower() == "agents":
                if runtime_available:
                    agents_response = list_agents()
                    if "error" not in agents_response:
                        click.echo(f"\n{Fore.CYAN}Available Agents:{Style.RESET_ALL}")
                        for agent in agents_response.get("agents", []):
                            click.echo(f"- {agent['name']} ({agent['id']})")
                            click.echo(f"  Description: {agent['description']}")
                            click.echo(f"  Capabilities: {', '.join(agent['capabilities'])}")
                            click.echo("")
                    else:
                        click.echo(f"{Fore.RED}Error retrieving agents: {agents_response['error']}{Style.RESET_ALL}")
                else:
                    click.echo(f"{Fore.RED}Cannot list agents: Runtime is not available.{Style.RESET_ALL}")

            elif user_input.lower().startswith("direct "):
                # Parse agent specs from the command
                agent_specs_str = user_input[7:].strip()
                agent_specs = parse_agents_string(agent_specs_str)

                if agent_specs:
                    call_agent_directly(agent_specs)
                else:
                    click.echo(f"{Fore.RED}Invalid agent specification. Use: direct <agent-id>[:<param>][,<agent-id>[:<param>]...]{Style.RESET_ALL}")

            elif user_input.lower().startswith("group "):
                # Parse group chat command
                match = re.match(r"group\s+([^\"]+?)\s+(.+)", user_input)
                if match:
                    agents_str = match.group(1).strip()
                    query = match.group(2).strip()

                    # Parse agent IDs
                    agent_ids = [agent_id.strip() for agent_id in agents_str.split(",") if agent_id.strip()]

                    if runtime_available and agent_ids:
                        # No need to echo the query here as the streaming function will do it
                        # Use streaming group chat query
                        result = send_streaming_group_chat_query(query, agent_ids=agent_ids, conversation_id=conversation_id)

                        if "error" in result:
                            click.echo(f"{Fore.RED}Error: {result['error']}{Style.RESET_ALL}")
                            continue

                        # Update conversation ID if it changed
                        if "conversation_id" in result and result["conversation_id"]:
                            conversation_id = result["conversation_id"]
                    else:
                        click.echo(f"{Fore.RED}Cannot process group chat: Runtime is not available.{Style.RESET_ALL}")
                else:
                    click.echo(f"{Fore.RED}Invalid group chat command format. Use: group <agent-id1>[,<agent-id2>,...] <query>{Style.RESET_ALL}")

            # If no special command, treat as a query
            else:
                if not runtime_available:
                    click.echo(f"{Fore.RED}Cannot process query: Runtime is not available.{Style.RESET_ALL}")
                    click.echo(f"{Fore.YELLOW}Try using 'direct <agent-id>' to call agents directly.{Style.RESET_ALL}")
                    continue

                # Don't need to echo user query as it will be handled in the streaming function
                # Use streaming query instead of regular query
                result = send_streaming_query(user_input, conversation_id=conversation_id)

                if "error" in result:
                    click.echo(f"{Fore.RED}Error: {result['error']}{Style.RESET_ALL}")
                    continue

                # Update conversation ID if it changed
                if "conversation_id" in result and result["conversation_id"]:
                    conversation_id = result["conversation_id"]

        except KeyboardInterrupt:
            click.echo(f"\n{Fore.CYAN}Exiting CLI. Goodbye!{Style.RESET_ALL}")
            break
        except Exception as e:
            click.echo(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

    return


@click.group()
@click.option('--debug/--no-debug', default=False, help='Enable debug mode with verbose logging')
@click.pass_context
def cli(ctx, debug):
    """Agent Runtime CLI - Interact with the agent runtime system."""
    # Set up the context object
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug
    set_debug_mode(debug)


@cli.command()
def interactive():
    """Start interactive CLI mode."""
    interactive_mode()


@cli.command()
@click.argument('query', required=True)
@click.option('--conversation-id', '-c', help='Specify a conversation ID')
@click.pass_context
def query(ctx, query, conversation_id):
    """Send a query to the runtime."""
    # Generate a conversation ID if not provided
    if not conversation_id:
        conversation_id = f"cli-{int(time.time())}"
        click.echo(f"Using conversation ID: {conversation_id}")

    result = send_streaming_query(query, conversation_id=conversation_id)

    if "error" in result:
        click.echo(f"{Fore.RED}Error: {result['error']}{Style.RESET_ALL}")
        return


@cli.command()
@click.argument('agent_id', required=True)
@click.argument('param', required=False)
def direct(agent_id, param):
    """Call a specific agent directly."""
    agent_specs = {agent_id: param}
    call_agent_directly(agent_specs)


@cli.command()
@click.argument('agents', required=True)
@click.argument('query', required=True)
def group(agents, query):
    """Use group chat with specific agents."""
    agent_ids = [agent_id.strip() for agent_id in agents.split(",") if agent_id.strip()]

    if agent_ids:
        # Use streaming group chat query
        result = send_streaming_group_chat_query(query, agent_ids=agent_ids)

        if "error" in result:
            click.echo(f"{Fore.RED}Error: {result['error']}{Style.RESET_ALL}")
            return

        # No need to display content as it's already displayed during streaming
    else:
        click.echo(f"{Fore.RED}Invalid agent specification. Use comma-separated agent IDs.{Style.RESET_ALL}")


@cli.command()
def agents():
    """List available agents."""
    agents_response = list_agents()
    if "error" not in agents_response:
        click.echo("\nAvailable Agents:")
        for agent in agents_response.get("agents", []):
            click.echo(f"  {agent['name']} ({agent['id']})")
            click.echo(f"    Description: {agent['description']}")
            click.echo(f"    Capabilities: {', '.join(agent['capabilities'])}")
            click.echo(f"    Endpoint: {agent['endpoint']}")
            click.echo("")
    else:
        click.echo(f"Error: {agents_response.get('error')}")


@cli.command()
def status():
    """Check the runtime status."""
    runtime_available = check_runtime_status()
    if runtime_available:
        click.echo(f"Runtime is available at {RUNTIME_URL}")
    else:
        click.echo("Runtime is not available.")


if __name__ == "__main__":
    cli(obj={})
