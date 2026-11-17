from backend.agents.research_agent import run_professor_research

result = run_professor_research("professor_001")

print("\n========== PROFESSOR ==========\n")
print(result["professor"])

print("\n========== RESEARCH INTERESTS ==========\n")
for interest in result["research_interests"]:
    print("-", interest)

print("\n========== AI RESEARCH ANALYSIS ==========\n")
print(result["analysis"])

print("\n========== PAPERS FOUND ==========\n")
for paper in result["papers"]:
    print("-", paper["title"])
    print("  Year:", paper["year"])
    print("  Citations:", paper["citations"])
    print("  URL:", paper["url"])