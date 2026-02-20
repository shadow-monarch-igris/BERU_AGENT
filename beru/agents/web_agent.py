"""
Web Agent for BERU
Handles web search, API testing, and web operations
"""

from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Optional

from beru.core.agent import BaseAgent, agent
from beru.core.llm import get_llm_client
from beru.plugins.base import Tool, ToolResult, ToolParameter, ToolType
from beru.utils.logger import get_logger

logger = get_logger("beru.agents.web")


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for information"
    tool_type = ToolType.UTILITY
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Search query",
            required=True,
        ),
        ToolParameter(
            name="num_results",
            type="integer",
            description="Number of results to return",
            required=False,
            default=5,
        ),
    ]

    async def execute(self, query: str, num_results: int = 5, **kwargs) -> ToolResult:
        try:
            import aiohttp

            search_url = f"https://duckduckgo.com/html/?q={query}"

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        results = self._parse_results(html, num_results)
                        return ToolResult(
                            success=True,
                            output=results,
                            metadata={"query": query, "count": len(results)},
                        )
                    else:
                        return ToolResult(
                            success=False,
                            output=None,
                            error=f"Search failed with status {response.status}",
                        )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def _parse_results(self, html: str, limit: int) -> List[Dict[str, str]]:
        import re

        results = []
        pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>'
        matches = re.findall(pattern, html)[:limit]

        for url, title in matches:
            results.append({"title": title.strip(), "url": url})

        return results


class OpenWebsiteTool(Tool):
    name = "open_website"
    description = "Open a website in the default browser"
    tool_type = ToolType.UTILITY
    parameters = [
        ToolParameter(
            name="url",
            type="string",
            description="URL to open",
            required=True,
        ),
        ToolParameter(
            name="browser",
            type="string",
            description="Browser to use (default, firefox, chrome)",
            required=False,
            default="default",
        ),
    ]

    async def execute(self, url: str, browser: str = "default", **kwargs) -> ToolResult:
        import webbrowser

        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            if browser == "default":
                webbrowser.open(url)
            else:
                browsers = {
                    "firefox": "firefox",
                    "chrome": "google-chrome",
                    "chromium": "chromium-browser",
                }
                cmd = browsers.get(browser, browser)
                subprocess.Popen([cmd, url], start_new_session=True)

            return ToolResult(
                success=True,
                output=f"Opened {url} in {browser} browser",
                metadata={"url": url, "browser": browser},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class APITesterTool(Tool):
    name = "test_api"
    description = "Test REST API endpoints"
    tool_type = ToolType.UTILITY
    parameters = [
        ToolParameter(
            name="url",
            type="string",
            description="API endpoint URL",
            required=True,
        ),
        ToolParameter(
            name="method",
            type="string",
            description="HTTP method (GET, POST, PUT, DELETE)",
            required=False,
            default="GET",
        ),
        ToolParameter(
            name="headers",
            type="object",
            description="Request headers as JSON object",
            required=False,
        ),
        ToolParameter(
            name="body",
            type="object",
            description="Request body as JSON object",
            required=False,
        ),
    ]

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        body: Optional[Dict] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            import aiohttp
            import json

            method = method.upper()

            async with aiohttp.ClientSession() as session:
                request_kwargs = {"headers": headers or {}}

                if body and method in ["POST", "PUT", "PATCH"]:
                    request_kwargs["json"] = body

                async with session.request(
                    method, url, **request_kwargs, timeout=30
                ) as response:
                    try:
                        response_body = await response.json()
                    except:
                        response_body = await response.text()

                    result = {
                        "status_code": response.status,
                        "status": "success"
                        if 200 <= response.status < 300
                        else "error",
                        "headers": dict(response.headers),
                        "body": response_body,
                    }

                    return ToolResult(
                        success=True,
                        output=result,
                        metadata={"url": url, "method": method},
                    )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FetchURLTool(Tool):
    name = "fetch_url"
    description = "Fetch content from a URL"
    tool_type = ToolType.UTILITY
    parameters = [
        ToolParameter(
            name="url",
            type="string",
            description="URL to fetch",
            required=True,
        ),
    ]

    async def execute(self, url: str, **kwargs) -> ToolResult:
        try:
            import aiohttp

            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        return ToolResult(
                            success=True,
                            output=content[:10000],
                            metadata={"url": url, "size": len(content)},
                        )
                    else:
                        return ToolResult(
                            success=False, output=None, error=f"HTTP {response.status}"
                        )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


@agent
class WebAgent(BaseAgent):
    name = "web_agent"
    description = "Agent specialized in web operations and API testing"
    agent_type = "web"
    tools = [WebSearchTool, OpenWebsiteTool, APITesterTool, FetchURLTool]

    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.llm = get_llm_client()

    async def think(self, input_text: str) -> Dict[str, Any]:
        from beru.utils.helpers import extract_json

        prompt = f"""You are BERU's Web Agent - an expert in web operations and API testing.

User request: {input_text}

Available tools (use the EXACT action name):
- action: "web_search" - Search web (params: {{"query": "search query", "num_results": 5}})
- action: "open_website" - Open in browser (params: {{"url": "example.com", "browser": "default"}})
- action: "test_api" - Test API (params: {{"url": "https://api.example.com", "method": "GET", "headers": {{}}, "body": {{}}}})
- action: "fetch_url" - Fetch URL content (params: {{"url": "https://example.com"}})

Guidelines:
- For general questions: use action "answer"
- For web operations: use appropriate tool
- Be helpful with API testing
- Suggest best practices

Respond ONLY with valid JSON:
{{"action": "answer", "final_answer": "your response"}}
OR
{{"action": "tool_name", "action_input": {{"param": "value"}}}}

JSON response:"""

        try:
            response = await self.llm.generate(prompt, max_tokens=500, temperature=0.3)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text[:500]
                    if response.text
                    else "I'm not sure how to help.",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": f"Error: {e}. Please try again.",
            }

    async def act(self, thought: Dict[str, Any]) -> ToolResult:
        action = thought.get("action", "answer")
        action_input = thought.get("action_input", {})

        if action == "answer":
            return ToolResult(
                success=True,
                output=thought.get("final_answer", str(action_input)),
            )

        if isinstance(action_input, str):
            return ToolResult(
                success=False,
                output=None,
                error="Tool parameters must be an object",
            )

        return await self.execute_tool(action, **action_input)
