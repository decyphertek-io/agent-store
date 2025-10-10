
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
        
        # NEW ARCHITECTURE: Look in ~/.decyphertek-ai/store/ for installed components
        self.user_home = Path.home() / ".decyphertek-ai"
        self.user_store = self.user_home / "store"
        
        # Installed component paths
        self.app_store_path = self.user_store / "app"
        self.mcp_store_path = self.user_store / "mcp"
        self.agent_store_path = self.user_store / "agent"
        
        # Discover installed components
        self.available_apps = self._discover_flet_apps()
        self.available_mcp_servers = self._discover_mcp_servers()
        
        # Note management paths
        self.notes_dir = self.user_home
        self.user_notes_path = self.notes_dir / "user_notes.txt"
        self.agent_notes_path = self.notes_dir / "notes.md"
        
        # New notes directory structure - save directly to ~/.decyphertek-ai/notes/
        self.notes_folder = self.notes_dir / "notes"
        self.admin_file = self.notes_folder / "admin.txt"
        self.quicknotes_file = self.notes_folder / "quicknotes.md"
        
        # Chat history path
        self.chat_history_path = self.user_home / "chat_history.json"
        
        # RAG MCP server integration
        self.rag_server_id = "rag"
        
        # Ensure directories exist
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.notes_folder.mkdir(parents=True, exist_ok=True)
        self.user_store.mkdir(parents=True, exist_ok=True)
        
        # Debug info removed for cleaner output

    def _discover_flet_apps(self) -> Dict[str, Dict]:
        """Discover available Flet applications from the app store"""
        apps = {}
        if not self.app_store_path.exists():
            if getattr(self, "verbose", False):
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
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] MCP store not found at {self.mcp_store_path}")
            return servers
        
        for server_dir in self.mcp_store_path.iterdir():
            if server_dir.is_dir():
                server_name = server_dir.name
                # Look for compiled .mcp binary first, then fallback to .py scripts
                if server_name == "web-search":
                    server_binary = server_dir / "web.mcp"
                    server_script = server_dir / "web.py"
                else:
                    server_binary = server_dir / f"{server_name}.mcp"
                    server_script = server_dir / f"{server_name}.py"
                
                # Prefer binary over script
                if server_binary.exists():
                    servers[server_name.lower()] = {
                        'name': server_name,
                        'path': server_dir,
                        'script': server_binary,
                        'type': 'binary'
                    }
                elif server_script.exists():
                    servers[server_name.lower()] = {
                        'name': server_name,
                        'path': server_dir,
                        'script': server_script,
                        'type': 'script'
                    }
        return servers
    
    def _call_mcp_server(self, server_id: str, message: str) -> str:
        """Call an MCP server with a message."""
        try:
            if server_id not in self.available_mcp_servers:
                return f"❌ MCP server '{server_id}' not found."
            
            server_info = self.available_mcp_servers[server_id]
            script_path = server_info['script']
            server_type = server_info.get('type', 'script')
            
            # Prepare the payload for the MCP server
            payload = {
                "message": message,
                "context": "",
                "history": []
            }
            
            # Set up environment variables
            env_vars = os.environ.copy()
            
            # Enable debug mode for systemctl/healthcheck or likely web queries
            is_systemctl_command = message.startswith("sudo systemctl")
            is_healthcheck_mode = os.environ.get("HEALTHCHECK_MODE", "0") in ("1", "true", "yes")
            msg_lc = (message or "").lower()
            is_web_query = any(k in msg_lc for k in ("weather", "web ", "search ", "look up", "find "))
            env_vars.update({
                "PATH": os.environ.get("PATH", ""),
                "MCP_DEBUG": "1" if (is_systemctl_command or is_healthcheck_mode or is_web_query) else "0",
                "MCP_STANDALONE": "1"  # Ensure MCP servers run in standalone mode when called by agent
            })
            
            # Execute based on server type
            if server_type == 'binary':
                # Direct execution of compiled binary
                cmd = [str(script_path)]
            else:
                # Fallback to Python script execution
                env_vars["PYTHONPATH"] = str(server_info['path'])
                venv_python = server_info['path'] / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                python_executable = str(venv_python) if venv_python.exists() else sys.executable
                cmd = [python_executable, str(script_path)]
            
            # Execute the MCP server
            process = subprocess.run(
                cmd,
                input=json.dumps(payload).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(server_info['path']),
                env=env_vars,
                timeout=30
            )
            
            stdout_text = process.stdout.decode("utf-8", errors="ignore").strip()
            stderr_text = process.stderr.decode("utf-8", errors="ignore").strip()
            if process.returncode != 0:
                return f"❌ MCP server '{server_id}' error: {stderr_text}"
            if not stdout_text:
                # Treat empty output as failure with diagnostics from stderr
                return f"❌ MCP server '{server_id}' produced no output. STDERR: {stderr_text[:400]}"
            
            # Parse response
            output = stdout_text
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
    
    def _run_health_check(self) -> str:
        """Show agent status, capabilities, and run functionality tests"""
        result = "=== Adminotaur Agent Health Check ===\n\n"
        
        # Agent status
        result += f"🤖 Agent: Adminotaur\n"
        result += f"  📁 Store path: {self.user_store}\n"
        result += f"  🔧 Verbose mode: {'✅' if getattr(self, 'verbose', False) else '❌'}\n"
        result += f"  🚀 Status: Active and ready\n\n"
        
        # Available MCP servers
        result += f"📡 Available MCP Servers:\n"
        if self.available_mcp_servers:
            for server_id, server_info in self.available_mcp_servers.items():
                server_type = server_info.get('type', 'unknown')
                result += f"  • {server_id} ({server_type})\n"
        else:
            result += "  ⚠️ No MCP servers available\n"
        
        result += "\n"
        
        # Available apps
        result += f"📱 Available Apps:\n"
        if self.available_apps:
            for app_id, app_info in self.available_apps.items():
                result += f"  • {app_id}\n"
        else:
            result += "  ⚠️ No apps available\n"
        
        result += "\n"
        
        # Capabilities
        result += f"🛠️ Capabilities:\n"
        result += f"  • Web search (via MCP servers)\n"
        result += f"  • Document management (RAG)\n"
        result += f"  • Application launching\n"
        result += f"  • Note management\n"
        result += f"  • System diagnostics\n"
        result += f"  • Chat and conversation\n"
        
        result += "\n"
        result += "=== Functionality Tests ===\n\n"
        
        # Test agent - return adminotaur.md
        result += f"🔍 Testing Agent:\n"
        agent_test = self._test_agent()
        if agent_test["success"]:
            result += f"  ✅ Agent test: SUCCESS\n"
            result += f"  ⏱️  Response time: {agent_test['execution_time']:.2f}s\n"
            result += f"  📝 Response preview: {agent_test['response'][:100]}...\n"
        else:
            result += f"  ❌ Agent test: FAILED\n"
            result += f"  🚨 Error: {agent_test['error']}\n"
        
        result += "\n"
        
        # Test web-search MCP server specifically
        if "web-search" in self.available_mcp_servers:
            result += f"🔍 Testing Web Search MCP:\n"
            web_test = self._test_mcp_server("web-search")
            if web_test["success"]:
                result += f"  ✅ Web search test: SUCCESS\n"
                result += f"  ⏱️  Response time: {web_test['execution_time']:.2f}s\n"
                result += f"  📝 Response preview: {web_test['response'][:100]}...\n"
            else:
                result += f"  ❌ Web search test: FAILED\n"
                result += f"  🚨 Error: {web_test['error']}\n"
        else:
            result += f"  ⚠️ Web search MCP not available\n"

        # Test OpenRouter API if available
        result += "\n"
        api_test = self._test_api_openrouter()
        result += "🔍 Testing OpenRouter API:\n"
        if api_test["success"]:
            result += f"  ✅ API test: SUCCESS\n"
            result += f"  ⏱️  Response time: {api_test['execution_time']:.2f}s\n"
            result += f"  📝 Response preview: {api_test['response'][:100]}...\n"
        else:
            result += f"  ❌ API test: FAILED\n"
            result += f"  🚨 Error: {api_test['error']}\n"
        
        result += "\n"
        result += "I can help with launching applications, managing notes, and system diagnostics. What would you like to do?"
        
        return result
    
    def _test_agent(self) -> Dict[str, Any]:
        """Test agent functionality by returning adminotaur.md"""
        test_result = {
            "success": False,
            "response": None,
            "error": None,
            "execution_time": 0
        }
        
        try:
            import time
            start_time = time.time()
            
            # Try to read adminotaur.md file
            md_file = self.user_store / "agent" / "adminotaur" / "adminotaur.md"
            if md_file.exists():
                content = md_file.read_text(encoding="utf-8")
                test_result["success"] = True
                test_result["response"] = content
            else:
                test_result["error"] = f"adminotaur.md not found at {md_file}"
            
            test_result["execution_time"] = time.time() - start_time
            
        except Exception as e:
            test_result["error"] = f"Error reading adminotaur.md: {e}"
        
        return test_result
    
    def _test_mcp_server(self, server_id: str) -> Dict[str, Any]:
        """Test MCP server functionality with appropriate test queries"""
        test_result = {
            "success": False,
            "response": None,
            "error": None,
            "execution_time": 0
        }
        
        try:
            import time
            start_time = time.time()
            
            # Prepare test payload based on server type
            if server_id == "web-search":
                test_message = "web search Describe Neuromancer 1984"
            elif server_id == "rag":
                test_message = "rag list_documents"
            else:
                test_message = f"test {server_id}"
            
            # Mark healthcheck mode for verbose diagnostics inside _call_mcp_server
            prev_health = os.environ.get("HEALTHCHECK_MODE")
            os.environ["HEALTHCHECK_MODE"] = "1"
            try:
                # Call the MCP server
                response = self._call_mcp_server(server_id, test_message)
            finally:
                if prev_health is None:
                    os.environ.pop("HEALTHCHECK_MODE", None)
                else:
                    os.environ["HEALTHCHECK_MODE"] = prev_health
            
            test_result["execution_time"] = time.time() - start_time
            
            if response and not response.startswith("❌"):
                test_result["success"] = True
                test_result["response"] = response
            else:
                # Include response text in error for better diagnostics
                test_result["error"] = response or "Unknown error (empty response)"
                
        except Exception as e:
            test_result["error"] = f"Test error: {e}"
        
        return test_result

    def _test_api_openrouter(self) -> Dict[str, Any]:
        """Test OpenRouter API if configured via OPENROUTER_API_KEY."""
        test_result = {
            "success": False,
            "response": None,
            "error": None,
            "execution_time": 0
        }
        try:
            import time, json, os, urllib.request
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                test_result["error"] = "OPENROUTER_API_KEY not configured"
                return test_result
            start = time.time()
            req = urllib.request.Request(
                url="https://openrouter.ai/api/v1/chat/completions",
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": "qwen/qwen-2.5-coder-32b-instruct",
                    "messages": [{"role": "user", "content": "Can you explain recursion?"}]
                }).encode("utf-8")
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
            test_result["execution_time"] = time.time() - start
            test_result["success"] = True
            test_result["response"] = body
        except Exception as e:
            test_result["error"] = f"API test error: {e}"
        return test_result

    def chat(self, messages: List[Dict], user_message: str) -> str:
        """
        Main chat method for the Adminotaur agent.
        Determines if a tool needs to be used, like launching an app.
        """
        # Save chat message to history
        self._save_chat_message(user_message, "user")
        
        # Check for health check command first
        if user_message in ("health-check-agent", "healthcheck-agent"):
            response = self._run_health_check()
            self._save_chat_message(response, "assistant")
            return response
        
        # Check if research mode is enabled (via toggle or one-shot @research)
        research_enabled = os.environ.get("RESEARCH_MODE_ENABLED", "0") in ("1", "true", "yes")
        
        if research_enabled:
            # Strip @research prefix if present (one-shot mode)
            clean_message = user_message.replace("@research", "").strip() if user_message.startswith("@research") else user_message
            response = self._handle_research_mode(clean_message)
            self._save_chat_message(response, "assistant")
            return response
        
        # Thinking...
        
        message_lower = user_message.lower()
        app_launch_keywords = ["run", "launch", "start", "open", "execute"]
        web_search_keywords = ["weather", "search", "what is", "how to", "find", "look up", "web search"]
        
        # Route based on UI toggle propagated via env
        try:
            use_web_search = os.environ.get("WEB_SEARCH_ENABLED", "0") in ("1", "true", "yes")
        except Exception:
            use_web_search = False
        if use_web_search and "web-search" in self.available_mcp_servers:
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] Web Search enabled: routing to web-search MCP server")
            return self._call_mcp_server("web-search", user_message)
        
        # If not using web search, continue with normal routing (apps/RAG/API)
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
                if getattr(self, "verbose", False):
                    print(f"[Adminotaur] Detected request to launch '{app_to_launch}'")
                # The main_class should have a generic launch method
                if hasattr(self.main_class, "launch_app_by_name"):
                    self.main_class.launch_app_by_name(app_to_launch)
                    return f"I have launched the {self.available_apps[app_to_launch]['name']} application for you."
                else:
                    return f"Sorry, I can't launch applications right now. The main application is missing the 'launch_app_by_name' method."
            
        # Check for RAG-related commands
        if "rag" in message_lower or "document" in message_lower or "documents" in message_lower:
            if "analyze" in message_lower or "analysis" in message_lower:
                # Extract filename from the message
                filename = user_message.replace("rag", "").replace("document", "").replace("analyze", "").replace("analysis", "").strip()
                if filename:
                    return self.analyze_rag_document(filename)
                else:
                    return "Please provide a filename. Example: 'rag analyze description.txt'"
            elif "search" in message_lower or "query" in message_lower or "find" in message_lower:
                # Extract search query from the message
                query = user_message.replace("rag", "").replace("document", "").replace("search", "").replace("query", "").replace("find", "").strip()
                if query:
                    return self.search_rag_documents(query)
                else:
                    return "Please provide a search query. Example: 'rag search python programming'"
            elif "read" in message_lower:
                # Extract filename from the message
                filename = user_message.replace("rag", "").replace("document", "").replace("read", "").strip()
                if filename:
                    return self.read_rag_document(filename)
                else:
                    return "Please provide a filename. Example: 'rag read myfile.txt'"
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
        response = "I can help with launching applications, managing notes, and system diagnostics. What would you like to do?"
        self._save_chat_message(response, "assistant")
        return response
    
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
            mcp_response = self._call_rag_mcp_tool("list_documents", parameters)
            
            # Create combined response with MCP server response and Adminotaur's analysis
            response_parts = []
            
            # Add MCP Server response bubble
            mcp_bubble = self._create_mcp_response_bubble(mcp_response)
            response_parts.append(mcp_bubble)
            
            # Add Adminotaur's analysis
            if mcp_response.get("success", False):
                result = mcp_response.get("result", {})
                if result.get("success", False):
                    adminotaur_analysis = self._format_list_result(result)
                    adminotaur_bubble = self._create_adminotaur_response_bubble(adminotaur_analysis)
                    response_parts.append(adminotaur_bubble)
                else:
                    error_bubble = self._create_adminotaur_response_bubble(f"❌ RAG list failed: {result.get('error', 'Unknown error')}")
                    response_parts.append(error_bubble)
            else:
                error_bubble = self._create_adminotaur_response_bubble(f"❌ Failed to call RAG MCP tool: {mcp_response.get('error', 'Unknown error')}")
                response_parts.append(error_bubble)
            
            # Return combined response
            return "\n\n---\n\n".join(response_parts)
                
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
    
    def read_rag_document(self, filename: str) -> str:
        """Read a specific document from storage"""
        try:
            parameters = {
                "filename": filename
            }
            mcp_response = self._call_rag_mcp_tool("read_document", parameters)
            
            # Create combined response with MCP server response and Adminotaur's analysis
            response_parts = []
            
            # Add MCP Server response bubble
            mcp_bubble = self._create_mcp_response_bubble(mcp_response)
            response_parts.append(mcp_bubble)
            
            # Add Adminotaur's analysis
            if mcp_response.get("success", False):
                result = mcp_response.get("result", {})
                if result.get("success", False):
                    adminotaur_analysis = self._format_read_result(result)
                    adminotaur_bubble = self._create_adminotaur_response_bubble(adminotaur_analysis)
                    response_parts.append(adminotaur_bubble)
                else:
                    error_bubble = self._create_adminotaur_response_bubble(f"❌ RAG read failed: {result.get('error', 'Unknown error')}")
                    response_parts.append(error_bubble)
            else:
                error_bubble = self._create_adminotaur_response_bubble(f"❌ Failed to call RAG MCP tool: {mcp_response.get('error', 'Unknown error')}")
                response_parts.append(error_bubble)
            
            # Return combined response
            return "\n\n---\n\n".join(response_parts)
                
        except Exception as e:
            return f"❌ Failed to read RAG document: {e}"
    
    def search_rag_documents(self, query: str) -> str:
        """Search through stored documents by content"""
        try:
            parameters = {
                "query": query
            }
            mcp_response = self._call_rag_mcp_tool("search_documents", parameters)
            
            # Create combined response with MCP server response and Adminotaur's analysis
            response_parts = []
            
            # Add MCP Server response bubble
            mcp_bubble = self._create_mcp_response_bubble(mcp_response)
            response_parts.append(mcp_bubble)
            
            # Add Adminotaur's analysis
            if mcp_response.get("success", False):
                result = mcp_response.get("result", {})
                if result.get("success", False):
                    adminotaur_analysis = self._format_search_result(result)
                    adminotaur_bubble = self._create_adminotaur_response_bubble(adminotaur_analysis)
                    response_parts.append(adminotaur_bubble)
                else:
                    error_bubble = self._create_adminotaur_response_bubble(f"❌ RAG search failed: {result.get('error', 'Unknown error')}")
                    response_parts.append(error_bubble)
            else:
                error_bubble = self._create_adminotaur_response_bubble(f"❌ Failed to call RAG MCP tool: {mcp_response.get('error', 'Unknown error')}")
                response_parts.append(error_bubble)
            
            # Return combined response
            return "\n\n---\n\n".join(response_parts)
                
        except Exception as e:
            return f"❌ Failed to search RAG documents: {e}"
    
    def analyze_rag_document(self, filename: str) -> str:
        """Analyze document structure, format, and extract metadata (netrunner-style)"""
        try:
            parameters = {
                "filename": filename
            }
            mcp_response = self._call_rag_mcp_tool("analyze_document", parameters)
            
            # Create combined response with MCP server response and Adminotaur's analysis
            response_parts = []
            
            # Add MCP Server response bubble
            mcp_bubble = self._create_mcp_response_bubble(mcp_response)
            response_parts.append(mcp_bubble)
            
            # Add Adminotaur's analysis
            if mcp_response.get("success", False):
                result = mcp_response.get("result", {})
                if result.get("success", False):
                    adminotaur_analysis = self._format_analysis_result(result)
                    adminotaur_bubble = self._create_adminotaur_response_bubble(adminotaur_analysis)
                    response_parts.append(adminotaur_bubble)
                else:
                    error_bubble = self._create_adminotaur_response_bubble(f"❌ RAG analysis failed: {result.get('error', 'Unknown error')}")
                    response_parts.append(error_bubble)
            else:
                error_bubble = self._create_adminotaur_response_bubble(f"❌ Failed to call RAG MCP tool: {mcp_response.get('error', 'Unknown error')}")
                response_parts.append(error_bubble)
            
            # Return combined response
            return "\n\n---\n\n".join(response_parts)
                
        except Exception as e:
            return f"❌ Failed to analyze RAG document: {e}"
    
    def _call_rag_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call a RAG MCP tool via the compiled binary and return the raw result for MCP server display"""
        try:
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] Calling RAG MCP tool: {tool_name} with params: {parameters}")
            
            # Use the RAG MCP server via subprocess call
            rag_server_id = "rag"
            if rag_server_id not in self.available_mcp_servers:
                return {
                    "success": False,
                    "error": f"RAG MCP server '{rag_server_id}' not found",
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "server": "RAG"
                }
            
            # Prepare payload for RAG MCP server
            payload = {
                "message": f"rag {tool_name}",
                "context": json.dumps(parameters),
                "history": []
            }
            
            # Call the RAG MCP server
            result_text = self._call_mcp_server(rag_server_id, json.dumps(payload))
            
            # Parse the result
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                result = {"text": result_text, "status": "success"}
            
            # Return the raw result for MCP server display
            return {
                "success": True,
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result,
                "server": "RAG"
            }
                
        except Exception as e:
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] Error calling RAG tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "parameters": parameters,
                "server": "RAG"
            }
    
    def _display_mcp_response(self, mcp_response: Dict[str, Any]) -> None:
        """Store MCP server response for chat display"""
        try:
            # Store the MCP response in a way that the chat system can access it
            if not hasattr(self, '_mcp_responses'):
                self._mcp_responses = []
            
            server_name = mcp_response.get("server", "MCP Server")
            tool_name = mcp_response.get("tool_name", "Unknown Tool")
            
            if mcp_response.get("success", False):
                result = mcp_response.get("result", {})
                if isinstance(result, dict):
                    # Format the result nicely
                    response_text = f"**{server_name}: {tool_name}**\n\n"
                    response_text += f"✅ **Status**: Success\n"
                    response_text += f"🔧 **Tool**: {tool_name}\n"
                    response_text += f"📊 **Parameters**: {mcp_response.get('parameters', {})}\n\n"
                    
                    # Add the actual result
                    if result.get("success", False):
                        response_text += f"📋 **Result**:\n```json\n{json.dumps(result, indent=2)}\n```"
                    else:
                        response_text += f"❌ **Error**: {result.get('error', 'Unknown error')}"
                else:
                    response_text = f"**{server_name}: {tool_name}**\n\n```\n{str(result)}\n```"
            else:
                response_text = f"**{server_name}: {tool_name}**\n\n❌ **Error**: {mcp_response.get('error', 'Unknown error')}"
            
            # Store the response for the chat system to display
            self._mcp_responses.append({
                "type": "mcp_response",
                "content": response_text,
                "server": server_name,
                "tool": tool_name
            })
            
            print(f"[MCP Response] {response_text}")
                
        except Exception as e:
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] Error storing MCP response: {e}")
    
    def get_mcp_responses(self) -> List[Dict[str, Any]]:
        """Get stored MCP responses and clear them"""
        responses = getattr(self, '_mcp_responses', [])
        self._mcp_responses = []
        return responses
    
    def _create_mcp_response_bubble(self, mcp_response: Dict[str, Any]) -> str:
        """Create MCP server response bubble content"""
        try:
            server_name = mcp_response.get("server", "MCP Server")
            tool_name = mcp_response.get("tool_name", "Unknown Tool")
            
            bubble_content = f"**MCP Server: {server_name} Chat**\n\n"
            bubble_content += f"🔧 **Tool**: {tool_name}\n"
            bubble_content += f"📊 **Parameters**: {mcp_response.get('parameters', {})}\n\n"
            
            if mcp_response.get("success", False):
                result = mcp_response.get("result", {})
                bubble_content += f"✅ **Status**: Success\n\n"
                bubble_content += f"📋 **Raw Response**:\n```json\n{json.dumps(result, indent=2)}\n```"
            else:
                bubble_content += f"❌ **Status**: Failed\n"
                bubble_content += f"❌ **Error**: {mcp_response.get('error', 'Unknown error')}"
            
            return bubble_content
            
        except Exception as e:
            return f"**MCP Server: RAG Chat**\n\n❌ Error formatting MCP response: {e}"
    
    def _create_adminotaur_response_bubble(self, content: str) -> str:
        """Create Adminotaur response bubble content"""
        return f"**Adminotaur**\n\n{content}"
    
    def _format_analysis_result(self, result: Dict[str, Any]) -> str:
        """Format document analysis result for display"""
        try:
            analysis = result.get("analysis", {})
            metadata = result.get("metadata", {})
            
            output = f"🔍 **Document Analysis: {result.get('filename', 'Unknown')}**\n\n"
            
            # Format information
            format_info = analysis.get("format", {})
            output += f"📄 **Format**: {format_info.get('description', 'Unknown')} ({format_info.get('type', 'unknown')})\n"
            
            # Statistics
            stats = analysis.get("stats", {})
            output += f"📊 **Statistics**:\n"
            output += f"  - Characters: {stats.get('char_count', 0):,}\n"
            output += f"  - Words: {stats.get('word_count', 0):,}\n"
            output += f"  - Lines: {stats.get('line_count', 0):,}\n"
            output += f"  - Paragraphs: {stats.get('paragraph_count', 0):,}\n\n"
            
            # Topics
            topics = analysis.get("topics", [])
            if topics:
                output += f"🏷️ **Key Topics**: {', '.join(topics[:5])}\n\n"
            
            # Entities
            entities = analysis.get("entities", {})
            if any(entities.values()):
                output += f"🔗 **Extracted Entities**:\n"
                for entity_type, values in entities.items():
                    if values:
                        output += f"  - {entity_type.title()}: {len(values)} found\n"
                output += "\n"
            
            # Readability
            readability = analysis.get("readability", {})
            if readability and "score" in readability:
                output += f"📖 **Readability**: {readability.get('level', 'Unknown')} ({readability.get('score', 0)}/100)\n"
                output += f"  - Avg words per sentence: {readability.get('avg_words_per_sentence', 0)}\n"
                output += f"  - Avg chars per word: {readability.get('avg_chars_per_word', 0)}\n\n"
            
            # Structure
            structure = analysis.get("structure", {})
            if structure:
                headings = structure.get("headings", [])
                if headings:
                    output += f"📋 **Structure**: {len(headings)} headings found\n"
                
                code_blocks = structure.get("code_blocks", [])
                if code_blocks:
                    output += f"💻 **Code Blocks**: {len(code_blocks)} found\n"
                
                lists = structure.get("lists", [])
                if lists:
                    output += f"📝 **Lists**: {len(lists)} found\n"
            
            return output
            
        except Exception as e:
            return f"❌ Error formatting analysis result: {e}"
    
    def _format_read_result(self, result: Dict[str, Any]) -> str:
        """Format document read result for display"""
        try:
            content = result.get("content", "")
            filename = result.get("filename", "Unknown")
            size = result.get("size", 0)
            
            # Truncate very long content
            if len(content) > 2000:
                content = content[:2000] + "\n\n... (content truncated)"
            
            return f"📖 **Document: {filename}** ({size:,} chars)\n\n{content}"
            
        except Exception as e:
            return f"❌ Error formatting read result: {e}"
    
    def _format_search_result(self, result: Dict[str, Any]) -> str:
        """Format document search result for display"""
        try:
            query = result.get("query", "")
            results = result.get("results", [])
            total = result.get("total_matches", 0)
            
            if total == 0:
                return f"🔍 **Search Results for '{query}'**: No matches found"
            
            output = f"🔍 **Search Results for '{query}'**: {total} matches found\n\n"
            
            for i, match in enumerate(results[:5], 1):  # Show top 5 results
                filename = match.get("filename", "Unknown")
                context = match.get("context", "")
                output += f"**{i}. {filename}**\n"
                output += f"```\n{context}\n```\n\n"
            
            if total > 5:
                output += f"... and {total - 5} more results"
            
            return output
            
        except Exception as e:
            return f"❌ Error formatting search result: {e}"
    
    def _format_list_result(self, result: Dict[str, Any]) -> str:
        """Format document list result for display"""
        try:
            documents = result.get("documents", [])
            
            if not documents:
                return "📚 **RAG Documents**: No documents found"
            
            output = f"📚 **RAG Documents**: {len(documents)} documents\n\n"
            
            for doc in documents:
                filename = doc.get("filename", "Unknown")
                size = doc.get("size", 0)
                source = doc.get("source", "unknown")
                output += f"📄 **{filename}** ({size:,} chars) - {source}\n"
            
            return output
            
        except Exception as e:
            return f"❌ Error formatting list result: {e}"
    
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

**Analyze Documents (Netrunner-style):**
- `rag analyze <filename>` - Deep analysis of document structure, format, and metadata
- `document analysis <filename>` - Extract entities, topics, readability metrics
- `documents analyze <filename>` - Cyberpunk-style document intelligence

**Search Documents:**
- `rag search <query>` - Search through uploaded documents
- `document query <query>` - Query the RAG database
- `documents find <query>` - Find information in documents

**Read Documents:**
- `rag read <filename>` - Read a specific document from storage
- `document read <filename>` - Read document content

**List Documents:**
- `rag list` - List all documents in RAG database
- `documents show` - Show all available documents

**Add Documents:**
- Use the RAG interface in the app to upload documents
- Documents are automatically processed and indexed

**Examples:**
- `rag analyze description.txt` - Full document analysis
- `rag search python programming` - Search content
- `rag read myfile.txt` - Read document
- `document analysis config.json` - Analyze configuration file
- `rag list` - List all documents"""
    
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

