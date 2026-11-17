
from backend.tools.openalex_tool import search_papers


papers = search_papers(
    "AI Agents",
    limit=5
)

for index, paper in enumerate(papers, start=1):

    print(f"\n========== PAPER {index} ==========")

    print("Title:", paper["title"])
    print("Year:", paper["year"])
    print("URL:", paper["url"])

    if paper["abstract"]:
        print("\nABSTRACT:")
        print(paper["abstract"][:1000])
    else:
        print("\nABSTRACT: Not available")
