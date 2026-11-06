from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import before_model
from langchain_core.messages import HumanMessage, RemoveMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from tools import web_search

load_dotenv()

PROMPT_FILE = Path(__file__).parent / "prompts" / "personal_chef.txt"
MODEL_NAME = "openai/gpt-oss-120b"

# History cap: keep only the last N user turns (each turn includes its tool calls
# and search results). Older turns are dropped before every model call.
KEEP_TURNS = 3


@before_model
def cap_history(state, runtime):
    messages = state["messages"]
    human_idx = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if len(human_idx) <= KEEP_TURNS:
        return None  # nothing to trim
    # Start at the first message of the oldest turn we keep. Starting on a user
    # message means we never leave an orphaned tool result at the front.
    start = human_idx[-KEEP_TURNS]
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *messages[start:]]}


def build_agent():
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")
    # llm = ChatGroq(model=MODEL_NAME, temperature=0.2)
    llm = ChatGroq(model=MODEL_NAME, temperature=0.2, reasoning_effort="low")
    return create_agent(
        model=llm,
        tools=[web_search],
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
        middleware=[cap_history],
    )


def get_text(message) -> str:
    """Return the plain text of a model reply."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "") for part in content if isinstance(part, dict)
    )