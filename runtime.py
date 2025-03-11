#!/usr/bin/env python3

import os
import sys
import json
import time
import requests
import re
from typing import Dict, List, Any, Optional
from pprint import pprint
import click
from colorama import init, Fore, Style

# Initialize colorama
init()

# Runtime URL
RUNTIME_URL = os.environ.get("RUNTIME_URL", "http://localhost:5003")

def send_query(query: str, user_id: str = "cli-user", conversation_id: Optional[str] = None, verbose: bool = True, max_agents: Optional[int] = None) -> Dict[str, Any]:
    """Send a query to the agent runtime."""
    try:
        click.echo("Sending query to the runtime...")
        
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
        
        # Immediately display agent calls if available
        if "agents_used" in result and result["agents_used"]:
            for agent_id in result["agents_used"]:
                click.echo(f"\n{Fore.YELLOW}ƒ(x) calling the [{agent_id}] agent...{Style.RESET_ALL}")
        
        return result
    except requests.exceptions.RequestException as e:
        click.echo(f"{Fore.RED}Error communicating with the runtime: {e}{Style.RESET_ALL}")
        return {"error": str(e)}

def send_group_chat_query(query: str, agent_ids: Optional[List[str]] = None, user_id: str = "cli-user", 
                         conversation_id: Optional[str] = None, max_iterations: int = 5, verbose: bool = False) -> Dict[str, Any]:
    """Send a query to the agent runtime's group chat functionality."""
    try:
        click.echo("Sending query to the group chat...")
        
        payload = {
            "query": query,
            "user_id": user_id,
            "max_iterations": max_iterations,
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
        
        # Immediately display agent calls if available
        if "agents_used" in result and result["agents_used"]:
            for agent_id in result["agents_used"]:
                click.echo(f"\n{Fore.YELLOW}ƒ(x) calling the [{agent_id}] agent...{Style.RESET_ALL}")
        
        return result
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
        click.echo(f"\n{Fore.CYAN}Calling agent: {agent_id}{Style.RESET_ALL}")
        
        # Get agent endpoint
        endpoint = None
        if agent_id in agents_info:
            endpoint = agents_info[agent_id]["endpoint"]
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
        
        # Prepare message content
        content = param if param else "Hello"
        
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
            click.echo(f"Sending to {endpoint}: {content}")
            response = requests.post(endpoint, json=message)
            response.raise_for_status()
            result = response.json()
            
            # Display response
            click.echo(f"\n{Fore.GREEN}Response from {agent_id}:{Style.RESET_ALL}")
            click.echo(f"{result.get('content', 'No content')}")
            
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
            # Get user input
            user_input = click.prompt("> ", type=str, show_default=False)
            
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
                        click.echo(f"Starting group chat with agents: {', '.join(agent_ids)}")
                        result = send_group_chat_query(query, agent_ids=agent_ids)
                        
                        if "error" not in result:
                            click.echo(f"\n{Fore.GREEN}Response:{Style.RESET_ALL}")
                            click.echo(result.get("content", "No response"))
                    else:
                        click.echo(f"{Fore.RED}Cannot process group chat: Runtime is not available.{Style.RESET_ALL}")
                else:
                    click.echo(f"{Fore.RED}Invalid group chat command format. Use: group <agent-id1>[,<agent-id2>,...] <query>{Style.RESET_ALL}")
                    
            # Process regular query
            elif runtime_available and user_input:
                result = send_query(user_input)
                
                if "error" not in result:
                    click.echo(f"\n{Fore.GREEN}Response:{Style.RESET_ALL}")
                    click.echo(result.get("content", "No response"))
                else:
                    click.echo(f"{Fore.RED}Error: {result.get('error')}{Style.RESET_ALL}")
                        
            elif not runtime_available and user_input:
                click.echo(f"{Fore.RED}Cannot process query: Runtime is not available.{Style.RESET_ALL}")
                click.echo(f"{Fore.YELLOW}Try using 'direct <agent-id>' to call agents directly.{Style.RESET_ALL}")
                
        except KeyboardInterrupt:
            click.echo(f"\n{Fore.CYAN}Exiting CLI. Goodbye!{Style.RESET_ALL}")
            break
        except Exception as e:
            click.echo(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

@click.group()
@click.option('--debug/--no-debug', default=False, help='Enable debug mode with verbose logging')
@click.pass_context
def cli(ctx, debug):
    """Agent Runtime CLI - Interact with the agent runtime system."""
    # Set up the context object
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug

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
    result = send_query(query, conversation_id=conversation_id)
    
    if "error" not in result:
        click.echo(f"\n{Fore.GREEN}Response:{Style.RESET_ALL}")
        click.echo(result.get("content", "No response"))
    else:
        click.echo(f"{Fore.RED}Error: {result.get('error')}{Style.RESET_ALL}")

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
        result = send_group_chat_query(query, agent_ids=agent_ids)
        
        if "error" not in result:
            click.echo(f"\n{Fore.GREEN}Response:{Style.RESET_ALL}")
            click.echo(result.get("content", "No response"))
        else:
            click.echo(f"{Fore.RED}Error: {result.get('error')}{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}Invalid agent specification. Use comma-separated agent IDs.{Style.RESET_ALL}")

@cli.command()
def agents():
    """List available agents."""
    agents_response = list_agents()
    if "error" not in agents_response:
        click.echo(f"\nAvailable Agents:")
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
        click.echo(f"Runtime is not available.")

if __name__ == "__main__":
    cli(obj={}) 