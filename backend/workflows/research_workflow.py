from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from backend.tools.openalex_tool import search_papers


# 1. Define the workflow state
class ResearchState(TypedDict):
    topic: str
    papers: list[dict]


# 2. Create the search node
def search_node(state: ResearchState):
    papers = search_papers(
        state["topic"],
        limit=5
    )

    return {
        "papers": papers
    }


# 3. Build the LangGraph workflow
builder = StateGraph(ResearchState)

builder.add_node("search_papers", search_node)

builder.add_edge(START, "search_papers")
builder.add_edge("search_papers", END)


# 4. Compile the workflow
research_graph = builder.compile()


# 5. Create a function to run it
def run_research(topic: str):
    return research_graph.invoke({
        "topic": topic,
        "papers": []
    })