
import requests
import time


def reconstruct_abstract(inverted_index):
    """
    Convert OpenAlex abstract inverted index
    into normal readable text.
    """

    if not inverted_index:
        return None

    words = {}

    for word, positions in inverted_index.items():
        for position in positions:
            words[position] = word

    return " ".join(
        words[position]
        for position in sorted(words)
    )


def search_papers(
    topic: str,
    limit: int = 5,
    publication_type: str = None
):
    """
    Search OpenAlex for academic publications.

    publication_type:
        None        -> All publication types
        "journal"   -> Journal articles
        "conference"-> Conference publications
    """

    url = "https://api.openalex.org/works"

    # Retrieve extra candidates because some results
    # will be excluded by the publication-type filter.
    candidate_limit = 50
    #candidate_limit = min(max(limit * 10, 50), 100)

    params = {
        "search": topic,
        "per-page": candidate_limit,
        "sort": "relevance_score:desc"
    }

    response = None

    # Retry temporary API errors.
    for attempt in range(4):

        try:
            response = requests.get(
                url,
                params=params,
                timeout=30
            )

            if response.status_code == 429 or response.status_code >= 500:

                if attempt == 3:
                    response.raise_for_status()

                retry_after = response.headers.get("Retry-After")

                try:
                    wait_time = float(retry_after)
                except (TypeError, ValueError):
                    wait_time = 5 * (2 ** attempt)

                print(
                    f"OpenAlex temporarily unavailable. "
                    f"Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

            else:
                response.raise_for_status()
                break

        except requests.RequestException:

            if attempt == 3:
                raise

            wait_time = 5 * (2 ** attempt)

            print(
                f"OpenAlex request failed. "
                f"Retrying in {wait_time} seconds..."
            )

            time.sleep(wait_time)

    data = response.json()

    papers = []

    for item in data.get("results", []):

        # Publication information
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}

        source_type = source.get("type")

        work_type = item.get("type")

        # Filter journal and conference publications.
        if publication_type == "journal":

            if work_type != "article" or source_type != "journal":
                continue

        elif publication_type == "conference":

            if work_type != "conference-paper" or source_type != "conference":
                continue

        abstract = reconstruct_abstract(
            item.get("abstract_inverted_index")
        )

        paper = {

            "title": item.get("title"),

            "year": item.get("publication_year"),

            "doi": item.get("doi"),

            "citations": item.get("cited_by_count"),

            "relevance_score": item.get("relevance_score"),

            "type": work_type,

            "type_crossref": item.get("type_crossref"),

            "publication_source": source.get("display_name"),       

            "publication_source_type": source_type,

            "issn": source.get("issn"),

            "issn_l": source.get("issn_l"),

            "publisher": source.get("host_organization_name"),

            "url": item.get("doi") or item.get("id"),

            "abstract": abstract,

            "authors": [
                authorship.get("author", {}).get("display_name")
                for authorship in item.get("authorships", [])
            ],

            "institutions": [
                institution.get("display_name")
                for authorship in item.get("authorships", [])
                for institution in authorship.get("institutions", [])
            ]
        }

        papers.append(paper)

        if len(papers) >= limit:
            break

    return papers
