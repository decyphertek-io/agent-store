# Agent Store

A collection of LangGraph-based AI agents for Decyphertek.ai

## Overview

The Agent Store provides modular, open-source AI agents built with **LangGraph** that integrate seamlessly with the Decyphertek.ai CLI application. Each agent is designed to perform specific tasks while being coordinated by the Adminotaur supervisor agent.

## What is LangGraph?

LangGraph is a framework for building stateful, multi-agent applications with LLMs. It provides:

- **StateGraph**: Define agent workflows as directed graphs with nodes and edges
- **Multi-Agent Orchestration**: Supervisor/worker patterns for coordinating multiple agents
- **State Management**: Track conversation history, context, and workflow state
- **Conditional Routing**: Smart decision-making about which nodes to execute
- **Checkpointing**: Save and resume agent workflows (optional)

### Key Concepts

**StateGraph**: A graph-based workflow where nodes are functions and edges define execution flow

**Supervisor Agent**: Coordinates worker agents, routes requests, and manages overall workflow

**Worker Agents**: Specialized agents that perform specific tasks (future expansion)

**Tools**: Functions decorated with `@tool` that agents can call (e.g., MCP Gateway API calls)

**State**: TypedDict that flows through the graph, containing messages and routing information

## Integration with Decyphertek.ai

### Architecture

```
User Input → Decyphertek CLI
                ↓
    Adminotaur (LangGraph StateGraph)
    ├── Supervisor Node (analyzes request)
    ├── Execute Node (routes to MCP Gateway)
    └── Worker Nodes (future: specialized agents)
                ↓
        MCP Gateway (FastMCP)
        ├── Credential Management
        ├── Skill Invocation
        │   ├── openrouter-ai (LLM calls)
        │   ├── rag-chat (RAG queries)
        │   ├── web-search (search)
        │   └── custom skills...
        └── Returns Response
                ↓
    Response → CLI → User
```

### How It Works

1. **CLI Initialization**: When you run `decyphertek-cli.ai`, it downloads Adminotaur from this agent store
2. **LangGraph Workflow**: User input flows through Adminotaur's StateGraph:
   - **Supervisor Node**: Analyzes request, determines routing
   - **Execute Node**: Calls MCP Gateway with appropriate skill/tool
3. **MCP Gateway**: Handles credential retrieval, skill invocation, and API calls
4. **Response**: Results flow back through the graph to the CLI

### Directory Structure

```
~/.decyphertek.ai/
├── agent-store/       # Downloaded agents (Adminotaur, etc.)
├── mcp-store/         # MCP server skills (openrouter-ai, rag-chat, etc.)
├── app-store/         # Applications (chromadb, etc.)
├── creds/             # Encrypted credentials
├── configs/           # Configuration files (ai-config.json, slash-commands.json)
└── keys/              # SSH keys for encryption
```

## Building Agents with LangGraph

### Adminotaur Pattern (Supervisor)

Adminotaur uses LangGraph's supervisor pattern:

```python
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

class AgentState(TypedDict):
    messages: Annotated[List, operator.add]
    next: str

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("execute", execute_node)
workflow.add_edge("supervisor", "execute")
workflow.add_edge("execute", END)
graph = workflow.compile()

# Process input
result = graph.invoke({"messages": [HumanMessage(content="Hello")]})
```

### Worker Agent Pattern (Future)

Worker agents will follow this pattern:
- Specialized tasks (e.g., code analysis, system monitoring)
- Called by Adminotaur supervisor
- Can run automated tasks on schedules
- Use MCP Gateway for external API calls

### Learn More

- **LangGraph Documentation**: https://docs.langchain.com/oss/python/langgraph/overview
- **LangGraph Tutorials**: https://langchain-ai.github.io/langgraph/tutorials/
- **Multi-Agent Supervisor**: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/ 
