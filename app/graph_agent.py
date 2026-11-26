from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from app import agent          # reuse your tools, prompt, model name


@tool
def read_logs(service:str)->str:
    """Read recent ERROR/WARN log lines (last 2 minutes) for a service."""
    return agent.read_logs(service)



@tool
def get_metrics(service:str)->str:
    """Get request counts by status code (last 2 minutes) for a service."""
    return agent.get_metrics(service)

@tool
def get_service_status() -> str:
    """List all containers and whether each is Up or Exited."""
    return agent.get_service_status()


tools = [read_logs,get_metrics,get_service_status]
llm = ChatGroq(model=agent.MODEL).bind_tools(tools)  # bind_tools = send the tool menu every call


def call_llm(state:MessagesState):
    response = llm.invoke([SystemMessage(agent.SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}




builder = StateGraph(MessagesState)
builder.add_node("llm",call_llm)
builder.add_node("tools",ToolNode(tools))

builder.add_edge(START,"llm")
builder.add_conditional_edges("llm",tools_condition)
builder.add_edge("tools","llm")

graph = builder.compile()

if __name__ == "__main__":
    result = graph.invoke({"messages": [HumanMessage("ALERT: order-service error rate is above 5% for the last 2 minutes.")]})
    for m in result["messages"]:
        for tc in getattr(m, "tool_calls", []):
            print("Tool:", tc["name"], tc["args"])
    print("\nFINAL ANSWER:\n", result["messages"][-1].content)