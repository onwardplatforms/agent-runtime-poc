#!/usr/bin/env python3

import os
import sys
import json
import time
import argparse
import requests
import re
import logging
from typing import Dict, List, Any, Optional
from pprint import pprint
from colorama import init, Fore, Style

# Initialize colorama
init()

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Get logger for our module
cli_logger = logging.getLogger("runtime_cli")
cli_logger.setLevel(logging.WARNING)

RUNTIME_URL = "http://localhost:5003"

def send_query(query: str, user_id: str = "cli-user", conversation_id: Optional[str] = None, verbose: bool = True, max_agents: Optional[int] = None) -> Dict[str, Any]:
    """Send a query to the agent runtime."""
    try:
        payload = {
            "query": query,
            "user_id": user_id,
            "verbose": verbose
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
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}

def send_group_chat_query(query: str, agent_ids: Optional[List[str]] = None, user_id: str = "cli-user", 
                         conversation_id: Optional[str] = None, max_iterations: int = 5, verbose: bool = False) -> Dict[str, Any]:
    """Send a query to the agent runtime's group chat functionality."""
    try:
        payload = {
            "query": query,
            "user_id": user_id,
            "max_iterations": max_iterations,
            "verbose": verbose
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
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error communicating with the runtime's group chat: {e}{Style.RESET_ALL}")
        return {"error": str(e)}

def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Get conversation history for a specific conversation."""
    try:
        response = requests.get(f"{RUNTIME_URL}/api/conversations/{conversation_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error retrieving conversation: {e}{Style.RESET_ALL}")
        return {"error": str(e)}

def list_agents() -> Dict[str, Any]:
    """List all available agents."""
    try:
        response = requests.get(f"{RUNTIME_URL}/api/agents")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error listing agents: {e}{Style.RESET_ALL}")
        return {"error": str(e)}

def check_runtime_status():
    """Check if the runtime API is available."""
    try:
        response = requests.get(RUNTIME_URL)
        response.raise_for_status()
        print(f"{Fore.GREEN}Runtime is available at {RUNTIME_URL}{Style.RESET_ALL}")
        return True
    except requests.exceptions.RequestException:
        print(f"{Fore.RED}Runtime is not available at {RUNTIME_URL}{Style.RESET_ALL}")
        return False

def parse_agent_spec(agent_spec: str) -> Dict[str, Optional[str]]:
    """Parse an agent specification string like 'agent-id:param'.
    
    Returns a dictionary of agent_id -> parameter.
    """
    result = {}
    
    # Split the spec by colon to get agent and parameter
    parts = agent_spec.strip().split(":", 1)
    agent_id = parts[0].strip()
    
    # If there's a parameter, use it, otherwise use None
    param = parts[1].strip() if len(parts) > 1 else None
    
    result[agent_id] = param
    return result

def parse_agents_string(agents_string: str) -> Dict[str, Optional[str]]:
    """Parse a comma-separated list of agent specifications.
    
    Examples:
    - agent-id
    - agent-id:param
    - agent-id1,agent-id2
    - agent-id1:param1,agent-id2:param2
    
    Returns a dictionary of agent_id -> parameter.
    """
    result = {}
    
    # Split the string by commas to get individual agent specs
    parts = agents_string.split(",")
    
    for part in parts:
        agent_spec = parse_agent_spec(part.strip())
        result.update(agent_spec)
    
    return result

def display_execution_trace(trace: List[str]):
    """Display the execution trace in a formatted way."""
    if not trace:
        return
        
    print(f"\n{Fore.CYAN}Execution trace:{Style.RESET_ALL}")
    for entry in trace:
        print(f"{Fore.CYAN}  {entry}{Style.RESET_ALL}")
    print()

def call_agent_directly(agent_specs: Dict[str, Optional[str]] = None):
    """Call one or more agents directly with given specifications."""
    if not agent_specs:
        return
        
    # Get the list of available agents
    agents_response = list_agents()
    if "error" in agents_response:
        print(f"{Fore.RED}Cannot fetch agents from runtime.{Style.RESET_ALL}")
        return
    
    available_agents = {agent["id"]: agent for agent in agents_response.get("agents", [])}
    
    # Filter to only specified agents that exist
    agent_ids = []
    queries = {}
    
    for agent_id, param in agent_specs.items():
        if agent_id in available_agents:
            agent_ids.append(agent_id)
            
            # Generate an appropriate query
            if param:
                queries[agent_id] = f"Use parameter: {param}"
            else:
                queries[agent_id] = "Default query"
                
    if not agent_ids:
        print(f"{Fore.RED}No matching agents found for {list(agent_specs.keys())}.{Style.RESET_ALL}")
        return
    
    # Call each agent in sequence
    all_responses = []
    for agent_id in agent_ids:
        agent = available_agents[agent_id]
        query = queries.get(agent_id, "Default query")
        
        print(f"{Fore.YELLOW}Calling {agent['name']} with query: '{query}'{Style.RESET_ALL}")
        
        try:
            # First try using the runtime API if available
            if check_runtime_status():
                # Filter for this specific agent by setting agent_ids
                result = send_group_chat_query(query, agent_ids=[agent_id])
                if "error" not in result:
                    content = result.get("content", "No response")
                    all_responses.append(content)
                    print(f"{Fore.GREEN}Response: {content}{Style.RESET_ALL}")
                    continue
            
            # Fall back to direct API call if runtime is not available or returned an error
            endpoint = agent["endpoint"]
            request_data = {
                "messageId": "cli-msg-" + str(int(time.time())),
                "conversationId": "cli-conv-direct",
                "senderId": "cli-user",
                "recipientId": agent_id,
                "content": query,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "type": 0 if agent_id == "goodbye-agent" else "Text"  # Special case handling
            }
            
            response = requests.post(
                endpoint,
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("content", "No response")
            all_responses.append(content)
            print(f"{Fore.GREEN}Response: {content}{Style.RESET_ALL}")
            
        except Exception as e:
            error_msg = f"Error calling {agent['name']}: {str(e)}"
            print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
            all_responses.append(f"Error: {error_msg}")
    
    if len(all_responses) > 1:
        print(f"\n{Fore.GREEN}Combined response: {' '.join(all_responses)}{Style.RESET_ALL}")

def interactive_mode():
    """Start an interactive CLI session."""
    print(f"\n{Fore.CYAN}=== Agent Runtime CLI ==={Style.RESET_ALL}")
    print("Type your commands below. Special commands:")
    print(f"  {Fore.YELLOW}exit{Style.RESET_ALL} - Exit the CLI")
    print(f"  {Fore.YELLOW}status{Style.RESET_ALL} - Check the runtime status")
    print(f"  {Fore.YELLOW}agents{Style.RESET_ALL} - List available agents")
    print(f"  {Fore.YELLOW}direct <agent-id>[:<param>][,<agent-id>[:<param>]...]{Style.RESET_ALL} - Call specific agent(s) directly")
    print(f"  {Fore.YELLOW}group <agent-id1>[,<agent-id2>,...] <query>{Style.RESET_ALL} - Use group chat with specific agents")
    
    # Check runtime status at startup
    runtime_available = check_runtime_status()
    
    # Generate a conversation ID for this session
    conversation_id = f"cli-{int(time.time())}"
    print(f"{Fore.CYAN}Starting new conversation: {conversation_id}{Style.RESET_ALL}")
    
    while True:
        try:
            user_input = input(f"\n{Fore.GREEN}> {Style.RESET_ALL}").strip()
            
            # Process exit command
            if user_input.lower() == "exit":
                print(f"{Fore.CYAN}Exiting CLI. Goodbye!{Style.RESET_ALL}")
                break
                
            # Check runtime status
            elif user_input.lower() == "status":
                runtime_available = check_runtime_status()
                
            # List available agents
            elif user_input.lower() == "agents":
                if runtime_available:
                    agents = list_agents()
                    if "agents" in agents:
                        print(f"{Fore.CYAN}Available agents:{Style.RESET_ALL}")
                        for agent in agents["agents"]:
                            capabilities = ", ".join(agent.get("capabilities", []))
                            print(f"  {Fore.YELLOW}{agent['id']}{Style.RESET_ALL} - {agent['name']}: {agent['description']}")
                            print(f"    Capabilities: {capabilities}")
                    else:
                        print(f"{Fore.RED}Error retrieving agents: {agents.get('error', 'Unknown error')}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Runtime is not available. Cannot list agents.{Style.RESET_ALL}")
            
            # Process direct agent call
            elif user_input.lower().startswith("direct "):
                parts = user_input.split(" ", 1)
                if len(parts) == 2:
                    agent_specs_str = parts[1].strip()
                    agent_specs = parse_agents_string(agent_specs_str)
                    call_agent_directly(agent_specs)
                else:
                    print(f"{Fore.RED}Please specify agent(s) to call directly.{Style.RESET_ALL}")
                    
            # Process group chat
            elif user_input.lower().startswith("group "):
                parts = user_input.split(" ", 2)
                if len(parts) == 3:
                    agents_str = parts[1].strip()
                    query = parts[2].strip()
                    
                    # Parse agent IDs
                    agent_specs = parse_agents_string(agents_str)
                    agent_ids = list(agent_specs.keys())
                    
                    if runtime_available:
                        result = send_group_chat_query(query, agent_ids=agent_ids, conversation_id=conversation_id, verbose=True)
                        
                        if "error" not in result:
                            print(f"{Fore.GREEN}Response: {result.get('content', 'No response')}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}Error: {result.get('error', 'Unknown error')}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Runtime is not available. Cannot use group chat.{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Please specify agents and query for group chat.{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}Example: group hello-agent,goodbye-agent What's the weather?{Style.RESET_ALL}")
                    
            # Process history command
            elif user_input.lower() == "history":
                if runtime_available:
                    try:
                        response = requests.get(f"{RUNTIME_URL}/api/conversations/{conversation_id}")
                        response.raise_for_status()
                        history = response.json()
                        
                        if "messages" in history:
                            print(f"{Fore.CYAN}Conversation history:{Style.RESET_ALL}")
                            for msg in history["messages"]:
                                role = msg.get("role", "unknown")
                                content = msg.get("content", "No content")
                                timestamp = msg.get("timestamp", "Unknown time")
                                
                                if role == "user":
                                    print(f"{Fore.GREEN}User ({timestamp}): {content}{Style.RESET_ALL}")
                                elif role == "assistant":
                                    print(f"{Fore.BLUE}Assistant ({timestamp}): {content}{Style.RESET_ALL}")
                                    if "execution_trace" in msg and msg["execution_trace"]:
                                        display_execution_trace(msg["execution_trace"])
                        else:
                            print(f"{Fore.YELLOW}No conversation history found.{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}Error retrieving conversation history: {e}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Runtime is not available. Cannot retrieve history.{Style.RESET_ALL}")
            
            # Regular query to the runtime
            elif runtime_available and user_input:
                print(f"{Fore.YELLOW}Sending query to the runtime...{Style.RESET_ALL}")
                result = send_query(user_input, conversation_id=conversation_id, verbose=True)
                
                if "error" in result:
                    print(f"{Fore.RED}{result['error']}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.GREEN}Response: {result.get('content', 'No response')}{Style.RESET_ALL}")
                    if "selected_agents" in result:
                        agents_used = result["selected_agents"]
                        print(f"{Fore.CYAN}Agents used: {', '.join(agents_used)}{Style.RESET_ALL}")
                    if "execution_trace" in result:
                        display_execution_trace(result["execution_trace"])
                        
            elif not runtime_available and user_input:
                print(f"{Fore.RED}Cannot process query: Runtime is not available.{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Try using 'direct <agent-id>' to call agents directly.{Style.RESET_ALL}")
                
        except KeyboardInterrupt:
            print(f"\n{Fore.CYAN}Exiting CLI. Goodbye!{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

def main():
    """Process command line arguments and execute appropriate action."""
    parser = argparse.ArgumentParser(description="CLI for the Agent Runtime")
    
    parser.add_argument("-i", "--interactive", action="store_true", 
                        help="Start interactive CLI mode")
    
    parser.add_argument("-q", "--query", type=str,
                        help="Send a single query to the runtime")
    
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output with execution traces")
    
    parser.add_argument("-c", "--conversation", type=str,
                        help="Specify a conversation ID")
    
    parser.add_argument("-a", "--agent", type=str,
                        help="Call a specific agent directly by ID")
    
    parser.add_argument("-p", "--param", type=str,
                        help="Parameter to pass to the agent when using -a/--agent")
    
    parser.add_argument("--group", type=str, nargs=2, metavar=("AGENTS", "QUERY"),
                        help="Use group chat with specific agents (comma-separated) and query")
                        
    args = parser.parse_args()
    
    # Handle group chat
    if args.group:
        agents_str = args.group[0]
        query = args.group[1]
        
        # Parse agent IDs
        agent_specs = parse_agents_string(agents_str)
        agent_ids = list(agent_specs.keys())
        
        result = send_group_chat_query(query, agent_ids=agent_ids, verbose=args.verbose)
        
        if "error" not in result:
            print(f"Response: {result.get('content', 'No response')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        return
    
    # Handle direct agent call
    if args.agent:
        agent_id = args.agent
        param = args.param
        
        agent_specs = {agent_id: param}
        call_agent_directly(agent_specs)
        return
    
    # Handle single query
    if args.query:
        result = send_query(
            args.query, 
            conversation_id=args.conversation,
            verbose=args.verbose
        )
        
        if "error" not in result:
            print(f"Response: {result.get('content', 'No response')}")
            if args.verbose and "execution_trace" in result:
                display_execution_trace(result["execution_trace"])
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        return
    
    # Default to interactive mode if no other action specified
    if args.interactive or not (args.query or args.agent or args.group):
        interactive_mode()

if __name__ == "__main__":
    main() 