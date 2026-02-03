#!/usr/bin/env python3
"""
Adminotaur - LangGraph Supervisor Agent
Coordinates worker agents and manages MCP skills for Decyphertek.ai
"""

import os
import json
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from pathlib import Path
import glob
import operator
import subprocess
import sys

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


@tool
def web_search(query: str) -> str:
    """Search the web for information.
    
    Args:
        query: Search query
        
    Returns:
        Search results
    """
    try:
        skill_path = Path.home() / ".decyphertek.ai" / "mcp-store" / "web-search" / "web.mcp"
        
        if not skill_path.exists():
            return f"Error: web-search skill not found"
        
        result = subprocess.run(
            [str(skill_path), query],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def rag_chat(query: str, context: str = "") -> str:
    """Query RAG system with context.
    
    Args:
        query: User query
        context: Optional context
        
    Returns:
        RAG response
    """
    try:
        skill_path = Path.home() / ".decyphertek.ai" / "mcp-store" / "rag-chat" / "rag.mcp"
        
        if not skill_path.exists():
            return f"Error: rag-chat skill not found"
        
        input_data = json.dumps({"query": query, "context": context})
        result = subprocess.run(
            [str(skill_path)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"


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
        Uses LangChain for OpenRouter AI, LangGraph for orchestration
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
        
        # Initialize LangChain LLM for OpenRouter
        api_key = os.environ.get('OPENROUTER_API_KEY', '')
        provider_config = self.ai_config.get("providers", {}).get("openrouter-ai", {})
        model = provider_config.get("default_model", "anthropic/claude-3.5-sonnet")
        base_url = provider_config.get("base_url", "https://openrouter.ai/api/v1")
        
        self.llm = ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7
        )
        
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
        config_text += f"Model: {self.ai_config.get('providers', {}).get('openrouter-ai', {}).get('default_model', 'Not set')}\n"
        config_text += f"Slash Commands: {len(self.slash_commands.get('commands', {}))} loaded\n"
        return config_text
    
    
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
        """Execute node that processes the request using LangChain LLM"""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        
        if not last_message:
            return state
        
        user_input = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Handle slash commands with builtin logic
        if user_input.startswith("/"):
            response = self._handle_slash_command(user_input)
        else:
            # Use LangChain LLM directly for AI responses
            try:
                ai_response = self.llm.invoke([HumanMessage(content=user_input)])
                response = ai_response.content
            except Exception as e:
                response = f"Error: {str(e)}"
        
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
