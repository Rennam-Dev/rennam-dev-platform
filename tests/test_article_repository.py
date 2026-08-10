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