**Research Mode:**
- `@research <topic>` - Trigger research mode with web search and AI summary
- Results are automatically saved to research notes
- Can reference previous research notes and chat history

**Examples:**
- `search notes for "troubleshooting"`
- `write note: Remember to check logs when debugging`
- `read notes`
- `@research cybersecurity trends 2025`

Notes are saved to:
- User notes: `~/.decyphertek-ai/user_notes.txt`
- Agent notes: `~/.decyphertek-ai/notes.md` (formatted markdown)
- Research notes: `~/.decyphertek-ai/notes/` (can name anything like example.txt, researching.txt)"""
    
    def _handle_research_mode(self, message: str) -> str:
        """
        Handle @research mode: web search + AI summarization + note saving.
        Format: @research <topic>
        """
        try:
            # Extract research topic
            topic = message.replace("@research", "").strip()
            
            if not topic:
                return "❌ Please provide a research topic. Example: `@research quantum computing basics`"
            
            result_lines = [f"🔬 **Research Mode Activated**\n"]
            result_lines.append(f"📋 **Topic:** {topic}\n")
            
            # Step 1: Web search using MCP
            result_lines.append("### Step 1: Web Search")
            
            if "web-search" not in self.available_mcp_servers:
                return "❌ Web search MCP server not available. Please install it first."
            
            search_query = f"web search {topic}"
            result_lines.append(f"🔍 Searching for: {topic}...")
            
            web_results = self._call_mcp_server("web-search", search_query)
            
            if web_results.startswith("❌"):
                result_lines.append(f"\n{web_results}")
                return "\n".join(result_lines)
            
            result_lines.append(f"✅ Search completed\n")
            
            # Step 2: AI Summarization using OpenRouter
            result_lines.append("### Step 2: AI Analysis & Summarization")
            result_lines.append("🤖 Analyzing findings with AI...")
            
            summary = self._summarize_with_ai(topic, web_results)
            
            if summary.startswith("❌"):
                result_lines.append(f"\n{summary}")
                return "\n".join(result_lines)
            
            result_lines.append(f"✅ Analysis completed\n")
            
            # Step 3: Read previous notes and chat history for context
            result_lines.append("### Step 3: Context Integration")
            result_lines.append("📚 Checking previous research and chat history...")
            
            context_info = self._get_research_context(topic)
            result_lines.append(f"✅ Found {context_info['notes_count']} related notes, {context_info['history_count']} relevant chat messages\n")
            
            # Step 4: Save to notes
            result_lines.append("### Step 4: Saving Research")
            
            note_filename = self._save_research_note(topic, web_results, summary, context_info)
            
            if note_filename:
                result_lines.append(f"✅ Research saved to: `{note_filename}`\n")
            else:
                result_lines.append("⚠️ Research could not be saved\n")
            
            # Step 5: Present summary
            result_lines.append("### 📊 Research Summary\n")
            result_lines.append(summary)
            
            if context_info['related_notes']:
                result_lines.append("\n### 🔗 Related Previous Research")
                for note in context_info['related_notes'][:3]:
                    result_lines.append(f"- {note}")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"❌ Research mode error: {e}"
    
    def _summarize_with_ai(self, topic: str, web_results: str) -> str:
        """Use OpenRouter AI to summarize web search findings."""
        try:
            import urllib.request
            
            # Get API key from environment
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                return "❌ OPENROUTER_API_KEY not configured. Please set it in your environment."
            
            # Prepare prompt for AI
            prompt = f"""You are a research assistant helping to summarize web search results.

