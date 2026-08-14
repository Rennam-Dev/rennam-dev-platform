import re
import xml.etree.ElementTree as ElementTree
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from app import web
from app.core.database import SessionLocal
from app.models import Article, Category, Project, Tag
from app.routes import public as public_routes


def add_article(
    *,
    title: str,
    slug: str,
    section: str,
    status: str = "published",
    published_at: datetime | None = None,
    summary: str | None = None,
    content_markdown: str | None = None,
    category: Category | None = None,
    tags: list[Tag] | None = None,
) -> None:
    with SessionLocal() as db:
        db.add(
            Article(
                title=title,
                slug=slug,
                summary=summary or f"Summary for {title}.",
                content_markdown=content_markdown or f"## {title}",
                section=section,
                status=status,
                published_at=published_at,
                category=category,
                tags=tags or [],
            )
        )
        db.commit()


def test_blog_and_journal_lists_show_only_their_published_articles(client) -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    add_article(
        title="Published Blog",
        slug="published-blog",
        section="blog",
        published_at=publication,
        category=Category(name="Architecture", slug="architecture"),
        tags=[Tag(name="FastAPI", slug="fastapi")],
    )
    add_article(
        title="Published Journal",
        slug="published-journal",
        section="journal",
        published_at=publication,
    )
    add_article(
        title="Draft Blog",
        slug="draft-blog",
        section="blog",
        status="draft",
    )
    add_article(
        title="Withdrawn Blog",
        slug="withdrawn-blog",
        section="blog",
        status="draft",
        published_at=publication,
    )

    blog = client.get("/blog")
    journal = client.get("/journal")

    assert blog.status_code == 200
    assert "Published Blog" in blog.text
    assert "Summary for Published Blog." in blog.text
    assert "2026-08-10" in blog.text
    assert "Architecture" in blog.text
    assert "FastAPI" in blog.text
    assert "Published Journal" not in blog.text
    assert "Draft Blog" not in blog.text
    assert "Withdrawn Blog" not in blog.text

    assert journal.status_code == 200
    assert "Diário de Engenharia" in journal.text
    assert "Engineering Journal" not in journal.text
    assert "Published Journal" in journal.text
    assert "Published Blog" not in journal.text
    assert "Draft Blog" not in journal.text


