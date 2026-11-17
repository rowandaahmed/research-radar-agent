from backend.agents.research_agent import run_research_agent

result = run_research_agent("AI Agents")

print("\n========== RESEARCH ANALYSIS ==========\n")
print(result["analysis"])

print("\n========== PAPERS RETRIEVED ==========\n")

for paper in result["papers"]:
    print("-", paper["title"])