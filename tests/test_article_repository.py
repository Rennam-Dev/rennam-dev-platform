from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models import Article, Category, Tag
from app.repositories import articles as article_repository


def make_article(
    *,
    slug: str = "repository-article",
    section: str = "blog",
) -> Article:
    return Article(
        title="Repository Article",
        slug=slug,
        summary="Article used to test explicit persistence functions.",
        content_markdown="# Repository",
        section=section,
    )


def test_get_by_id_loads_category_and_tags() -> None:
    with SessionLocal() as db:
        category = Category(name="Architecture", slug="architecture")
        tag = Tag(name="PostgreSQL", slug="postgresql")
        article = make_article()
        article.category = category
        article.tags = [tag]
        db.add(article)
        db.commit()
        article_id = article.id

    with SessionLocal() as db:
        found = article_repository.get_by_id(db, article_id)

        assert found is not None
        assert found.category is not None
        assert found.category.slug == "architecture"
        assert {item.slug for item in found.tags} == {"postgresql"}


def test_get_by_id_returns_none_when_missing() -> None:
    with SessionLocal() as db:
        assert article_repository.get_by_id(db, 999_999) is None


def test_get_by_section_slug_respects_editorial_namespace() -> None:
    with SessionLocal() as db:
        blog = make_article(slug="same-slug", section="blog")
        journal = make_article(slug="same-slug", section="journal")
        db.add_all([blog, journal])
        db.commit()

        found_blog = article_repository.get_by_section_slug(
            db, "blog", "same-slug"
        )
        found_journal = article_repository.get_by_section_slug(
            db, "journal", "same-slug"
        )

        assert found_blog is not None
        assert found_blog.id == blog.id
        assert found_journal is not None
        assert found_journal.id == journal.id
        assert (
            article_repository.get_by_section_slug(db, "blog", "missing") is None
        )


def test_category_queries_find_existing_and_missing_rows() -> None:
    with SessionLocal() as db:
        category = Category(name="Data", slug="data")
        db.add(category)
        db.commit()

        assert article_repository.get_category_by_id(db, category.id) is category
        assert article_repository.get_category_by_slug(db, "data") is category
        assert article_repository.get_category_by_id(db, 999_999) is None
        assert article_repository.get_category_by_slug(db, "missing") is None


def test_tag_query_finds_existing_and_missing_rows() -> None:
    with SessionLocal() as db:
        tag = Tag(name="FastAPI", slug="fastapi")
        db.add(tag)
        db.commit()

        assert article_repository.get_tag_by_slug(db, "fastapi") is tag
        assert article_repository.get_tag_by_slug(db, "missing") is None


def test_repository_adds_and_flushes_without_ending_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_transaction_boundary() -> None:
        raise AssertionError("repository must not end the transaction")

    with SessionLocal() as db:
        transaction = db.begin()
        monkeypatch.setattr(db, "commit", forbidden_transaction_boundary)
        monkeypatch.setattr(db, "rollback", forbidden_transaction_boundary)
        category = Category(name="Engineering", slug="engineering")
        tag = Tag(name="SQLAlchemy", slug="sqlalchemy")
        article = make_article()
        article.category = category
        article.tags = [tag]

        article_repository.add_category(db, category)
        article_repository.add_tag(db, tag)
        article_repository.add_article(db, article)

        assert category in db.new
        assert tag in db.new
        assert article in db.new

        article_repository.flush(db)

        assert db.get_transaction() is transaction
        assert transaction.is_active
        assert category.id is not None
        assert tag.id is not None
        assert article.id is not None
        transaction.rollback()

    with SessionLocal() as db:
        assert article_repository.get_by_section_slug(
            db, "blog", "repository-article"
        ) is None
        assert article_repository.get_category_by_slug(db, "engineering") is None
        assert article_repository.get_tag_by_slug(db, "sqlalchemy") is None


def test_caller_can_commit_article_category_and_tag() -> None:
    with SessionLocal() as db:
        category = Category(name="CMS", slug="cms")
        tag = Tag(name="Markdown", slug="markdown")
        article = make_article(slug="committed-article")
        article.category = category
        article.tags = [tag]
        article_repository.add_category(db, category)
        article_repository.add_tag(db, tag)
        article_repository.add_article(db, article)
        article_repository.flush(db)
        db.commit()
        article_id = article.id

    with SessionLocal() as db:
        persisted = article_repository.get_by_id(db, article_id)

        assert persisted is not None
        assert persisted.slug == "committed-article"
        assert persisted.category is not None
        assert persisted.category.slug == "cms"
        assert {item.slug for item in persisted.tags} == {"markdown"}


