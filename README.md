# Agent Store

A collection of LangChain-based AI agents for Decyphertek.ai

## Overview

The Agent Store provides modular, open-source AI agents built with LangChain that integrate seamlessly with the Decyphertek.ai CLI application. Each agent is designed to perform specific tasks while being coordinated by the Adminotaur supervisor agent.

## What is LangChain?

LangChain is a framework for building applications powered by large language models (LLMs). It provides:

- **Agent Framework**: Create AI agents that can use tools and make decisions
- **Tool Integration**: Connect LLMs to external APIs, databases, and services
- **Memory Management**: Maintain conversation history and context
- **Prompt Templates**: Structure interactions with LLMs effectively
- **Chain Composition**: Combine multiple operations into workflows

### Key Concepts

**Agents**: AI systems that can reason, use tools, and take actions to accomplish goals

**Tools**: Functions that agents can call to interact with external systems (APIs, databases, file systems, etc.)

**Memory**: Storage of conversation history to maintain context across interactions

**Chains**: Sequences of operations that process inputs and produce outputs

## Integration with Decyphertek.ai

### Architecture

```
Decyphertek CLI
    ↓
Adminotaur (Supervisor Agent)
    ↓
Worker Agents (from Agent Store)
    ↓
MCP Skills + Tools
```

### How It Works

1. **CLI Initialization**: When you run `decyphertek-cli.ai`, it downloads Adminotaur from this agent store
2. **Supervisor Coordination**: Adminotaur acts as the supervisor, analyzing your requests and routing them to appropriate worker agents
3. **Agent Execution**: Worker agents use LangChain tools to interact with MCP skills, APIs, and system resources
4. **Response**: Results flow back through Adminotaur to the CLI

### Directory Structure

Agents are stored in your system at:
```
~/.decyphertek.ai/
├── agent-workers/     # Downloaded agents from this store
├── mcp-skills/        # MCP server skills
├── creds/             # Encrypted credentials
└── config/            # Configuration files
```

## Building Agents

Learn how to build LangChain agents:
- **LangChain Documentation**: https://docs.langchain.com/oss/python/langchain/overview
- **DeepAgents Documentation**: https://docs.langchain.com/oss/python/deepagents/overview
- **LangGraph Documentation**: https://docs.langchain.com/oss/python/langgraph/overview 
