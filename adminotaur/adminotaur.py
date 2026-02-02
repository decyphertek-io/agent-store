#!/usr/bin/env python3
"""
Adminotaur - LangChain Supervisor Agent
Coordinates worker agents and manages MCP skills for Decyphertek.ai
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import SystemMessage, HumanMessage


class Adminotaur:
    """
    LangChain-based supervisor agent for Decyphertek.ai
    Coordinates worker agents, manages MCP skills, and ensures system health
    """
    
    def __init__(self, llm=None):
        """
        Initialize Adminotaur supervisor agent
        
        Args:
            llm: LangChain LLM instance (provided by CLI/MCP Gateway)
        """
        self.llm = llm
        self.app_dir = Path.home() / ".decyphertek.ai"
        self.agent_workers_dir = self.app_dir / "agent-workers"
        self.mcp_skills_dir = self.app_dir / "mcp-skills"
        
        
        # Initialize memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Create agent if LLM provided
        if self.llm:
            self.agent = self._create_agent()
        else:
            self.agent = None
        
    def _initialize_tools(self) -> List[Tool]:
        """Initialize available tools for the agent"""
        tools = [
            Tool(
                name="list_agent_workers",
                func=self._list_agent_workers,
                description="List all available agent workers in the agent-workers directory"
            ),
            Tool(
                name="list_mcp_skills",
                func=self._list_mcp_skills,
                description="List all available MCP skills in the mcp-skills directory"
            ),
            Tool(
                name="system_health_check",
                func=self._system_health_check,
                description="Perform a system health check on Decyphertek.ai components"
            ),
            Tool(
                name="get_agent_info",
                func=self._get_agent_info,
                description="Get information about a specific agent worker. Input should be the agent name."
            ),
        ]
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent with tools"""
        system_prompt = """You are Adminotaur, the supervisor agent for Decyphertek.ai.

Your responsibilities:
1. Coordinate and manage worker agents
2. Monitor system health and component status
3. Route tasks to appropriate worker agents or MCP skills
4. Handle errors and implement recovery strategies
5. Ensure all components work together smoothly

You act as a system administrator - you're knowledgeable, efficient, and proactive.
When users ask for help, analyze their request and determine:
- Which worker agents are needed
- Which MCP skills should be used
- What the best approach is to solve their problem

Always provide clear, concise responses and take action when needed.
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5
        )
        
        return agent_executor
    
    def _list_agent_workers(self, query: str = "") -> str:
        """List available agent workers"""
        if not self.agent_workers_dir.exists():
            return "No agent workers directory found"
        
        agents = []
        for item in self.agent_workers_dir.iterdir():
            if item.is_file() and item.suffix in ['.agent', '.py']:
                agents.append(item.name)
        
        if not agents:
            return "No agent workers found"
        
        return f"Available agent workers: {', '.join(agents)}"
    
    def _list_mcp_skills(self, query: str = "") -> str:
        """List available MCP skills"""
        if not self.mcp_skills_dir.exists():
            return "No MCP skills directory found"
        
        skills = []
        for item in self.mcp_skills_dir.iterdir():
            if item.is_dir() or item.suffix in ['.json', '.py']:
                skills.append(item.name)
        
        if not skills:
            return "No MCP skills found"
        
        return f"Available MCP skills: {', '.join(skills)}"
    
    def _system_health_check(self, query: str = "") -> str:
        """Perform system health check"""
        checks = {
            "app_directory": self.app_dir.exists(),
            "agent_workers_directory": self.agent_workers_dir.exists(),
            "mcp_skills_directory": self.mcp_skills_dir.exists(),
            "creds_directory": (self.app_dir / "creds").exists(),
            "config_directory": (self.app_dir / "config").exists(),
        }
        
        status = "System Health Check:\n"
        for component, healthy in checks.items():
            status += f"  - {component}: {'✓ OK' if healthy else '✗ MISSING'}\n"
        
        all_healthy = all(checks.values())
        status += f"\nOverall Status: {'✓ All systems operational' if all_healthy else '✗ Issues detected'}"
        
        return status
    
    def _get_agent_info(self, agent_name: str) -> str:
        """Get information about a specific agent"""
        agent_path = self.agent_workers_dir / agent_name
        
        if not agent_path.exists():
            return f"Agent '{agent_name}' not found"
        
        info = f"Agent: {agent_name}\n"
        info += f"Path: {agent_path}\n"
        info += f"Type: {agent_path.suffix}\n"
        info += f"Size: {agent_path.stat().st_size} bytes\n"
        
        return info
    
    def process(self, user_input: str) -> str:
        """
        Process user input through the agent
        
        Args:
            user_input: User's request or query
            
        Returns:
            Agent's response
        """
        try:
            response = self.agent.invoke({"input": user_input})
            return response.get("output", "No response generated")
        except Exception as e:
            return f"Error processing request: {str(e)}"
    
    def reset_memory(self):
        """Reset conversation memory"""
        self.memory.clear()


def main():
    """Example usage - LLM must be provided by CLI/MCP Gateway"""
    print("Adminotaur agent")
    print("This agent is designed to be initialized by the Decyphertek CLI")
    print("LLM credentials are managed by the MCP Gateway")
    print("\nTo use: Import Adminotaur class and provide LLM instance")
    print("Example: adminotaur = Adminotaur(llm=your_llm_instance)")


if __name__ == "__main__":
    main()
