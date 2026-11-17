from backend.workflows.research_workflow import run_research

result = run_research("AI Agents")

for paper in result["papers"]:
    print("\nTitle:", paper["title"])
    print("Year:", paper["year"])
    print("Citations:", paper["citations"])
    print("URL:", paper["url"])