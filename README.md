# 🚀 BERU AI Assistant Available For Your Help  

Your personal AI assistant with comprehensive capabilities for file management, coding, web operations, project scaffolding, and more.

---

# 🔥 Why BERU Is Different (Fully Local Advantage)

## 🔒 100% Fully Local — No Paid Models Required

Most AI assistants:
- Require paid APIs
- Have monthly limits
- Restrict advanced models
- Cap token usage
- Lock features behind subscriptions

**BERU runs completely on your machine.**

If a model exists locally, BERU can use it.

Supported examples (via Ollama):
- mistral
- llama
- codellama
- phi
- deepseek
- any Ollama-supported local model

### What This Means:

- ❌ No API billing
- ❌ No usage limits
- ❌ No subscription dependency
- ❌ No vendor lock-in
- ❌ No cloud data exposure

You control:
- The model
- The hardware
- The privacy
- The performance

Your machine = your AI power.

---

# 🏆 Additional Advantages Over Other Assistants

✅ Fully offline capability  
✅ Unlimited usage (hardware dependent)  
✅ Model-agnostic architecture  
✅ True multi-agent system (not just chat wrapper)  
✅ Dynamic skill injection  
✅ System-level control (files + terminal + projects)  
✅ Built-in safety enforcement  
✅ Designed for developers, not casual users  

---

# ⚙️ Features

## 👤 User Experience

- **First-time Onboarding**: BERU greets you, learns about you, and saves your profile
- **System Scanning**: Automatically detects your apps, languages, and projects
- **Personalized Responses**: Uses your profile to tailor assistance
- **Conversation Tracking**: Remembers your interactions

---

# 🤖 Multi-Agent Architecture

| Agent | Purpose | Tools |
|-------|---------|-------|
| `file_agent` | File operations | read, write, update, delete, search, summarize, open in apps |
| `terminal_agent` | Command execution | execute commands, run scripts |
| `code_agent` | Code operations | write code, review, security analysis, documentation |
| `project_agent` | Project scaffolding | create FastAPI, Flask, React, Node.js projects |
| `web_agent` | Web operations | search web, open websites, test APIs |
| `orchestrator` | Multi-agent coordination | coordinates other agents for complex tasks |

Each agent has bounded responsibility and dedicated tools — making BERU modular and production-ready.

---

# 🧩 Skills System

Dynamically loadable skills from markdown files:

- Code Reviewer
- Data Analyst
- Web Researcher
- API Tester
- Create your own custom skills instantly

Add skill example:

```
beru> add skill email_sender
```

Skill loads instantly — no restart required.

---

# 📂 File Operations

- Read/write/update/delete files
- List directories with details
- Search files by pattern
- Summarize folder contents
- Open files in VS Code, browser, or any app

---

# 🏗️ Project Scaffolding

Create complete project structures:

- FastAPI projects
- Flask projects
- Python packages
- Node.js APIs
- React apps

Includes folder structure, boilerplate, and base setup.

---

# 🧠 Code Features

- Write structured production-ready code
- Review code for bugs
- Perform security analysis
- Generate documentation
- Refactor intelligently

---

# 🌐 Web Features

- Search the web
- Open websites in browser
- Test REST APIs
- Fetch URL content

---

# 🖥️ Terminal Operations

- Execute system commands
- Run scripts
- Git operations
- Inspect environment

---

# 📦 Installation

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

---

# 🚀 Quick Start

## CLI Mode

```bash
python -m beru.main
```

## API Server Mode

```bash
python -m beru.main --server --port 8080
```

---

# 🧾 Commands

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

---

# 💡 Usage Examples

## File Operations

```
beru> list files in /home/user171125/Documents
beru> read the file /home/user171125/Documents/notes.txt
beru> create a folder called test in Downloads
beru> summarize my projects folder
beru> open this folder in VS Code
beru> search for all Python files in Documents
beru> update the file config.py with "# Added by BERU"
```

---

## Project Creation

```
beru> agent project_agent
beru> create a FastAPI project called my_api in Downloads
beru> create a Flask project called webapp
beru> create a Python package called mylib
```

---

## Code Operations

```
beru> agent code_agent
beru> write a Python function to fetch data from an API
beru> review the code in utils.py
beru> analyze security issues in auth.py
beru> generate documentation for main.py
```

---

## Web Operations

```
beru> agent web_agent
beru> search for Python best practices
beru> open github.com in browser
beru> test the API at https://api.example.com/users
beru> fetch content from example.com
```

---

## Terminal Operations

```
beru> agent terminal_agent
beru> show current directory
beru> list all files with details
beru> run git status
```

---

# ⚙️ Configuration

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

---

# 🧬 Project Structure

```
beru/
├── agents/
│   ├── file_agent.py
│   ├── code_agent.py
│   ├── project_agent.py
│   ├── web_agent.py
│   ├── terminal_agent.py
│   └── orchestrator.py
├── core/
│   ├── agent.py
│   ├── llm.py
│   ├── profile.py
│   ├── onboarding.py
│   └── workflow.py
├── services/
│   └── system_scanner.py
├── skills/
│   ├── templates/
│   └── custom/
├── plugins/
├── safety/
├── api/
└── main.py
```

---

# 🛡️ Safety Features

- Blocks `rm -rf /`
- Validates file paths
- Requires confirmation for dangerous operations
- Logs operations for audit
- Sandbox protection

---

# 🧪 Python API

```python
import asyncio
from beru import AgentFactory

agent = AgentFactory.create('file_agent')
response = asyncio.run(agent.run('List all Python files'))
print(response)

code_agent = AgentFactory.create('code_agent')
response = asyncio.run(code_agent.run('Write a hello world function'))
```

---

# 🌍 REST API

```bash
curl http://localhost:8080/api/health
curl http://localhost:8080/api/agents

curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List files", "agent": "file_agent"}'
```

---

# 📌 Requirements

- Python 3.8+
- Ollama
- Local LLM
- Dependencies from requirements.txt

---

# 📜 License

MIT License — Free for personal and commercial use.

---

**Built by sHiVaM AI/ML Developer**  
**Powered entirely by Local LLMs via Ollama**

If you want complete control over your AI stack —  
BERU is your foundation.