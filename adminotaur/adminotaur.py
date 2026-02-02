#!/usr/bin/env python3
"""
Adminotaur - LangGraph Supervisor Agent
Coordinates worker agents and manages MCP skills for Decyphertek.ai
"""

import os
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from pathlib import Path
import glob
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool


# Global MCP Gateway configuration
MCP_HOST = "localhost"
MCP_PORT = 9000


@tool
def invoke_mcp_skill(skill: str, tool_name: str, params: dict) -> str:
    """Call MCP Gateway to invoke a skill.
    
    Args:
        skill: Name of the MCP skill (e.g., 'openrouter-ai', 'rag-chat')
        tool_name: Name of the tool within the skill (e.g., 'chat_completion')
        params: Parameters to pass to the tool
        
    Returns:
        Response content from MCP Gateway skill
    """
    try:
        request_data = {
            "skill": skill,
            "tool": tool_name,
            "params": params
        }
        url = f"http://{MCP_HOST}:{MCP_PORT}/invoke"
        
        req = urllib.request.Request(
            url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            # Extract the actual response content
            if isinstance(result, dict):
                return result.get("response", result.get("content", str(result)))
            return str(result)
    except Exception as e:
        return f"Error calling MCP Gateway: {str(e)}"


@tool
def check_system_health() -> str:
    """Check Decyphertek.ai system health.
    
    Returns:
        System health status report
    """
    app_dir = Path.home() / ".decyphertek.ai"
    checks = {
        "app_directory": app_dir.exists(),
        "agent_store": (app_dir / "agent-store").exists(),
        "mcp_store": (app_dir / "mcp-store").exists(),
        "app_store": (app_dir / "app-store").exists(),
        "configs": (app_dir / "configs").exists(),
        "creds": (app_dir / "creds").exists(),
    }
    
    status = "System Health Check:\n"
    for component, healthy in checks.items():
        status += f"  - {component}: {'✓ OK' if healthy else '✗ MISSING'}\n"
    
    all_healthy = all(checks.values())
    status += f"\nOverall Status: {'✓ All systems operational' if all_healthy else '✗ Issues detected'}"
    
    return status


@tool
def list_available_agents() -> str:
    """List all available agent workers in the agent store.
    
    Returns:
        Comma-separated list of agent names
    """
    agent_store_dir = Path.home() / ".decyphertek.ai" / "agent-store"
    if not agent_store_dir.exists():
        return "No agent-store directory found"
    
    agents = [item.name for item in agent_store_dir.iterdir() if item.is_dir()]
    
    if not agents:
        return "No agent workers found"
    
    return f"Available agent workers: {', '.join(agents)}"


@tool
def list_mcp_skills() -> str:
    """List all available MCP skills in the MCP store.
    
    Returns:
        Comma-separated list of skill names
    """
    mcp_store_dir = Path.home() / ".decyphertek.ai" / "mcp-store"
    if not mcp_store_dir.exists():
        return "No mcp-store directory found"
    
    skills = [item.name for item in mcp_store_dir.iterdir() if item.is_dir()]
    
    if not skills:
        return "No MCP skills found"
    
    return f"Available MCP skills: {', '.join(skills)}"


class AgentState(TypedDict):
    """State for the supervisor agent graph"""
    messages: Annotated[List, operator.add]
    next: str


class Adminotaur:
    """
    LangGraph-based supervisor agent for Decyphertek.ai
    Uses StateGraph to coordinate worker agents and MCP skills
    """
    
    def __init__(self):
        """
        Initialize Adminotaur supervisor agent
        Routes all AI calls to MCP Gateway
        """
        self.app_dir = Path.home() / ".decyphertek.ai"
        self.agent_store_dir = self.app_dir / "agent-store"
        self.mcp_store_dir = self.app_dir / "mcp-store"
        self.app_store_dir = self.app_dir / "app-store"
        self.configs_dir = self.app_dir / "configs"
        
        # Load configurations
        self.slash_commands = self._load_slash_commands()
        self.ai_config = self._load_ai_config()
        self.context_data = self._load_context_files()
        
        # MCP Gateway connection
        self.mcp_gateway_host = self.ai_config.get("mcp_gateway", {}).get("host", "localhost")
        self.mcp_gateway_port = self.ai_config.get("mcp_gateway", {}).get("port", 9000)
        
        # Update global MCP config for @tool functions
        global MCP_HOST, MCP_PORT
        MCP_HOST = self.mcp_gateway_host
        MCP_PORT = self.mcp_gateway_port
        
        # Build LangGraph workflow
        self.graph = self._build_graph()
        
    def _load_slash_commands(self) -> Dict[str, Any]:
        """Load slash commands configuration"""
        config_file = self.configs_dir / "slash-commands.json"
        if config_file.exists():
            return json.loads(config_file.read_text())
        return {"commands": {}}
    
    def _load_ai_config(self) -> Dict[str, Any]:
        """Load AI provider configuration"""
        config_file = self.configs_dir / "ai-config.json"
        if config_file.exists():
            return json.loads(config_file.read_text())
        return {}
    
    def _load_context_files(self) -> Dict[str, str]:
        """Load context from JSON and MD files for self-awareness"""
        context = {}
        
        # Load registry files
        registries = [
            self.agent_store_dir / "workers.json",
            self.mcp_store_dir / "skills.json",
            self.app_store_dir / "app.json"
        ]
        
        for registry in registries:
            if registry.exists():
                context[str(registry)] = registry.read_text()
        
        # Load markdown docs
        md_patterns = [
            str(self.agent_store_dir / "**/*.md"),
            str(self.mcp_store_dir / "**/*.md"),
            str(self.app_store_dir / "**/*.md")
        ]
        
        for pattern in md_patterns:
            for md_file in glob.glob(pattern, recursive=True):
                md_path = Path(md_file)
                if md_path.exists():
                    context[str(md_path)] = md_path.read_text()
        
        return context
    
    def _call_mcp_gateway(self, request: str) -> str:
        """Call MCP Gateway to invoke skills"""
        try:
            request_data = json.loads(request) if isinstance(request, str) else request
            url = f"http://{self.mcp_gateway_host}:{self.mcp_gateway_port}/invoke"
            
            req = urllib.request.Request(
                url,
                data=json.dumps(request_data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return json.dumps(result, indent=2)
        
        except Exception as e:
            return f"Error calling MCP Gateway: {str(e)}"
    
    def _list_agent_workers(self, query: str = "") -> str:
        """List available agent workers"""
        if not self.agent_store_dir.exists():
            return "No agent-store directory found"
        
        agents = []
        for item in self.agent_store_dir.iterdir():
            if item.is_dir():
                agents.append(item.name)
        
        if not agents:
            return "No agent workers found"
        
        return f"Available agent workers: {', '.join(agents)}"
    
    def _list_mcp_skills(self, query: str = "") -> str:
        """List available MCP skills"""
        if not self.mcp_store_dir.exists():
            return "No mcp-store directory found"
        
        skills = []
        for item in self.mcp_store_dir.iterdir():
            if item.is_dir():
                skills.append(item.name)
        
        if not skills:
            return "No MCP skills found"
        
        return f"Available MCP skills: {', '.join(skills)}"
    
    def _system_health_check(self, query: str = "") -> str:
        """Perform system health check"""
        checks = {
            "app_directory": self.app_dir.exists(),
            "agent_store_directory": self.agent_store_dir.exists(),
            "mcp_store_directory": self.mcp_store_dir.exists(),
            "app_store_directory": self.app_store_dir.exists(),
            "configs_directory": self.configs_dir.exists(),
            "creds_directory": (self.app_dir / "creds").exists(),
        }
        
        status = "System Health Check:\n"
        for component, healthy in checks.items():
            status += f"  - {component}: {'✓ OK' if healthy else '✗ MISSING'}\n"
        
        all_healthy = all(checks.values())
        status += f"\nOverall Status: {'✓ All systems operational' if all_healthy else '✗ Issues detected'}"
        
        return status
    
    def _get_agent_info(self, agent_name: str) -> str:
        """Get information about a specific agent"""
        agent_path = self.agent_store_dir / agent_name
        
        if not agent_path.exists():
            return f"Agent '{agent_name}' not found"
        
        info = f"Agent: {agent_name}\n"
        info += f"Path: {agent_path}\n"
        
        if agent_path.is_dir():
            files = list(agent_path.iterdir())
            info += f"Files: {len(files)}\n"
            for f in files:
                info += f"  - {f.name}\n"
        
        return info
    
    def route_request(self, user_input: str) -> str:
        """
        Route user request based on slash commands or default AI
        
        Args:
            user_input: User's request or query
            
        Returns:
            Routed response
        """
        # Check for slash commands
        if user_input.startswith("/"):
            return self._handle_slash_command(user_input)
        
        # Default routing to OpenRouter AI via MCP Gateway
        return self._route_to_ai(user_input)
    
    def _handle_slash_command(self, user_input: str) -> str:
        """Handle slash command routing"""
        parts = user_input.split(" ", 1)
        command = parts[0]
        query = parts[1] if len(parts) > 1 else ""
        
        commands = self.slash_commands.get("commands", {})
        
        if command not in commands:
            return f"Unknown command: {command}\nUse /help to see available commands"
        
        cmd_config = commands[command]
        
        # Handle builtin commands
        if cmd_config.get("builtin"):
            return self._handle_builtin_command(command, query)
        
        # Handle MCP skill commands
        if "mcp_skill" in cmd_config:
            return self._route_to_skill(cmd_config, query)
        
        return "Command not implemented"
    
    def _handle_builtin_command(self, command: str, query: str) -> str:
        """Handle builtin slash commands"""
        if command == "/help":
            return self._show_help()
        elif command == "/status":
            return self._system_health_check()
        elif command == "/config":
            return self._show_config()
        return "Unknown builtin command"
    
    def _show_help(self) -> str:
        """Show available commands"""
        commands = self.slash_commands.get("commands", {})
        help_text = "Available Commands:\n\n"
        for cmd, config in commands.items():
            if config.get("enabled", True):
                help_text += f"{cmd}: {config.get('description', 'No description')}\n"
        return help_text
    
    def _show_config(self) -> str:
        """Show current configuration"""
        config_text = "Current Configuration:\n\n"
        config_text += f"AI Provider: {self.ai_config.get('default_provider', 'Not set')}\n"
        config_text += f"MCP Gateway: {self.mcp_gateway_host}:{self.mcp_gateway_port}\n"
        config_text += f"Slash Commands: {len(self.slash_commands.get('commands', {}))} loaded\n"
        return config_text
    
    def _route_to_skill(self, cmd_config: Dict[str, Any], query: str) -> str:
        """Route request to MCP skill via gateway"""
        skill_name = cmd_config.get("mcp_skill")
        tools = cmd_config.get("tools", [])
        
        # Call first tool with query
        if tools:
            request = {
                "skill": skill_name,
                "tool": tools[0],
                "params": {"query": query}
            }
            return self._call_mcp_gateway(json.dumps(request))
        
        return f"No tools configured for skill: {skill_name}"
    
    def _route_to_ai(self, user_input: str) -> str:
        """Route to default AI provider (OpenRouter via MCP Gateway)"""
        try:
            provider = self.ai_config.get("default_provider", "openrouter-ai")
            provider_config = self.ai_config.get("providers", {}).get(provider, {})
            credential_service = provider_config.get("credential_service", "openrouter")
            
            # Get encrypted credential from MCP Gateway
            cred_request = {
                "action": "get_credential",
                "service": credential_service
            }
            cred_response = self._call_mcp_gateway(json.dumps(cred_request))
            
            # Parse credential response
            try:
                cred_data = json.loads(cred_response)
                if cred_data.get("status") != "success":
                    return f"Error: {cred_data.get('message', 'Failed to retrieve credential')}"
                api_key = cred_data.get("credential")
            except:
                return "Error: Failed to retrieve encrypted credential from MCP Gateway"
            
            # Call AI skill with decrypted credential
            request = {
                "skill": provider,
                "tool": "chat_completion",
                "params": {
                    "messages": [{"role": "user", "content": user_input}],
                    "api_key": api_key
                }
            }
            return self._call_mcp_gateway(json.dumps(request))
        except Exception as e:
            return f"Error routing to AI: {str(e)}"
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph StateGraph for agent workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("execute", self._execute_node)
        
        # Set entry point
        workflow.set_entry_point("supervisor")
        
        # Add edges
        workflow.add_edge("supervisor", "execute")
        workflow.add_edge("execute", END)
        
        return workflow.compile()
    
    def _supervisor_node(self, state: AgentState) -> AgentState:
        """Supervisor node that analyzes request and routes to appropriate action"""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        
        if not last_message:
            return {"messages": [], "next": "execute"}
        
        user_input = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Determine routing
        state["next"] = "execute"
        return state
    
    def _execute_node(self, state: AgentState) -> AgentState:
        """Execute node that processes the request using LangGraph tools"""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        
        if not last_message:
            return state
        
        user_input = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Handle slash commands with builtin logic
        if user_input.startswith("/"):
            response = self._handle_slash_command(user_input)
        else:
            # Use invoke_mcp_skill tool for AI routing
            provider = self.ai_config.get("default_provider", "openrouter-ai")
            provider_config = self.ai_config.get("providers", {}).get(provider, {})
            credential_service = provider_config.get("credential_service", "openrouter")
            
            # Get credential from MCP Gateway
            cred_request = {
                "action": "get_credential",
                "service": credential_service
            }
            cred_response = self._call_mcp_gateway(json.dumps(cred_request))
            
            try:
                cred_data = json.loads(cred_response)
                if cred_data.get("status") == "success":
                    api_key = cred_data.get("credential")
                    
                    # Use invoke_mcp_skill tool
                    response = invoke_mcp_skill(
                        skill=provider,
                        tool_name="chat_completion",
                        params={
                            "messages": [{"role": "user", "content": user_input}],
                            "api_key": api_key
                        }
                    )
                else:
                    response = f"Error: {cred_data.get('message', 'Failed to retrieve credential')}"
            except Exception as e:
                response = f"Error routing to AI: {str(e)}"
        
        # Add response to messages
        state["messages"].append(AIMessage(content=response))
        return state
    
    def process(self, user_input: str) -> str:
        """
        Process user input through LangGraph workflow
        
        Args:
            user_input: User's request or query
            
        Returns:
            Agent's response
        """
        # Create initial state
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "next": ""
        }
        
        # Run graph
        result = self.graph.invoke(initial_state)
        
        # Extract response
        messages = result.get("messages", [])
        if messages and len(messages) > 1:
            last_message = messages[-1]
            return last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        return "No response generated"
    
def main():
    """CLI entry point for subprocess execution"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: adminotaur.agent <user_input>")
        sys.exit(1)
    
    user_input = " ".join(sys.argv[1:])
    
    # Initialize Adminotaur (uses MCP Gateway routing)
    agent = Adminotaur()
    
    # Process input and return response
    response = agent.process(user_input)
    print(response)


if __name__ == "__main__":
    main()