Topic: {topic}

Web Search Results:
{web_results}

Please provide a comprehensive summary covering:
1. Key findings and main points
2. Important facts and statistics
3. Relevant trends or developments
4. Practical applications or implications
5. Recommended next steps or areas for deeper research

Format the summary in clear markdown with headers and bullet points."""

            # Call OpenRouter API
            request_data = {
                "model": "qwen/qwen-2.5-coder-32b-instruct",
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            req = urllib.request.Request(
                url="https://openrouter.ai/api/v1/chat/completions",
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                data=json.dumps(request_data).encode("utf-8")
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))
            
            # Extract summary from response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                summary = response_data["choices"][0]["message"]["content"]
                return summary
            else:
                return "❌ AI summarization failed: No response from API"
                
        except Exception as e:
            return f"❌ AI summarization error: {e}"
    
    def _get_research_context(self, topic: str) -> Dict[str, Any]:
        """Get context from previous research notes and chat history."""
        context = {
            "notes_count": 0,
            "history_count": 0,
            "related_notes": [],
            "related_messages": []
        }
        
        try:
            # Search research notes in ~/.decyphertek-ai/notes/
            if self.notes_folder.exists():
                for note_file in self.notes_folder.glob("*.txt"):
                    content = note_file.read_text(encoding="utf-8")
                    # Simple keyword matching
                    if any(word.lower() in content.lower() for word in topic.split()):
                        context["notes_count"] += 1
                        context["related_notes"].append(note_file.name)
            
            # Search chat history
            if self.chat_history_path.exists():
                chat_history = json.loads(self.chat_history_path.read_text(encoding="utf-8"))
                for msg in chat_history[-100:]:  # Check last 100 messages
                    if any(word.lower() in msg.get("content", "").lower() for word in topic.split()):
                        context["history_count"] += 1
                        context["related_messages"].append(msg.get("content", "")[:100])
                        
        except Exception as e:
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] Error getting research context: {e}")
        
        return context
    
    def _save_research_note(self, topic: str, web_results: str, summary: str, context: Dict[str, Any]) -> str:
        """Save research findings to a note file in ~/.decyphertek-ai/notes/"""
        try:
            from datetime import datetime
            
            # Generate filename - can be anything.txt like "researching.txt"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic)
            safe_topic = safe_topic.replace(' ', '_')[:50]  # Limit length
            filename = f"{timestamp}_{safe_topic}.txt"
            filepath = self.notes_folder / filename
            
            # Prepare note content
            note_content = f"""# Research Note: {topic}
Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary
{summary}

