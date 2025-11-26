"""Helper functions for generating test HTML content."""

from pathlib import Path


def create_test_html(
    title: str, body: str, links: list[str] | None = None, external_links: list[str] | None = None
) -> str:
    """
    Generate HTML test content with consistent structure.

    Args:
        title: Page title
        body: Body content (will be wrapped in <p> tag)
        links: List of internal links (relative paths)
        external_links: List of external URLs

    Returns:
        Complete HTML document as string
    """
    links_html = ""
    if links or external_links:
        all_links: list[str] = []
        if links:
            all_links.extend(f'<a href="{url}">{url}</a>' for url in links)
        if external_links:
            all_links.extend(f'<a href="{url}">{url}</a>' for url in external_links)

        links_html = "<p>Links: " + " | ".join(all_links) + "</p>"

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
</head>
<body>
    <h1>{title}</h1>
    <p>{body}</p>
    {links_html}
</body>
</html>"""


def build_minimal_archive(base_dir: Path) -> None:
    """
    Construct complete minimal test archive with relative linking.

    Args:
        base_dir: Directory to create archive in
    """
    # Create subdirectories
    (base_dir / "subdir").mkdir(parents=True, exist_ok=True)
    (base_dir / "subdir" / "deep").mkdir(parents=True, exist_ok=True)

    # Root index page
    (base_dir / "index.html").write_text(
        create_test_html(
            "SPICE Documentation Index",
            "Welcome to the SPICE toolkit documentation. This is a test archive.",
            links=["page_kernels.html", "page_time.html", "page_links.html", "subdir/nested.html"],
        )
    )

    # Page about kernels
    (base_dir / "page_kernels.html").write_text(
        create_test_html(
            "SPICE Kernels Guide",
            "Information about SPICE kernel files including SPK ephemeris "
            "kernels and CK attitude kernels.",
            links=["page_time.html", "index.html"],
        )
    )

    # Page about time systems
    (base_dir / "page_time.html").write_text(
        create_test_html(
            "Time Systems in SPICE",
            "Documentation about ephemeris time, UTC, and other time systems "
            "used in SPICE calculations.",
            links=["index.html", "page_kernels.html"],
        )
    )

    # Page with various links for extraction testing
    (base_dir / "page_links.html").write_text(
        create_test_html(
            "Links Test Page",
            "This page contains various types of links for testing link extraction.",
            links=["index.html", "./page_kernels.html", "subdir/nested.html"],
            external_links=["https://naif.jpl.nasa.gov/", "https://example.com/test"],
        )
    )

    # Nested page with relative link
    (base_dir / "subdir" / "nested.html").write_text(
        create_test_html(
            "Nested Page",
            "This is a nested page in a subdirectory with relative links.",
            links=["../index.html", "../page_kernels.html", "deep/deeper.html"],
        )
    )

    # Deeply nested page
    (base_dir / "subdir" / "deep" / "deeper.html").write_text(
        create_test_html(
            "Deeply Nested Page",
            "This is a deeply nested page for testing path resolution.",
            links=["../../index.html", "../nested.html"],
        )
    )
