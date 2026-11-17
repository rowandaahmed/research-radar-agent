
import os
import json
import time

from typing import TypedDict
from dotenv import load_dotenv
from google import genai

from langgraph.graph import StateGraph, START, END

from backend.tools.openalex_tool import search_papers
from backend.profile_loader import load_professor_profile


# Load environment variables
load_dotenv()

# Initialize Gemini
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# 1. Define agent state
class ResearchState(TypedDict):
    topic: str
    papers: list[dict]
    analysis: str


# 2. Search node
def search_node(state: ResearchState):

    if state["papers"]:
        return {}

    papers = search_papers(
        state["topic"],
        limit=6
    )

    return {
        "papers": papers
    }


# 3. Analysis node
def analysis_node(state: ResearchState):

    papers_text = json.dumps(
        state["papers"],
        indent=2
    )

    prompt = f"""
    You are an expert academic research analyst specializing in
    Artificial Intelligence, Machine Learning, NLP, LLMs, and AI Agents.

    Research topic:
    {state["topic"]}

    Academic papers retrieved from OpenAlex:
    {papers_text}

    YOUR TASK:

    PART 1 — SELECT AND EXPLAIN THE PAPERS

    Analyze the supplied six papers.

    For each paper, provide:

    1. Title and publication year.
    2. Authors, if available.
    3. DOI or paper URL.
    4. Research problem.
    5. Methodology and technical approach.
    6. Main technical contribution.

    IMPORTANT:
    - Base explanations on the available abstracts.
    - Do not invent methods, technologies, or findings.
    - If information is unavailable, say:
      "Not specified in the abstract."
    - Avoid duplicate papers.
    - Keep explanations technically rich but concise.

    PART 2 — PROPOSE ONE RESEARCH IDEA

    Based on the selected papers, propose ONE promising
    research idea.

    Include:

    1. Research title.
    2. Research problem and motivation.
    3. Proposed technical approach.
    4. Possible algorithms, models, or technologies.
    5. Expected contribution.

    The idea must be a proposal, not a claim of proven novelty.
    Further literature review is required to verify originality.

    PART 3 — RESEARCH GAP

    Identify a research gap motivating the proposed idea.
    Distinguish evidence from the papers from your own inference.

    OUTPUT FORMAT:

    # ResearchRadar AI Report

    ## 1. Selected Academic Papers

    ## 2. Research Gap

    ## 3. Proposed Research Idea

    ## 4. Limitations of This Analysis

    Write in clear, technically rich academic English.
    Be concise and avoid generic statements.
    """

    # Separate model pools so a 429/503 on one immediately fails over to the next
    fallback_models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3-flash-preview",
    ]

    response = None
    last_error = None

    for model_name in fallback_models:
        for attempt in range(2):
            try:
                print(f"Generating analysis with {model_name} (attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                break
            except Exception as error:
                last_error = error
                err_str = str(error)
                print(f"{model_name} attempt {attempt + 1} failed: {error}")

                # If daily/minute quota is exhausted (429), switch model immediately without sleeping
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"{model_name} quota exhausted; switching to next fallback model...")
                    break

                # For temporary 503 overload, wait briefly once before switching model
                if attempt == 0:
                    time.sleep(5)

        if response is not None:
            break

    if response is None:
        raise RuntimeError(
            f"All Gemini fallback models failed. Last error: {last_error}"
        )

    return {
        "analysis": response.text
    }

# 4. Build LangGraph
builder = StateGraph(ResearchState)

builder.add_node("search", search_node)
builder.add_node("analyze", analysis_node)

builder.add_edge(START, "search")
builder.add_edge("search", "analyze")
builder.add_edge("analyze", END)


# 5. Compile agent
research_agent = builder.compile()


# 6. Run agent
def run_research_agent(
    topic: str,
    papers: list[dict] | None = None
):
    return research_agent.invoke({
        "topic": topic,
        "papers": papers or [],
        "analysis": ""
    })


# 7. Rank research papers
def rank_papers(papers):

    return sorted(
        papers,
        key=lambda paper: (
            paper.get("relevance_score") or 0,
            paper.get("year") or 0,
            paper.get("citations") or 0
        ),
        reverse=True
    )


# 8. Run professor research
def run_professor_research(professor_id: str):

    profile = load_professor_profile(professor_id)

    interests = profile["research_interests"]

    topic = ", ".join(interests)

    # Retrieve journal candidates
    print("\nSearching for journal candidates...")

    journal_candidates = search_papers(
        topic,
        limit=20,
        publication_type="journal"
    )

    print(
        f"Retrieved {len(journal_candidates)} journal candidates."
    )

    # Retrieve conference candidates
    print("\nSearching for conference candidates...")

    conference_candidates = search_papers(
        topic,
        limit=20,
        publication_type="conference"
    )

    print(
        f"Retrieved {len(conference_candidates)} conference candidates."
    )

    # Rank candidates
    journal_candidates = rank_papers(journal_candidates)

    conference_candidates = rank_papers(conference_candidates)

    # Select top 3 from each category
    journal_papers = journal_candidates[:3]

    conference_papers = conference_candidates[:3]

    # Label publication categories
    for paper in journal_papers:
        paper["publication_category"] = "Journal"

    for paper in conference_papers:
        paper["publication_category"] = "Conference"

    # Combine selected papers
    selected_papers = journal_papers + conference_papers

    print(
        f"\nSelected {len(selected_papers)} papers for analysis."
    )

    # Analyze selected papers with Gemini
    result = run_research_agent(
        topic,
        papers=selected_papers
    )

    return {
        "professor": profile["name"],
        "research_interests": interests,
        "analysis": result["analysis"],
        "papers": selected_papers
    }
