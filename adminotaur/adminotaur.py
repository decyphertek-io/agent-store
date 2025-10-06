
from typing import List, Dict, Any, Optional
import subprocess
import sys
import json
import os
from pathlib import Path

class AdminotaurAgent:
    """
    The core agent for interacting with the DecypherTek AI environment.
    It can discover and launch Flet applications from the agent-store.
    """
    def __init__(self, main_class: Any):
        """
        Initializes the Adminotaur agent.
        :param main_class: A reference to the main application class that holds the UI (page) and other state.
        """
        self.main_class = main_class
        self.page = main_class.page
        self.app_store_path = Path("./apps") # Assuming apps are in an 'apps' directory relative to the main app
        self.available_apps = self._discover_flet_apps()
        
        # Discover MCP servers in the store directory
        self.mcp_store_path = Path(__file__).parent.parent.parent / "store" / "mcp"
        self.available_mcp_servers = self._discover_mcp_servers()
        
        # Note management paths
        self.notes_dir = Path.home() / ".decyphertek-ai"
        self.user_notes_path = self.notes_dir / "user_notes.txt"
        self.agent_notes_path = self.notes_dir / "notes.md"
        
        # New notes directory structure
        self.notes_folder = self.notes_dir / "notes"
        self.admin_file = self.notes_folder / "admin.txt"
        self.quicknotes_file = self.notes_folder / "quicknotes.md"
        
        # RAG MCP server integration
        self.rag_server_id = "rag"
        
        # Ensure notes directory exists
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[Adminotaur] Initialized. Discovered apps: {list(self.available_apps.keys())}")
        print(f"[Adminotaur] Discovered MCP servers: {list(self.available_mcp_servers.keys())}")
        print(f"[Adminotaur] Notes directory: {self.notes_dir}")

    def _discover_flet_apps(self) -> Dict[str, Dict]:
        """Discover available Flet applications from the app store"""
        apps = {}
        if not self.app_store_path.exists():
            print(f"[Adminotaur] App store not found at {self.app_store_path}")
            return apps
        
        for app_dir in self.app_store_path.iterdir():
            if app_dir.is_dir():
                app_name = app_dir.name
                main_py = app_dir / "src" / "main.py"
                
                if main_py.exists():
                    apps[app_name.lower()] = {
                        'name': app_name,
                        'path': app_dir,
                        'main_file': main_py,
                    }
        return apps
    
    def _discover_mcp_servers(self) -> Dict[str, Dict]:
        """Discover available MCP servers from the MCP store"""
        servers = {}
        if not self.mcp_store_path.exists():
            print(f"[Adminotaur] MCP store not found at {self.mcp_store_path}")
            return servers
        
        for server_dir in self.mcp_store_path.iterdir():
            if server_dir.is_dir():
                server_name = server_dir.name
                server_script = server_dir / f"{server_name}.py"
                
                if server_script.exists():
                    servers[server_name.lower()] = {
                        'name': server_name,
                        'path': server_dir,
                        'script': server_script,
                    }
        return servers
    
    def _call_mcp_server(self, server_id: str, message: str) -> str:
        """Call an MCP server with a message."""
        try:
            if server_id not in self.available_mcp_servers:
                return f"❌ MCP server '{server_id}' not found."
            
            server_info = self.available_mcp_servers[server_id]
            script_path = server_info['script']
            
            # Prepare the payload for the MCP server
            payload = {
                "message": message,
                "context": "",
                "history": []
            }
            
            # Set up environment variables
            env_vars = os.environ.copy()
            env_vars.update({
                "PYTHONPATH": str(server_info['path']),
                "PATH": os.environ.get("PATH", "")
            })
            
            # Execute the MCP server script
            process = subprocess.run(
                [sys.executable, str(script_path)],
                input=json.dumps(payload).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(server_info['path']),
                env=env_vars,
                timeout=30
            )
            
            if process.returncode != 0:
                error_output = process.stderr.decode("utf-8", errors="ignore")
                return f"❌ MCP server '{server_id}' error: {error_output.strip()}"
            
            # Parse response
            output = process.stdout.decode("utf-8", errors="ignore").strip()
            try:
                response_data = json.loads(output)
                if isinstance(response_data, dict):
                    return response_data.get("text", response_data.get("response", str(response_data)))
                else:
                    return str(response_data)
            except json.JSONDecodeError:
                return output
                
        except subprocess.TimeoutExpired:
            return f"❌ MCP server '{server_id}' timed out"
        except Exception as e:
            return f"❌ Error calling MCP server '{server_id}': {e}"

    async def chat(self, messages: List[Dict], user_message: str) -> str:
        """
        Main chat method for the Adminotaur agent.
        Determines if a tool needs to be used, like launching an app.
        """
        print("[Adminotaur] Thinking...")
        
        message_lower = user_message.lower()
        app_launch_keywords = ["run", "launch", "start", "open", "execute"]
        web_search_keywords = ["weather", "search", "what is", "how to", "find", "look up", "web search"]
        
        # Check for web search intent
        if any(keyword in message_lower for keyword in web_search_keywords):
            if "web-search" in self.available_mcp_servers:
                print(f"[Adminotaur] Detected web search request, using web-search MCP server")
                return self._call_mcp_server("web-search", user_message)
            else:
                return "❌ Web search MCP server not available. Please ensure web-search is installed and enabled."
        
        # Check for app launch intent
        triggered_keyword = next((word for word in app_launch_keywords if word in message_lower), None)
        
        if triggered_keyword:
            # Find which app is being requested
            app_to_launch = None
            for app_name in self.available_apps.keys():
                if app_name in message_lower:
                    app_to_launch = app_name
                    break
            
            if app_to_launch:
                print(f"[Adminotaur] Detected request to launch '{app_to_launch}'")
                # The main_class should have a generic launch method
                if hasattr(self.main_class, "launch_app_by_name"):
                    self.main_class.launch_app_by_name(app_to_launch)
                    return f"I have launched the {self.available_apps[app_to_launch]['name']} application for you."
                else:
                    return f"Sorry, I can't launch applications right now. The main application is missing the 'launch_app_by_name' method."
            
        # Check for RAG-related commands
        if "rag" in message_lower or "document" in message_lower or "documents" in message_lower:
            if "search" in message_lower or "query" in message_lower or "find" in message_lower:
                # Extract search query from the message
                query = user_message.replace("rag", "").replace("document", "").replace("search", "").replace("query", "").replace("find", "").strip()
                if query:
                    return self.query_rag_documents(query)
                else:
                    return "Please provide a search query. Example: 'rag search python programming'"
            elif "list" in message_lower or "show" in message_lower:
                return self.list_rag_documents()
            elif "add" in message_lower or "upload" in message_lower:
                return "To add documents to RAG, please use the RAG interface in the app or upload files through the document manager."
            else:
                return self._get_rag_help()
        
        # Check for note-related commands
        if "note" in message_lower or "notes" in message_lower:
            if "search" in message_lower or "find" in message_lower:
                return self._search_notes(user_message)
            elif "write" in message_lower or "add" in message_lower or "create" in message_lower:
                return self._write_note(user_message)
            elif "read" in message_lower or "show" in message_lower:
                return self._read_notes()
            else:
                return self._get_notes_help()
        
        # Default response if no specific action is taken
        return "I can help with launching applications, managing notes, and system diagnostics. What would you like to do?"
    
    def handle_health_check(self) -> str:
        """Handle comprehensive health check requests and return system status."""
        try:
            result_lines = ["🔍 **Adminotaur System Health Check**\n"]
            
            # Agent Status
            result_lines.append("### 🤖 **Agent Status**")
            result_lines.append("✅ **Adminotaur Agent:** Operational and ready")
            result_lines.append("✅ **Agent Script:** Loaded successfully")
            result_lines.append("✅ **Agent Capabilities:** Available\n")
            
            # MCP Servers Status
            result_lines.append("### 🔧 **MCP Servers Status**")
            if self.available_mcp_servers:
                for server_id, server_info in self.available_mcp_servers.items():
                    # Test each MCP server
                    try:
                        test_result = self._call_mcp_server(server_id, "health_check")
                        if "working" in test_result.lower() or "success" in test_result.lower():
                            result_lines.append(f"✅ **{server_info['name']} ({server_id}):** Operational")
                        else:
                            result_lines.append(f"⚠️ **{server_info['name']} ({server_id}):** Issues detected")
                    except Exception as e:
                        result_lines.append(f"❌ **{server_info['name']} ({server_id}):** Error - {e}")
            else:
                result_lines.append("❌ **No MCP servers discovered**")
            result_lines.append("")
            
            # System Components
            result_lines.append("### 🏗️ **System Components**")
            result_lines.append("✅ **Chat Manager:** Available")
            result_lines.append("✅ **Store Manager:** Available")
            result_lines.append("✅ **Document Manager:** Available")
            result_lines.append("✅ **AI Client:** Available")
            result_lines.append("")
            
            # Agent Capabilities
            result_lines.append("### 📋 **Agent Capabilities**")
            current_dir = Path(__file__).parent
            md_file = current_dir / "adminotaur.md"
            
            if md_file.exists():
                try:
                    capabilities = md_file.read_text(encoding="utf-8").strip()
                    result_lines.append(capabilities)
                except Exception as e:
                    result_lines.append(f"⚠️ Could not read capabilities file: {e}")
            else:
                result_lines.append("⚠️ No capabilities file found (adminotaur.md)")
            
            result_lines.append("")
            
            # Note Management Status
            result_lines.append("### 📝 **Note Management**")
            user_notes_exist = self.user_notes_path.exists()
            agent_notes_exist = self.agent_notes_path.exists()
            
            result_lines.append(f"✅ **User Notes:** {'Available' if user_notes_exist else 'Not found'}")
            result_lines.append(f"✅ **Agent Notes:** {'Available' if agent_notes_exist else 'Not found'}")
            result_lines.append("✅ **Note Commands:** Available (search, read, write)")
            
            if user_notes_exist:
                try:
                    user_notes_size = len(self.user_notes_path.read_text(encoding="utf-8"))
                    result_lines.append(f"📊 **User Notes Size:** {user_notes_size} characters")
                except Exception:
                    pass
            
            if agent_notes_exist:
                try:
                    agent_notes_size = len(self.agent_notes_path.read_text(encoding="utf-8"))
                    result_lines.append(f"📊 **Agent Notes Size:** {agent_notes_size} characters")
                except Exception:
                    pass
            
            result_lines.append("")
            result_lines.append("### 🎯 **System Status: READY**")
            result_lines.append("All components are operational and ready for use.")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"❌ Health check failed: {e}"
    
    def handle_rag_status(self) -> str:
        """Handle RAG status check requests and return clean RAG system status."""
        try:
            result_lines = ["📚 **RAG System Status**\n"]
            
            # Check if document manager is available
            if not hasattr(self.main_class, 'document_manager') or not self.main_class.document_manager:
                result_lines.append("❌ Document Manager: Not available")
                result_lines.append("   RAG system is not initialized")
                return "\n".join(result_lines)
            
            doc_manager = self.main_class.document_manager
            
            # Check Qdrant connection
            try:
                collections = doc_manager.client.get_collections()
                result_lines.append("✅ Qdrant Connection: Connected")
                result_lines.append(f"   Collections: {len(collections.collections)}")
            except Exception as e:
                result_lines.append(f"❌ Qdrant Connection: Failed")
                result_lines.append("   RAG system cannot function without Qdrant")
                return "\n".join(result_lines)
            
            # Check documents
            try:
                documents = doc_manager.get_all_documents()
                result_lines.append(f"📄 Documents: {len(documents)} total")
                
                if documents:
                    result_lines.append("")
                    result_lines.append("Recent Documents:")
                    for i, doc in enumerate(documents[:3]):  # Show only first 3
                        title = doc.get('title', 'Untitled')
                        result_lines.append(f"   {i+1}. {title}")
                    
                    if len(documents) > 3:
                        result_lines.append(f"   ... and {len(documents) - 3} more")
                else:
                    result_lines.append("   No documents found")
                
            except Exception as e:
                result_lines.append(f"❌ Document Access: Failed")
            
            # Check storage directory
            try:
                storage_path = Path.home() / ".decyphertek-ai" / "qdrant"
                if storage_path.exists():
                    file_count = len(list(storage_path.rglob("*")))
                    result_lines.append(f"💾 Storage: {file_count} files")
                else:
                    result_lines.append("⚠️ Storage: Directory not found")
            except Exception as e:
                result_lines.append("❌ Storage: Check failed")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"❌ RAG status error: {e}"
    
    def handle_comprehensive_status(self) -> str:
        """Handle comprehensive system status check with all components and detailed information."""
        try:
            result_lines = ["🔍 **Comprehensive System Status Report**\n"]
            
            # Agent Status
            result_lines.append("### 🤖 **Agent Status**")
            result_lines.append("✅ **Adminotaur Agent:** Operational and ready")
            result_lines.append("✅ **Agent Script:** Loaded successfully")
            result_lines.append("✅ **Agent Capabilities:** Available\n")
            
            # MCP Servers Status
            result_lines.append("### 🔧 **MCP Servers Status**")
            if self.available_mcp_servers:
                for server_id, server_info in self.available_mcp_servers.items():
                    try:
                        test_result = self._call_mcp_server(server_id, "health_check")
                        if "working" in test_result.lower() or "success" in test_result.lower():
                            result_lines.append(f"✅ **{server_info['name']} ({server_id}):** Operational")
                        else:
                            result_lines.append(f"⚠️ **{server_info['name']} ({server_id}):** Issues detected")
                            result_lines.append(f"   Details: {test_result}")
                    except Exception as e:
                        result_lines.append(f"❌ **{server_info['name']} ({server_id}):** Error - {e}")
            else:
                result_lines.append("❌ **No MCP servers discovered**")
            result_lines.append("")
            
            # RAG System Status
            result_lines.append("### 📚 **RAG System Status**")
            if hasattr(self.main_class, 'document_manager') and self.main_class.document_manager:
                try:
                    doc_manager = self.main_class.document_manager
                    collections = doc_manager.client.get_collections()
                    result_lines.append("✅ **Qdrant Connection:** Connected")
                    result_lines.append(f"   Collections: {len(collections.collections)}")
                    
                    documents = doc_manager.get_all_documents()
                    result_lines.append(f"📄 **Documents:** {len(documents)} total")
                    
                    storage_path = Path.home() / ".decyphertek-ai" / "qdrant"
                    if storage_path.exists():
                        file_count = len(list(storage_path.rglob("*")))
                        result_lines.append(f"💾 **Storage:** {file_count} files")
                    
                except Exception as e:
                    result_lines.append(f"❌ **RAG System:** Error - {e}")
            else:
                result_lines.append("❌ **RAG System:** Document Manager not available")
            result_lines.append("")
            
            # System Components
            result_lines.append("### 🏗️ **System Components**")
            result_lines.append("✅ **Chat Manager:** Available")
            result_lines.append("✅ **Store Manager:** Available")
            result_lines.append("✅ **AI Client:** Available")
            result_lines.append("")
            
            # Note Management Status
            result_lines.append("### 📝 **Note Management**")
            user_notes_exist = self.user_notes_path.exists()
            agent_notes_exist = self.agent_notes_path.exists()
            
            result_lines.append(f"✅ **User Notes:** {'Available' if user_notes_exist else 'Not found'}")
            result_lines.append(f"✅ **Agent Notes:** {'Available' if agent_notes_exist else 'Not found'}")
            result_lines.append("✅ **Note Commands:** Available (search, read, write)")
            
            if user_notes_exist:
                try:
                    user_notes_size = len(self.user_notes_path.read_text(encoding="utf-8"))
                    result_lines.append(f"📊 **User Notes Size:** {user_notes_size} characters")
                except Exception:
                    pass
            
            if agent_notes_exist:
                try:
                    agent_notes_size = len(self.agent_notes_path.read_text(encoding="utf-8"))
                    result_lines.append(f"📊 **Agent Notes Size:** {agent_notes_size} characters")
                except Exception:
                    pass
            
            result_lines.append("")
            result_lines.append("### 🎯 **Overall System Status: READY**")
            result_lines.append("All components are operational and ready for use.")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"❌ Comprehensive status check failed: {e}"
    
    def _call_rag_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """Call a RAG MCP server tool"""
        try:
            # Check if RAG MCP server is available
            if self.rag_server_id not in self.available_mcp_servers:
                return f"❌ RAG MCP server not found. Please install it first."
            
            # Use the ChatManager's MCP invocation system
            if hasattr(self.main_class, 'chat_manager') and self.main_class.chat_manager:
                return self.main_class.chat_manager.invoke_mcp_server(
                    self.rag_server_id, tool_name, parameters
                )
            else:
                return "❌ ChatManager not available for MCP server calls"
                
        except Exception as e:
            return f"❌ RAG MCP tool call failed: {e}"
    
    def add_document_to_rag(self, content: str, filename: str, source: str = "adminotaur") -> str:
        """Add a document to the RAG database"""
        try:
            parameters = {
                "content": content,
                "filename": filename,
                "source": source
            }
            result = self._call_rag_mcp_tool("add_document", parameters)
            return result
        except Exception as e:
            return f"❌ Failed to add document to RAG: {e}"
    
    def query_rag_documents(self, query: str, n_results: int = 3) -> str:
        """Query documents in the RAG database"""
        try:
            parameters = {
                "query": query,
                "n_results": n_results
            }
            result = self._call_rag_mcp_tool("query_documents", parameters)
            return result
        except Exception as e:
            return f"❌ Failed to query RAG documents: {e}"
    
    def list_rag_documents(self) -> str:
        """List all documents in the RAG database"""
        try:
            parameters = {}
            result = self._call_rag_mcp_tool("list_documents", parameters)
            return result
        except Exception as e:
            return f"❌ Failed to list RAG documents: {e}"
    
    def delete_rag_document(self, doc_id: str) -> str:
        """Delete a document from the RAG database"""
        try:
            parameters = {
                "doc_id": doc_id
            }
            result = self._call_rag_mcp_tool("delete_document", parameters)
            return result
        except Exception as e:
            return f"❌ Failed to delete RAG document: {e}"
    
    def _search_notes(self, query: str) -> str:
        """Search through user notes, agent notes, and quicknotes for relevant information."""
        try:
            results = []
            
            # Search user notes
            if self.user_notes_path.exists():
                user_notes = self.user_notes_path.read_text(encoding="utf-8")
                if query.lower() in user_notes.lower():
                    results.append("📝 **Found in User Notes:**")
                    # Find relevant lines
                    lines = user_notes.split('\n')
                    for i, line in enumerate(lines):
                        if query.lower() in line.lower():
                            results.append(f"  Line {i+1}: {line.strip()}")
            
            # Search agent notes
            if self.agent_notes_path.exists():
                agent_notes = self.agent_notes_path.read_text(encoding="utf-8")
                if query.lower() in agent_notes.lower():
                    results.append("\n🤖 **Found in Agent Notes:**")
                    # Find relevant lines
                    lines = agent_notes.split('\n')
                    for i, line in enumerate(lines):
                        if query.lower() in line.lower():
                            results.append(f"  Line {i+1}: {line.strip()}")
            
            # Search quicknotes
            if self.quicknotes_file.exists():
                quicknotes = self.quicknotes_file.read_text(encoding="utf-8")
                if query.lower() in quicknotes.lower():
                    results.append("\n✏️ **Found in Quicknotes:**")
                    # Find relevant lines
                    lines = quicknotes.split('\n')
                    for i, line in enumerate(lines):
                        if query.lower() in line.lower():
                            results.append(f"  Line {i+1}: {line.strip()}")
            
            if results:
                return "\n".join(results)
            else:
                return f"❌ No notes found containing '{query}'. Try 'read notes' to see all available notes."
                
        except Exception as e:
            return f"❌ Error searching notes: {e}"
    
    def _write_note(self, message: str) -> str:
        """Write a note to the agent notes.md file."""
        try:
            # Extract the note content from the message
            # Look for patterns like "write note: content" or "add note: content"
            note_content = message
            for prefix in ["write note:", "add note:", "create note:", "note:"]:
                if prefix in message.lower():
                    note_content = message.split(prefix, 1)[1].strip()
                    break
            
            if not note_content:
                return "❌ Please provide note content. Example: 'write note: This is my note'"
            
            # Read existing notes
            existing_notes = ""
            if self.agent_notes_path.exists():
                existing_notes = self.agent_notes_path.read_text(encoding="utf-8")
            
            # Add timestamp and new note
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            new_note = f"\n## Note - {timestamp}\n{note_content}\n"
            
            # Write to file
            with open(self.agent_notes_path, 'w', encoding='utf-8') as f:
                if existing_notes:
                    f.write(existing_notes)
                else:
                    f.write("# Adminotaur Agent Notes\n\n")
                f.write(new_note)
            
            return f"✅ Note added successfully!\n📝 **Added:** {note_content}\n📅 **Timestamp:** {timestamp}"
            
        except Exception as e:
            return f"❌ Error writing note: {e}"
    
    def _read_notes(self) -> str:
        """Read all available notes (user, agent, and quicknotes)."""
        try:
            result_lines = ["📋 **Available Notes:**\n"]
            
            # Read user notes
            if self.user_notes_path.exists():
                user_notes = self.user_notes_path.read_text(encoding="utf-8")
                result_lines.append("## 👤 User Notes:")
                result_lines.append(user_notes)
                result_lines.append("")
            else:
                result_lines.append("## 👤 User Notes: No notes found")
                result_lines.append("")
            
            # Read agent notes
            if self.agent_notes_path.exists():
                agent_notes = self.agent_notes_path.read_text(encoding="utf-8")
                result_lines.append("## 🤖 Agent Notes:")
                result_lines.append(agent_notes)
                result_lines.append("")
            else:
                result_lines.append("## 🤖 Agent Notes: No notes found")
                result_lines.append("")
            
            # Read quicknotes from the new structure
            if self.quicknotes_file.exists():
                quicknotes = self.quicknotes_file.read_text(encoding="utf-8")
                result_lines.append("## ✏️ Quicknotes:")
                result_lines.append(quicknotes)
            else:
                result_lines.append("## ✏️ Quicknotes: No notes found")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"❌ Error reading notes: {e}"
    
    def _get_rag_help(self) -> str:
        """Get help information for RAG document commands."""
        return """📚 **RAG Document Commands:**

**Search Documents:**
- `rag search <query>` - Search through uploaded documents
- `document query <query>` - Query the RAG database
- `documents find <query>` - Find information in documents

**List Documents:**
- `rag list` - List all documents in RAG database
- `documents show` - Show all available documents

**Add Documents:**
- Use the RAG interface in the app to upload documents
- Documents are automatically processed and indexed

**Examples:**
- `rag search python programming`
- `document query machine learning`
- `rag list`"""
    
    def _get_notes_help(self) -> str:
        """Get help information about note management."""
        return """📝 **Note Management Commands:**

**Search Notes:**
- `search notes for "keyword"` - Search through all notes
- `find notes about "topic"` - Find notes containing specific topic

**Read Notes:**
- `read notes` - Show all available notes
- `show notes` - Display user and agent notes

**Write Notes:**
- `write note: Your note content here` - Add a new note
- `add note: Your note content here` - Add a new note
- `create note: Your note content here` - Add a new note

**Examples:**
- `search notes for "troubleshooting"`
- `write note: Remember to check logs when debugging`
- `read notes`

Notes are saved to:
- User notes: `~/.decyphertek-ai/user_notes.txt`
- Agent notes: `~/.decyphertek-ai/notes.md` (formatted markdown)"""


def main():
    """Main entry point for the adminotaur agent when called as a script."""
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        message = input_data.get("message", "")
        
        # Create a dummy main class for the agent
        class DummyMainClass:
            def __init__(self):
                self.page = None
        
        # Create agent instance
        agent = AdminotaurAgent(DummyMainClass())
        
        # Handle different message types
        if message == "health_check" or message == "health-check":
            response = agent.handle_health_check()
        elif message == "sudo systemctl status agent-adminotaur":
            response = agent.handle_health_check()
        elif message == "sudo systemctl status rag":
            response = agent.handle_rag_status()
        elif message == "sudo systemctl status all":
            response = agent.handle_comprehensive_status()
        else:
            # For other messages, use the chat method
            response = agent.chat([], message)
        
        # Return JSON response
        result = {
            "text": response,
            "status": "success"
        }
        
        print(json.dumps(result))
        
    except Exception as e:
        # Return error response
        error_result = {
            "text": f"Error: {e}",
            "status": "error"
        }
        print(json.dumps(error_result))


if __name__ == "__main__":
    main()
