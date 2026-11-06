import re

from langchain_core.messages import HumanMessage, ToolMessage
from langsmith import traceable

from agent import build_agent, get_text
from guardrails import REFUSAL, check_input, check_output, reset_search_budget

agent = build_agent()


def _tool_urls(messages) -> set:
    last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    urls = set()
    for m in messages[last_human + 1:]:
        if isinstance(m, ToolMessage):
            for u in re.findall(r"https?://[^\s<>\"'\\]+", str(m.content)):
                urls.add(u.rstrip(".,);/"))
    return urls


@traceable(name="chef_chat")
def chat(user_input: str, thread_id: str = "local-chat") -> dict:
    allowed, cleaned, reason = check_input(user_input)
    if not allowed:
        return {"answer": REFUSAL, "status": f"blocked_input:{reason}"}

    result = agent.invoke(
        {"messages": [HumanMessage(content=cleaned)]},
        {"configurable": {"thread_id": thread_id}},
    )
    answer = get_text(result["messages"][-1])
    final, status = check_output(answer, _tool_urls(result["messages"]))
    return {"answer": final, "status": status}