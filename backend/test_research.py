from backend.tools.openalex_tool import search_papers

results = search_papers("AI Agents", limit=5)

for paper in results:
    print("\nTitle:", paper["title"])
    print("Year:", paper["year"])
    print("Citations:", paper["citations"])
    print("URL:", paper["url"])
    print("Authors:", paper["authors"])
    print("Institutions:", paper["institutions"])