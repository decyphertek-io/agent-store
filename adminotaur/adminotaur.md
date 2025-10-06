# Adminotaur Agent Capabilities

## Overview
Adminotaur is the core AI agent for the DecypherTek AI system, designed to interact with and manage various components of the environment.

## Core Capabilities

### 1. Application Management
- **Launch Flet Applications**: Can discover and launch Flet applications from the app store
- **App Discovery**: Automatically discovers available applications in the apps directory
- **App Execution**: Can execute applications with proper environment setup

### 2. System Integration
- **Health Monitoring**: Provides system health checks and status reports
- **Environment Management**: Handles virtual environment setup and dependency management
- **Configuration Management**: Manages agent configurations and settings

### 3. Chat Integration
- **Natural Language Processing**: Understands user intent for application launching
- **Command Recognition**: Recognizes keywords like "run", "launch", "start", "open", "execute"
- **Contextual Responses**: Provides appropriate responses based on user requests

### 4. Tool Integration
- **MCP Server Management**: Can interact with MCP (Model Context Protocol) servers
- **RAG Integration**: Works with Retrieval Augmented Generation for document processing
- **Store Management**: Manages agent, MCP, and app stores

## Usage Examples

### Launching Applications
- "Run langtek" - Launches the langtek application
- "Start the calculator app" - Launches calculator application
- "Open the text editor" - Launches text editor application

### System Commands
- "sudo systemctl status agent-adminotaur" - Shows agent status and capabilities
- "Health check" - Performs system health verification

## Technical Details

### Architecture
- Built as a modular Python class that can be instantiated and used
- Supports both direct instantiation and subprocess execution
- JSON-based communication protocol for subprocess calls

### Dependencies
- Python 3.7+
- Pathlib for file system operations
- JSON for data serialization
- Subprocess for external process management

### File Structure
- `adminotaur.py` - Main agent implementation
- `adminotaur.md` - This capabilities documentation
- `adminotaur.json` - Agent configuration
- `requirements.txt` - Python dependencies

## Status
✅ **Operational** - Agent is ready to assist with application management and system operations.