def test_public_article_details_enforce_section_status_and_slug(client) -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    add_article(
        title="Blog Same Slug",
        slug="same-slug",
        section="blog",
        published_at=publication,
    )
    add_article(
        title="Journal Same Slug",
        slug="same-slug",
        section="journal",
        published_at=publication,
    )
    add_article(
        title="Private Draft",
        slug="private-draft",
        section="blog",
        status="draft",
    )
    add_article(
        title="Withdrawn Draft",
        slug="withdrawn-draft",
        section="blog",
        status="draft",
        published_at=publication,
    )
    add_article(
        title="Journal Only",
        slug="journal-only",
        section="journal",
        published_at=publication,
    )

    blog = client.get("/blog/same-slug")
    journal = client.get("/journal/same-slug")

    assert blog.status_code == 200
    assert "Blog Same Slug" in blog.text
    assert "Journal Same Slug" not in blog.text
    assert journal.status_code == 200
    assert "Journal Same Slug" in journal.text
    assert "Blog Same Slug" not in journal.text

    for path in (
        "/blog/private-draft",
        "/blog/withdrawn-draft",
        "/blog/journal-only",
        "/journal/private-draft",
        "/journal/missing",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert "Página não encontrada" in response.text


def test_public_article_detail_renders_markdown_and_neutralizes_xss(client) -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    add_article(
        title='<script>alert("title")</script>',
        slug="safe-rendering",
        section="blog",
        published_at=publication,
        summary='<img src=x onerror="alert(1)">',
        content_markdown="""## Safe heading

Markdown **seguro**.

<script>alert(2)</script>

[unsafe](javascript:alert(3))

<a href="https://example.com" onclick="alert(4)">safe link</a>

<img src="x" onerror="alert(5)">
""",
        category=Category(
            name='<script>alert("category")</script>',
            slug="malicious-category",
        ),
        tags=[
            Tag(
                name='<img src=x onerror="alert(6)">',
                slug="malicious-tag",
            )
        ],
    )

    response = client.get("/blog/safe-rendering")

    assert response.status_code == 200
    assert "<h2>Safe heading</h2>" in response.text
    assert "<strong>seguro</strong>" in response.text
    assert "&lt;script&gt;alert(&#34;title&#34;)&lt;/script&gt;" in response.text
    rendered = response.text.lower()
    assert "<script" not in rendered
    assert "<img" not in rendered
    assert 'href="javascript:' not in rendered
    assert '<a href="https://example.com">safe link</a>' in rendered
    assert re.search(r"<[^>]+\sonclick\s*=", rendered) is None


def test_public_article_order_is_deterministic(client) -> None:
    older = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    newest = older + timedelta(days=1)
    add_article(
        title="First Tie",
        slug="first-tie",
        section="blog",
        published_at=newest,
    )
    add_article(
        title="Second Tie",
        slug="second-tie",
        section="blog",
        published_at=newest,
    )
    add_article(
        title="Older Article",
        slug="older-article",
        section="blog",
        published_at=older,
    )

    response = client.get("/blog")

    assert response.status_code == 200
    assert response.text.index("Second Tie") < response.text.index("First Tie")
    assert response.text.index("First Tie") < response.text.index("Older Article")


def test_home_shows_only_two_recent_published_blog_articles(client) -> None:
    older = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    newest = older + timedelta(days=1)
    add_article(
        title="First Home Tie",
        slug="first-home-tie",
        section="blog",
        published_at=newest,
    )
    add_article(
        title="Second Home Tie",
        slug="second-home-tie",
        section="blog",
        published_at=newest,
    )
    add_article(
        title="Older Home Article",
        slug="older-home-article",
        section="blog",
        published_at=older,
    )
    add_article(
        title="Home Draft",
        slug="home-draft",
        section="blog",
        status="draft",
    )
    add_article(
        title="Withdrawn Home Draft",
        slug="withdrawn-home-draft",
        section="blog",
        status="draft",
        published_at=newest,
    )
    add_article(
        title="Journal Excluded From Home",
        slug="journal-excluded-from-home",
        section="journal",
        published_at=newest,
    )

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.index("Second Home Tie") < response.text.index(
        "First Home Tie"
    )
    assert 'href="/blog/second-home-tie"' in response.text
    assert 'href="/blog/first-home-tie"' in response.text
    assert "2026-08-10" in response.text
    assert "Older Home Article" not in response.text
    assert "Home Draft" not in response.text
    assert "Withdrawn Home Draft" not in response.text
    assert "Journal Excluded From Home" not in response.text


def test_sitemap_uses_published_articles_from_both_sections(client) -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    with SessionLocal() as db:
        db.add_all(
            [
                Project(
                    title="Published Sitemap Project",
                    slug="published-sitemap-project",
                    summary="A published Project belongs in the sitemap.",
                    visibility="published",
                ),
                Project(
                    title="Draft Sitemap Project",
                    slug="draft-sitemap-project",
                    summary="A draft Project stays private.",
                    visibility="draft",
                ),
            ]
        )
        db.commit()
    add_article(
        title="Published Blog Sitemap Article",
        slug="shared-sitemap-slug",
        section="blog",
        published_at=publication,
    )
    add_article(
        title="Published Journal Sitemap Article",
        slug="shared-sitemap-slug",
        section="journal",
        published_at=publication,
    )
    add_article(
        title="Sitemap Draft",
        slug="sitemap-draft",
        section="blog",
        status="draft",
    )
    add_article(
        title="Withdrawn Sitemap Draft",
        slug="withdrawn-sitemap-draft",
        section="journal",
        status="draft",
        published_at=publication,
    )

    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    document = ElementTree.fromstring(response.content)
    paths = {
        urlsplit(location.text or "").path
        for location in document.findall(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}url/"
            "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )
    }

    assert "/blog" in paths
    assert "/journal" in paths
    assert "/projetos/published-sitemap-project" in paths
    assert "/blog/shared-sitemap-slug" in paths
    assert "/journal/shared-sitemap-slug" in paths
    assert "/projetos/draft-sitemap-project" not in paths
    assert "/blog/sitemap-draft" not in paths
    assert "/journal/withdrawn-sitemap-draft" not in paths
    assert not any(path.startswith("/admin") for path in paths)
    assert not any("preview" in path for path in paths)
    assert "/admin/login" not in paths


def test_public_navigation_contains_active_engineering_journal(client) -> None:
    response = client.get("/journal")

    assert response.status_code == 200
    desktop = re.search(
        r'<div class="nav__desktop">(?P<body>.*?)</div>',
        response.text,
        re.DOTALL,
    )
    mobile = re.search(
        r'<div class="nav__mobile-panel">(?P<body>.*?)</div>',
        response.text,
        re.DOTALL,
    )
    assert desktop is not None
    assert mobile is not None
    for navigation in (desktop.group("body"), mobile.group("body")):
        assert (
            '<a class="is-active" href="/journal">'
            "Diário de Engenharia</a>"
        ) in navigation
    assert "Engineering Journal" not in response.text


def test_public_article_surfaces_do_not_use_legacy_filesystem_loader(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    add_article(
        title="SQL Blog",
        slug="sql-blog",
        section="blog",
        published_at=publication,
    )
    add_article(
        title="SQL Journal",
        slug="sql-journal",
        section="journal",
        published_at=publication,
    )

    def forbidden_glob(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("public routes must not read legacy Markdown")

    monkeypatch.setattr(Path, "glob", forbidden_glob)

    assert client.get("/").status_code == 200
    assert client.get("/sitemap.xml").status_code == 200
    assert client.get("/blog").status_code == 200
    assert client.get("/blog/sql-blog").status_code == 200
    assert client.get("/journal").status_code == 200
    assert client.get("/journal/sql-journal").status_code == 200
    assert not hasattr(web, "load_posts")
    assert not hasattr(web, "load_post")
    assert not hasattr(public_routes, "load_posts")
    assert not hasattr(public_routes, "load_post")
