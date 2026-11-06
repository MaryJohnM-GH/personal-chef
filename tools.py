from typing import Any, Dict

from dotenv import load_dotenv
from langchain.tools import tool
from tavily import TavilyClient

from guardrails import clean_search_results, query_allowed

load_dotenv()
_tavily = TavilyClient()


@tool
def web_search(query: str) -> Dict[str, Any]:
    """Search the web for recipes and cooking information."""
    if not query_allowed(query):
        return {"results": [], "note": "Search not allowed or limit reached."}
    return clean_search_results(_tavily.search(query, max_results=3))