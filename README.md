# BERU 2.0

Production-grade multi-agent AI assistant with local LLM support.

## Features

- **Multi-Agent Architecture**: Specialized agents for different tasks
  - File Agent: Read, write, search, manage files
  - Terminal Agent: Execute commands safely
  - Orchestrator: Coordinate multiple agents in parallel

- **Parallel Workflows**: Run multiple independent tasks simultaneously

- **Plugin System**: Easily extend with custom tools

- **Safety Layer**: Sandboxing, command blocking, path validation

- **Local LLM**: Works with Ollama (no API keys needed)

- **REST API + WebSocket**: Build your own interface

- **Vector Memory**: ChromaDB for context retention

## Installation

```bash
# Clone or download BERU
cd beru

# Install dependencies
pip install -r requirements.txt

# Install Ollama (if not already)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull mistral
```

## Quick Start

### CLI Mode

```bash
# Start interactive CLI
python -m beru.main

# Or with specific config
python -m beru.main --config config.yaml
```

### API Server Mode

```bash
# Start REST API server
python -m beru.main --server --port 8080

# Or use default port from config
python -m beru.main --server
```

## Configuration

Edit `config.yaml` to customize:

```yaml
model:
  provider: "ollama"
  name: "mistral:latest"  # Your Ollama model
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

## Usage Examples

### 1. CLI Interactive Mode

```
beru> help

Commands:
  help              Show help
  exit, quit        Exit
  clear             Clear history
  agent <name>      Switch agent
  agents            List agents
  parallel <tasks>  Run parallel
  status            Show status

beru> List all Python files in this directory

[Agent analyzes and lists files]

beru> agent terminal_agent
Switched to terminal_agent

beru> What's the current directory?

[Terminal agent responds]
```

### 2. REST API

```bash
# Health check
curl http://localhost:8080/api/health

# List available agents
curl http://localhost:8080/api/agents

# Chat with agent
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all files in the current directory",
    "agent": "file_agent"
  }'

# Create parallel workflow
curl -X POST http://localhost:8080/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analyze_project",
    "mode": "parallel",
    "tasks": [
      {"input": "List all Python files", "agent": "file_agent"},
      {"input": "Count lines of code", "agent": "terminal_agent"}
    ]
  }'
```

### 3. WebSocket

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8080/ws');

// Initialize session
ws.send(JSON.stringify({
  cmd: 'init',
  agent: 'orchestrator'
}));

// Send message
ws.send(JSON.stringify({
  cmd: 'chat',
  message: 'Analyze this project'
}));

// Receive responses
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};

// Run parallel tasks
ws.send(JSON.stringify({
  cmd: 'parallel',
  tasks: [
    {input: 'Task 1', agent: 'file_agent'},
    {input: 'Task 2', agent: 'terminal_agent'}
  ]
}));
```

### 4. Python API

```python
import asyncio
from beru import (
    AgentFactory,
    Task,
    Workflow,
    get_workflow_executor,
)

# Create an agent
agent = AgentFactory.create('file_agent')

# Run a task
response = asyncio.run(agent.run('List all Python files'))

# Create parallel workflow
workflow = Workflow(name='parallel_analysis')

tasks = [
    Task.create(
        name='task1',
        input_text='List Python files',
        agent_name='file_agent'
    ),
    Task.create(
        name='task2',
        input_text='List config files',
        agent_name='file_agent'
    ),
]

workflow.add_parallel_tasks(tasks)

# Execute
executor = get_workflow_executor()
executor.register_agent(AgentFactory.create('file_agent'))

result = asyncio.run(executor.execute_workflow(workflow))
print(f"Status: {result.status.value}")
print(f"Duration: {result.total_duration}s")
```

## Creating Custom Tools

Create a new file in `plugins/custom/`:

```python
# plugins/custom/my_tools.py

from beru.plugins.base import Tool, ToolResult, ToolParameter, ToolType

class MyCustomTool(Tool):
    name = "my_custom_tool"
    description = "Does something custom"
    tool_type = ToolType.UTILITY
    parameters = [
        ToolParameter(
            name="input",
            type="string",
            description="Input to process",
            required=True,
        ),
    ]
    
    async def execute(self, input: str, **kwargs) -> ToolResult:
        # Your logic here
        result = f"Processed: {input}"
        return ToolResult(success=True, output=result)
```

The tool will be auto-discovered and loaded.

## Creating Custom Agents

```python
from beru.core.agent import BaseAgent, agent
from beru.core.llm import get_llm_client

@agent
class MyCustomAgent(BaseAgent):
    name = "custom_agent"
    description = "My custom agent"
    agent_type = "custom"
    tools = []  # Add your tools
    
    def __init__(self, agent_id=None):
        super().__init__(agent_id)
        self.llm = get_llm_client()
    
    async def think(self, input_text: str) -> dict:
        # Your reasoning logic
        prompt = f"Process: {input_text}"
        response = await self.llm.generate(prompt)
        return {"thought": response.text, "action": "answer", "final_answer": response.text}
    
    async def act(self, thought: dict) -> ToolResult:
        # Your action logic
        return ToolResult(success=True, output=thought.get("final_answer"))
```

## Safety Features

BERU blocks dangerous operations by default:

```python
from beru.safety import get_safety_manager

safety = get_safety_manager()

# Command validation
result = safety.validate_command("rm -rf /")
# result.allowed = False

# Path validation
result = safety.validate_path("/etc/passwd")
# result.allowed = False (if outside allowed paths)

# Safe execution
returncode, stdout, stderr = safety.execute_command("ls -la")
```

## Available Agents

| Agent | Purpose | Tools |
|-------|---------|-------|
| `file_agent` | File operations | read_file, write_file, list_directory, delete_file, search_files |
| `terminal_agent` | Command execution | execute_command, run_script |
| `orchestrator` | Multi-agent coordination | Coordinates other agents |

## Project Structure

```
beru/
├── core/
│   ├── agent.py      # Agent base classes
│   ├── llm.py        # LLM client (Ollama)
│   ├── memory.py     # Vector memory
│   └── workflow.py   # Workflow engine
├── agents/
│   ├── file_agent.py
│   ├── terminal_agent.py
│   └── orchestrator.py
├── plugins/
│   ├── base.py       # Tool base class
│   ├── loader.py     # Plugin loader
│   └── tools/        # Built-in tools
├── safety/
│   └── sandbox.py    # Safety layer
├── api/
│   └── server.py     # REST + WebSocket
├── utils/
│   ├── config.py     # Configuration
│   ├── logger.py     # Logging
│   └── helpers.py    # Utilities
└── main.py           # Entry point
```

## Environment Variables

```bash
# Custom config path
export BERU_CONFIG=/path/to/config.yaml

# Log level
export BERU_LOG_LEVEL=DEBUG
```

## Troubleshooting

### Ollama not found
```bash
# Start Ollama service
ollama serve

# Check available models
ollama list
```

### Model not found
```bash
# Update config.yaml with your model
# Or pull the model
ollama pull mistral
```

### Import errors
```bash
# Install all dependencies
pip install pyyaml aiohttp chromadb sentence-transformers
```

## License

MIT License - Use freely for any purpose.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Submit a pull request

---

Built with ❤️ for the AI community. Powered by local LLMs via Ollama.