def test_list_published_by_section_filters_status_and_section() -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    with SessionLocal() as db:
        db.add_all(
            [
                make_article(slug="blog-draft", section="blog"),
                Article(
                    title="Withdrawn Blog",
                    slug="withdrawn-blog",
                    summary="A draft with publication history stays private.",
                    content_markdown="# Withdrawn",
                    section="blog",
                    status="draft",
                    published_at=publication,
                ),
                Article(
                    title="Published Blog",
                    slug="published-blog",
                    summary="A public Blog article.",
                    content_markdown="# Blog",
                    section="blog",
                    status="published",
                    published_at=publication,
                ),
                Article(
                    title="Published Journal",
                    slug="published-journal",
                    summary="A public Journal article.",
                    content_markdown="# Journal",
                    section="journal",
                    status="published",
                    published_at=publication,
                ),
            ]
        )
        db.commit()

        blog = article_repository.list_published_by_section(db, "blog")
        journal = article_repository.list_published_by_section(db, "journal")

        assert [article.slug for article in blog] == ["published-blog"]
        assert [article.slug for article in journal] == ["published-journal"]


def test_list_published_by_section_orders_by_publication_then_id() -> None:
    older = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    newest = older + timedelta(days=1)
    with SessionLocal() as db:
        first_tie = Article(
            title="First tie",
            slug="first-tie",
            summary="First row at the newest timestamp.",
            content_markdown="# First tie",
            section="blog",
            status="published",
            published_at=newest,
        )
        second_tie = Article(
            title="Second tie",
            slug="second-tie",
            summary="Second row at the newest timestamp.",
            content_markdown="# Second tie",
            section="blog",
            status="published",
            published_at=newest,
        )
        older_article = Article(
            title="Older",
            slug="older",
            summary="An older article.",
            content_markdown="# Older",
            section="blog",
            status="published",
            published_at=older,
        )
        db.add_all([first_tie, second_tie, older_article])
        db.commit()

        found = article_repository.list_published_by_section(db, "blog")

        assert [article.slug for article in found] == [
            "second-tie",
            "first-tie",
            "older",
        ]


def test_get_published_by_slug_requires_published_status_and_section() -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    with SessionLocal() as db:
        blog = Article(
            title="Blog namespace",
            slug="same-public-slug",
            summary="Published in Blog.",
            content_markdown="# Blog",
            section="blog",
            status="published",
            published_at=publication,
        )
        journal = Article(
            title="Journal namespace",
            slug="same-public-slug",
            summary="Published in Journal.",
            content_markdown="# Journal",
            section="journal",
            status="published",
            published_at=publication,
        )
        withdrawn = Article(
            title="Withdrawn",
            slug="withdrawn",
            summary="Publication history must not make this public.",
            content_markdown="# Withdrawn",
            section="blog",
            status="draft",
            published_at=publication,
        )
        db.add_all([blog, journal, withdrawn])
        db.commit()

        found_blog = article_repository.get_published_by_slug(
            db, "blog", "same-public-slug"
        )
        found_journal = article_repository.get_published_by_slug(
            db, "journal", "same-public-slug"
        )

        assert found_blog is not None
        assert found_blog.id == blog.id
        assert found_journal is not None
        assert found_journal.id == journal.id
        assert (
            article_repository.get_published_by_slug(db, "blog", "withdrawn")
            is None
        )
        assert (
            article_repository.get_published_by_slug(
                db, "journal", "blog-only-missing"
            )
            is None
        )


def test_public_queries_eager_load_category_and_tags() -> None:
    publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    with SessionLocal() as db:
        category = Category(name="Public Engineering", slug="public-engineering")
        tag = Tag(name="Public SQL", slug="public-sql")
        article = Article(
            title="Public relationships",
            slug="public-relationships",
            summary="Relationships remain usable after the session closes.",
            content_markdown="# Public relationships",
            section="blog",
            status="published",
            published_at=publication,
            category=category,
            tags=[tag],
        )
        db.add(article)
        db.commit()

    with SessionLocal() as db:
        listed = article_repository.list_published_by_section(db, "blog")
        detailed = article_repository.get_published_by_slug(
            db, "blog", "public-relationships"
        )

    assert listed[0].category is not None
    assert listed[0].category.slug == "public-engineering"
    assert {tag.slug for tag in listed[0].tags} == {"public-sql"}
    assert detailed is not None
    assert detailed.category is not None
    assert detailed.category.slug == "public-engineering"
    assert {tag.slug for tag in detailed.tags} == {"public-sql"}