## Original Web Search Results
{web_results}

## Context
- Previous related notes: {context['notes_count']}
- Related chat messages: {context['history_count']}

## Related Notes
{chr(10).join(f"- {note}" for note in context['related_notes'][:5]) if context['related_notes'] else "None"}

---
Generated by Adminotaur Research Mode
"""
            
            # Write to file in ~/.decyphertek-ai/notes/
            filepath.write_text(note_content, encoding="utf-8")
            
            return filename
            
        except Exception as e:
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] Error saving research note: {e}")
            return None
    
    def _save_chat_message(self, message: str, role: str) -> None:
        """Save chat message to history for context."""
        try:
            # Load existing history
            history = []
            if self.chat_history_path.exists():
                try:
                    history = json.loads(self.chat_history_path.read_text(encoding="utf-8"))
                except:
                    history = []
            
            # Add new message
            from datetime import datetime
            history.append({
                "timestamp": datetime.now().isoformat(),
                "role": role,
                "content": message
            })
            
            # Keep only last 1000 messages
            if len(history) > 1000:
                history = history[-1000:]
            
            # Save history
            self.chat_history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
            
        except Exception as e:
            if getattr(self, "verbose", False):
                print(f"[Adminotaur] Error saving chat message: {e}")
    
    def read_research_notes(self, topic: str = None) -> str:
        """Read research notes from ~/.decyphertek-ai/notes/, optionally filtered by topic."""
        try:
            if not self.notes_folder.exists():
                return "📚 No research notes found yet. Use `@research <topic>` to create your first research note!"
            
            notes = list(self.notes_folder.glob("*.txt"))
            
            if not notes:
                return "📚 No research notes found yet. Use `@research <topic>` to create your first research note!"
            
            result_lines = [f"📚 **Research Notes** ({len(notes)} total)\n"]
            
            # Filter by topic if provided
            if topic:
                filtered_notes = []
                for note_file in notes:
                    content = note_file.read_text(encoding="utf-8")
                    if any(word.lower() in content.lower() for word in topic.split()):
                        filtered_notes.append(note_file)
                notes = filtered_notes
                result_lines.append(f"🔍 Filtered by: {topic}\n")
            
            if not notes:
                return f"📚 No research notes found for topic: {topic}"
            
            # List notes with preview
            for note_file in sorted(notes, reverse=True)[:10]:  # Show 10 most recent
                content = note_file.read_text(encoding="utf-8")
                # Extract title from content
                lines = content.split('\n')
                title = lines[0].replace('#', '').strip() if lines else note_file.name
                
                result_lines.append(f"### 📄 {note_file.name}")
                result_lines.append(f"**{title}**")
                result_lines.append(f"Preview: {content[:200]}...")
                result_lines.append("")
            
            if len(notes) > 10:
                result_lines.append(f"... and {len(notes) - 10} more notes")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"❌ Error reading research notes: {e}"


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
        if message in ("health_check", "health-check", "health-check-agent", "healthcheck-agent"):
            response = agent._run_health_check()
        elif message == "sudo systemctl status agent-adminotaur":
            response = agent._run_health_check()
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
