# 01_paper_schema.py
# this is defining the common structure for every research paper.

def create_paper(
    paper_id="",
    title="",
    authors=None,
    abstract="",
    year=None,
    doi="",
    url="",
    source="",
    journal="",
    publication_type=""
):
    """
    Standard Paper structure for ResearchMate.
    """

    if authors is None:
        authors = []

    paper = {
        "paper_id": paper_id,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "year": year,
        "doi": doi,
        "url": url,
        "source": source,
        "journal": journal,
        "publication_type": publication_type
    }

    return paper


# Test the standard structure
if __name__ == "__main__":

    sample_paper = create_paper(
        paper_id="TEST001",
        title="Example Research Paper",
        authors=["John Smith", "Mary Jones"],
        abstract="This is an example abstract.",
        year=2025,
        doi="10.1234/example",
        url="https://example.com",
        source="Test",
        journal="Example Journal",
        publication_type="journal-article"
    )

    print("ResearchMate Standard Paper Structure:")
    print()

    for key, value in sample_paper.items():
        print(f"{key}: {value}")