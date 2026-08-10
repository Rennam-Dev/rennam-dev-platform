from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal, engine
from app.models import Article, Category, Tag, article_tags


def make_article(
    *,
    slug: str = "test-article",
    section: str = "blog",
    status: str | None = None,
    category_id: int | None = None,
    published_at: datetime | None = None,
) -> Article:
    article = Article(
        title="Test Article",
        slug=slug,
        summary="Article used to exercise persistence constraints.",
        content_markdown="# Safe Markdown",
        section=section,
        category_id=category_id,
        published_at=published_at,
    )
    if status is not None:
        article.status = status
    return article


def test_article_metadata_has_only_the_approved_defaults() -> None:
    section = Article.__table__.c.section
    status = Article.__table__.c.status
    created_at = Article.__table__.c.created_at
    updated_at = Article.__table__.c.updated_at

    assert section.default is None
    assert section.server_default is None
    assert status.default is not None
    assert status.default.arg == "draft"
    assert status.server_default is not None
    assert str(status.server_default.arg) == "draft"
    assert created_at.server_default is not None
    assert updated_at.server_default is not None

    database_columns = {
        column["name"]: column for column in inspect(engine).get_columns("articles")
    }
    assert database_columns["section"]["default"] is None
    assert "draft" in database_columns["status"]["default"]
    assert "now()" in database_columns["created_at"]["default"]
    assert "now()" in database_columns["updated_at"]["default"]


def test_database_supplies_timestamps_when_sql_omits_them() -> None:
    with SessionLocal() as db:
        persisted = db.execute(
            text(
                """
                INSERT INTO articles (
                    title,
                    slug,
                    summary,
                    content_markdown,
                    section
                )
                VALUES (
                    :title,
                    :slug,
                    :summary,
                    :content_markdown,
                    :section
                )
                RETURNING status, created_at, updated_at
                """
            ),
            {
                "title": "Database Defaults",
                "slug": "database-defaults",
                "summary": "Timestamps are assigned by PostgreSQL.",
                "content_markdown": "# Database defaults",
                "section": "blog",
            },
        ).one()

        assert persisted.status == "draft"
        assert persisted.created_at is not None
        assert persisted.updated_at is not None


def test_valid_category_tag_and_draft_article_relationships() -> None:
    with SessionLocal() as db:
        category = Category(name="Engineering", slug="engineering")
        tag = Tag(name="PostgreSQL", slug="postgresql")
        article = make_article()
        article.category = category
        article.tags = [tag]
        db.add(article)
        db.commit()
        article_id = article.id
        category_id = category.id
        tag_id = tag.id

    with SessionLocal() as db:
        persisted_article = db.get(Article, article_id)
        persisted_category = db.get(Category, category_id)
        persisted_tag = db.get(Tag, tag_id)

        assert persisted_article is not None
        assert persisted_article.status == "draft"
        assert persisted_article.created_at is not None
        assert persisted_article.updated_at is not None
        assert persisted_article.category is not None
        assert persisted_article.category.slug == "engineering"
        assert {tag.slug for tag in persisted_article.tags} == {"postgresql"}

        assert persisted_category is not None
        assert {article.slug for article in persisted_category.articles} == {
            "test-article"
        }
        assert persisted_tag is not None
        assert {article.slug for article in persisted_tag.articles} == {
            "test-article"
        }


def test_section_is_required_without_a_default() -> None:
    with SessionLocal() as db:
        article = Article(
            title="Missing Section",
            slug="missing-section",
            summary="The database must reject this article.",
            content_markdown="No section was provided.",
        )
        db.add(article)

        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize("section", ["news", "", "BLOG"])
def test_invalid_section_is_rejected(section: str) -> None:
    with SessionLocal() as db:
        db.add(make_article(section=section))

        with pytest.raises(IntegrityError):
            db.commit()


def test_invalid_status_is_rejected() -> None:
    with SessionLocal() as db:
        db.add(make_article(status="scheduled"))

        with pytest.raises(IntegrityError):
            db.commit()


def test_published_article_requires_published_at() -> None:
    with SessionLocal() as db:
        db.add(make_article(status="published"))

        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize("status", ["draft", "published"])
def test_published_at_is_valid_for_draft_and_published_statuses(status: str) -> None:
    first_publication = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    with SessionLocal() as db:
        article = make_article(
            status=status,
            published_at=first_publication,
        )
        db.add(article)
        db.commit()

        assert article.status == status
        assert article.published_at == first_publication


def test_duplicate_slug_in_same_section_is_rejected() -> None:
    with SessionLocal() as db:
        db.add_all(
            [
                make_article(),
                make_article(),
            ]
        )

        with pytest.raises(IntegrityError):
            db.commit()


def test_same_slug_in_blog_and_journal_is_allowed() -> None:
    with SessionLocal() as db:
        blog_article = make_article(section="blog")
        journal_article = make_article(section="journal")
        db.add_all([blog_article, journal_article])
        db.commit()

        assert blog_article.slug == journal_article.slug
        assert blog_article.id != journal_article.id


def test_invalid_category_id_is_rejected_by_foreign_key() -> None:
    with SessionLocal() as db:
        db.add(make_article(category_id=999_999))

        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize(
    ("model", "name"),
    [
        (Category, "Category"),
        (Tag, "Tag"),
    ],
)
def test_taxonomy_slug_is_unique(model: type[Category] | type[Tag], name: str) -> None:
    with SessionLocal() as db:
        db.add_all(
            [
                model(name=f"{name} One", slug="duplicate"),
                model(name=f"{name} Two", slug="duplicate"),
            ]
        )

        with pytest.raises(IntegrityError):
            db.commit()


def test_duplicate_article_tag_association_is_rejected() -> None:
    with SessionLocal() as db:
        article = make_article()
        tag = Tag(name="FastAPI", slug="fastapi")
        article.tags = [tag]
        db.add(article)
        db.commit()

        with pytest.raises(IntegrityError):
            db.execute(
                article_tags.insert().values(
                    article_id=article.id,
                    tag_id=tag.id,
                )
            )


def test_database_has_only_the_planned_article_indexes() -> None:
    article_indexes = {
        index["name"]: index for index in inspect(engine).get_indexes("articles")
    }

    assert set(article_indexes) == {
        "ix_articles_category_id",
        "ix_articles_section_status_published_at",
        "uq_articles_section_slug",
    }
    assert article_indexes["uq_articles_section_slug"]["unique"] is True
    assert (
        article_indexes["uq_articles_section_slug"]["duplicates_constraint"]
        == "uq_articles_section_slug"
    )
