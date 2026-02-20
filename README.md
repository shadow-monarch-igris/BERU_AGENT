# BERU AI Assistant Available For Your Help 

Your personal AI assistant with comprehensive capabilities for file management, coding, web operations, project scaffolding, and more.

## Features

### User Experience
- **First-time Onboarding**: BERU greets you, learns about you, and saves your profile
- **System Scanning**: Automatically detects your apps, languages, and projects
- **Personalized Responses**: Uses your profile to tailor assistance
- **Conversation Tracking**: Remembers your interactions

### Multi-Agent Architecture

| Agent | Purpose | Tools |
|-------|---------|-------|
| `file_agent` | File operations | read, write, update, delete, search, summarize, open in apps |
| `terminal_agent` | Command execution | execute commands, run scripts |
| `code_agent` | Code operations | write code, review, security analysis, documentation |
| `project_agent` | Project scaffolding | create FastAPI, Flask, React, Node.js projects |
| `web_agent` | Web operations | search web, open websites, test APIs |
| `orchestrator` | Multi-agent coordination | coordinates other agents for complex tasks |

### Skills System
Dynamically loadable skills from markdown files:
- Code Reviewer
- Data Analyst
- Web Researcher
- API Tester
- Add your own custom skills with simple commands!

### File Operations
- Read/write/update/delete files
- List directories with details
- Search files by pattern
- Summarize folder contents
- Open files in VS Code, browser, or any app

### Project Scaffolding
Create complete project structures:
- FastAPI projects
- Flask projects
- Python packages
- Node.js APIs
- React apps

### Code Features
- Write code with proper structure
- Review code for bugs and issues
- Security analysis
- Generate documentation

### Web Features
- Search the web
- Open websites in browser
- Test REST APIs
- Fetch URL content

## Installation

```bash
# Navigate to BERU directory
cd /home/user171125/Downloads/BERU_AGENT

# Install dependencies
pip install -r requirements.txt

# Start Ollama (if not running)
ollama serve

# Pull a model
ollama pull mistral
```

## Quick Start

### CLI Mode
```bash
python -m beru.main
```

### API Server Mode
```bash
python -m beru.main --server --port 8080
```

## Commands

```
help              Show help
exit, quit, q     Exit the assistant
clear             Clear conversation history
agent <name>      Switch to a different agent
agents            List available agents
skills            List available skills
add skill         Add a new custom skill
status            Show current status
profile           View your profile
rescan            Rescan system for changes
```

## Usage Examples

### File Operations
```
beru> list files in /home/user171125/Documents
beru> read the file /home/user171125/Documents/notes.txt
beru> create a folder called test in Downloads
beru> summarize my projects folder
beru> open this folder in VS Code
beru> search for all Python files in Documents
beru> update the file config.py with "# Added by BERU"
```

### Project Creation
```
beru> agent project_agent
beru> create a FastAPI project called my_api in Downloads
beru> create a Flask project called webapp
beru> create a Python package called mylib
```

### Code Operations
```
beru> agent code_agent
beru> write a Python function to fetch data from an API
beru> review the code in utils.py
beru> analyze security issues in auth.py
beru> generate documentation for main.py
```

### Web Operations
```
beru> agent web_agent
beru> search for Python best practices
beru> open github.com in browser
beru> test the API at https://api.example.com/users
beru> fetch content from example.com
```

### Terminal Operations
```
beru> agent terminal_agent
beru> show current directory
beru> list all files with details
beru> run git status
```

### Add Custom Skills
```
beru> add skill email_sender
  Description: Send emails to users
  # Skill is created automatically and ready to use!
```

## Configuration

Edit `config.yaml`:

```yaml
model:
  provider: "ollama"
  name: "mistral:latest"
  temperature: 0.2
  base_url: "http://localhost:11434"

agents:
  file_agent:
    enabled: true
    max_concurrent: 5

safety:
  sandbox_enabled: true
  forbidden_commands:
    - "rm -rf /"
    - "sudo rm"

api:
  host: "0.0.0.0"
  port: 8080
```

## Project Structure

```
beru/
├── agents/           # Specialized agents
│   ├── file_agent.py
│   ├── code_agent.py
│   ├── project_agent.py
│   ├── web_agent.py
│   ├── terminal_agent.py
│   └── orchestrator.py
├── core/             # Core components
│   ├── agent.py      # Base agent class
│   ├── llm.py        # LLM client
│   ├── profile.py    # User profile manager
│   ├── onboarding.py # First-time setup
│   └── workflow.py   # Workflow engine
├── services/         # Utility services
│   └── system_scanner.py
├── skills/           # Dynamic skills
│   ├── templates/    # Default skills
│   └── custom/       # User-added skills
├── plugins/          # Plugin system
├── safety/           # Safety features
├── api/              # REST API server
└── main.py           # Entry point
```

## Safety Features

BERU blocks dangerous operations:
- Blocks `rm -rf /` and similar commands
- Validates file paths
- Requires confirmation for dangerous operations
- Logs all operations for audit

## Python API

```python
import asyncio
from beru import AgentFactory

# Create an agent
agent = AgentFactory.create('file_agent')

# Run a task
response = asyncio.run(agent.run('List all Python files'))
print(response)

# Switch agents
code_agent = AgentFactory.create('code_agent')
response = asyncio.run(code_agent.run('Write a hello world function'))
```

## REST API

```bash
# Health check
curl http://localhost:8080/api/health

# List agents
curl http://localhost:8080/api/agents

# Chat with agent
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List files", "agent": "file_agent"}'
```

## Requirements

- Python 3.8+
- Ollama (for local LLM)
- See requirements.txt for dependencies

## Troubleshooting

### Ollama not found
```bash
ollama serve
ollama list
```

### Model not found
```bash
ollama pull mistral
```

### Import errors
```bash
pip install pyyaml aiohttp chromadb
```

## License

MIT License - Use freely for any purpose.

---

**Built by sHiVaM AI/ML DEVELOPER. Powered by local LLMs via Ollama.**
