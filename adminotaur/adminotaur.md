# Adminotaur - LangChain Supervisor Agent

## Overview
Adminotaur is the core supervisor agent for Decyphertek.ai, built with LangChain to coordinate worker agents, manage MCP skills, and ensure system health. It acts as the central orchestrator and administrator for the entire system.

## Architecture

### Role
- **Supervisor Agent**: Coordinates and manages worker agents
- **System Administrator**: Monitors health and ensures components work together
- **Task Router**: Analyzes requests and delegates to appropriate workers/skills
- **Error Handler**: Implements recovery strategies when issues occur

### Integration
Adminotaur integrates directly with the Decyphertek CLI:
```
CLI → Adminotaur (supervisor) → Worker Agents + MCP Skills → Response
```

## Core Capabilities

### 1. Agent Coordination
- Discover and list available worker agents in `~/.decyphertek.ai/agent-workers/`
- Route tasks to appropriate worker agents
- Monitor worker agent execution
- Handle agent lifecycle management

### 2. MCP Skill Management
- Discover and list available MCP skills in `~/.decyphertek.ai/mcp-skills/`
- Coordinate MCP skill usage
- Manage skill dependencies
- Provide skill information to workers

### 3. System Health Monitoring
- Check status of all Decyphertek.ai components
- Verify directory structure integrity
- Monitor agent and skill availability
- Report system health status

### 4. Task Routing
- Analyze user requests using natural language understanding
- Determine which workers and skills are needed
- Coordinate multi-agent workflows
- Ensure efficient task execution

## Technical Details

### Built With
- **LangChain**: Agent framework and orchestration
- **LangChain-OpenAI**: LLM integration
- **OpenAI GPT-4**: Language model for decision making
- **Python 3.10+**: Core implementation language

### Dependencies
```toml
langchain>=0.1.0
langchain-openai>=0.0.5
langchain-core>=0.1.0
openai>=1.0.0
```

### File Structure
```
adminotaur/
├── adminotaur.py       # Main agent implementation
├── adminotaur.md       # This documentation
├── pyproject.toml      # Dependencies
└── build.sh            # Build script
```

## Installation

### Prerequisites
- Python 3.10-3.12
- uv (Python package manager)
- OpenAI API key

### Build
```bash
cd adminotaur/
bash build.sh
```

### Configuration
Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### Standalone Mode
```bash
python adminotaur.py
```

### Integration with Decyphertek CLI
Adminotaur is automatically downloaded and integrated when you run the Decyphertek CLI for the first time. The CLI initializes Adminotaur and uses it to process all user requests.

### Programmatic Usage
```python
from adminotaur import Adminotaur

# Initialize
agent = Adminotaur(api_key="your-key", model="gpt-4")

# Process request
response = agent.process("List all available worker agents")
print(response)

# Reset conversation memory
agent.reset_memory()
```

## Available Tools

Adminotaur has access to the following tools:

1. **list_agent_workers**: List all available agent workers
2. **list_mcp_skills**: List all available MCP skills
3. **system_health_check**: Perform system health check
4. **get_agent_info**: Get information about a specific agent

## System Prompt

Adminotaur operates with the following system prompt:

> You are Adminotaur, the supervisor agent for Decyphertek.ai.
>
> Your responsibilities:
> 1. Coordinate and manage worker agents
> 2. Monitor system health and component status
> 3. Route tasks to appropriate worker agents or MCP skills
> 4. Handle errors and implement recovery strategies
> 5. Ensure all components work together smoothly
>
> You act as a system administrator - you're knowledgeable, efficient, and proactive.

## Directory Structure

Adminotaur works with the following directory structure:

```
~/.decyphertek.ai/
├── agent-workers/      # Worker agents storage
├── mcp-skills/         # MCP skills storage
├── creds/              # Encrypted credentials
└── config/             # Configuration files
```

## Features

### Conversation Memory
- Maintains conversation history for context
- Can be reset with `reset_memory()`
- Enables multi-turn interactions

### Error Handling
- Graceful error handling with informative messages
- Automatic parsing error recovery
- Maximum iteration limits to prevent loops

### Extensibility
- Easy to add new tools
- Pluggable worker agent support
- MCP skill integration ready

## Status
✅ **Operational** - Adminotaur is ready to coordinate agents and manage the Decyphertek.ai system.

## License
Open source - part of the Decyphertek.ai project

## Contributing
Contributions welcome! This agent is designed to be extended with additional tools and capabilities as the system grows.
