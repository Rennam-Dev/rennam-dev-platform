from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import BASE_DIR
from app.core.database import SessionLocal
from app.models import Article, Category, Tag
from app.repositories import articles as article_repository
from app.scripts import import_legacy_blog

LEGACY_BLOG_DIR = BASE_DIR / "content" / "blog"
IMPORT_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def write_legacy_post(
    directory: Path,
    *,
    slug: str = "legacy-post",
    published_date: str = "2026-07-01",
    tags: str = '["FastAPI", "Arquitetura"]',
) -> Path:
    path = directory / f"{slug}.md"
    path.write_text(
        f'''---
titulo: "Legacy Post"
data: "{published_date}"
resumo: "Historical content imported through the explicit cutover."
tags: {tags}
---

## Legacy body

Markdown **preservado**.
''',
        encoding="utf-8",
    )
    return path


def test_load_legacy_articles_preserves_real_frontmatter_and_uses_utc() -> None:
    articles = import_legacy_blog.load_legacy_articles(LEGACY_BLOG_DIR)
    by_slug = {article.slug: article for article in articles}

    assert set(by_slug) == {"ola-mundo", "por-que-fastapi"}
    assert by_slug["ola-mundo"].title == "Olá, mundo"
    assert by_slug["ola-mundo"].summary == (
        "Por que esse site existe e o que você vai encontrar aqui."
    )
    assert by_slug["ola-mundo"].tags == ("meta",)
    assert "Cada post aqui é um arquivo markdown" in (
        by_slug["ola-mundo"].content_markdown
    )
    assert by_slug["ola-mundo"].published_at == datetime(
        2026, 7, 3, tzinfo=UTC
    )
    assert by_slug["ola-mundo"].published_at.tzinfo is UTC
    assert by_slug["por-que-fastapi"].title == (
        "Por que esse portfólio roda em FastAPI"
    )
    assert by_slug["por-que-fastapi"].tags == ("fastapi", "arquitetura")
    assert by_slug["por-que-fastapi"].published_at == datetime(
        2026, 7, 5, tzinfo=UTC
    )


def test_import_legacy_blog_preserves_content_and_taxonomy() -> None:
    expected = {
        article.slug: article
        for article in import_legacy_blog.load_legacy_articles(LEGACY_BLOG_DIR)
    }
    with SessionLocal() as db:
        report = import_legacy_blog.import_legacy_blog(
            db,
            LEGACY_BLOG_DIR,
            now=IMPORT_NOW,
        )

        assert report.created == 2
        assert report.unchanged == 0
        for slug, source in expected.items():
            article = article_repository.get_published_by_slug(db, "blog", slug)
            assert article is not None
            assert article.title == source.title
            assert article.summary == source.summary
            assert article.content_markdown == source.content_markdown
            assert article.section == "blog"
            assert article.status == "published"
            assert article.published_at == source.published_at
            assert article.published_at.tzinfo is not None
            assert article.published_at.utcoffset() == timedelta(0)
            assert article.category is not None
            assert article.category.name == "Conteúdo legado"
            assert article.category.slug == "conteudo-legado"
            assert {tag.name for tag in article.tags} == set(source.tags)


def test_imported_legacy_slugs_are_served_by_the_public_sql_runtime(client) -> None:
    with SessionLocal() as db:
        import_legacy_blog.import_legacy_blog(
            db,
            LEGACY_BLOG_DIR,
            now=IMPORT_NOW,
        )

    hello = client.get("/blog/ola-mundo")
    fastapi = client.get("/blog/por-que-fastapi")

    assert hello.status_code == 200
    assert "Olá, mundo" in hello.text
    assert fastapi.status_code == 200
    assert "Por que esse portfólio roda em FastAPI" in fastapi.text


def test_second_equivalent_import_is_a_no_op() -> None:
    with SessionLocal() as db:
        first = import_legacy_blog.import_legacy_blog(
            db,
            LEGACY_BLOG_DIR,
            now=IMPORT_NOW,
        )
        article = article_repository.get_published_by_slug(
            db, "blog", "ola-mundo"
        )
        assert article is not None
        original_updated_at = article.updated_at

        second = import_legacy_blog.import_legacy_blog(
            db,
            LEGACY_BLOG_DIR,
            now=IMPORT_NOW,
        )

        assert first.created == 2
        assert second.created == 0
        assert second.unchanged == 2
        assert db.scalar(select(func.count()).select_from(Article)) == 2
        unchanged = article_repository.get_published_by_slug(
            db, "blog", "ola-mundo"
        )
        assert unchanged is not None
        assert unchanged.updated_at == original_updated_at


@pytest.mark.parametrize(
    ("field", "divergent_value"),
    [
        ("title", "Manually edited title"),
        ("summary", "Manually edited summary"),
        ("content_markdown", "# Manually edited content"),
        ("status", "draft"),
        ("published_at", datetime(2026, 7, 4, tzinfo=UTC)),
    ],
)
def test_import_refuses_divergent_editorial_fields(
    field: str,
    divergent_value: object,
) -> None:
    with SessionLocal() as db:
        import_legacy_blog.import_legacy_blog(db, LEGACY_BLOG_DIR, now=IMPORT_NOW)
        article = article_repository.get_by_section_slug(db, "blog", "ola-mundo")
        assert article is not None
        setattr(article, field, divergent_value)
        db.commit()

        with pytest.raises(import_legacy_blog.LegacyBlogImportError) as error:
            import_legacy_blog.import_legacy_blog(
                db,
                LEGACY_BLOG_DIR,
                now=IMPORT_NOW,
            )

        assert "blog/ola-mundo" in str(error.value)
        assert "diverge" in str(error.value)
        persisted = article_repository.get_by_section_slug(db, "blog", "ola-mundo")
        assert persisted is not None
        assert getattr(persisted, field) == divergent_value
        assert db.scalar(select(func.count()).select_from(Article)) == 2


def test_import_refuses_divergent_category_and_tags() -> None:
    with SessionLocal() as db:
        import_legacy_blog.import_legacy_blog(db, LEGACY_BLOG_DIR, now=IMPORT_NOW)
        article = article_repository.get_by_section_slug(db, "blog", "ola-mundo")
        assert article is not None
        article.category = Category(name="Manual", slug="manual")
        article.tags = [Tag(name="Manual", slug="manual")]
        db.commit()

        with pytest.raises(import_legacy_blog.LegacyBlogImportError):
            import_legacy_blog.import_legacy_blog(
                db,
                LEGACY_BLOG_DIR,
                now=IMPORT_NOW,
            )

        persisted = article_repository.get_by_section_slug(db, "blog", "ola-mundo")
        assert persisted is not None
        assert persisted.category is not None
        assert persisted.category.slug == "manual"
        assert {tag.slug for tag in persisted.tags} == {"manual"}


def test_tag_order_case_and_audit_timestamps_do_not_create_false_conflict() -> None:
    with SessionLocal() as db:
        import_legacy_blog.import_legacy_blog(db, LEGACY_BLOG_DIR, now=IMPORT_NOW)
        article = article_repository.get_by_section_slug(
            db, "blog", "por-que-fastapi"
        )
        assert article is not None
        article.tags = list(reversed(article.tags))
        for tag in article.tags:
            tag.name = tag.name.upper()
        article.created_at -= timedelta(days=1)
        article.updated_at += timedelta(days=1)
        db.commit()

        report = import_legacy_blog.import_legacy_blog(
            db,
            LEGACY_BLOG_DIR,
            now=IMPORT_NOW,
        )

        assert report.created == 0
        assert report.unchanged == 2


def test_future_publication_date_is_rejected(tmp_path: Path) -> None:
    write_legacy_post(tmp_path, published_date="2026-08-14")

    with SessionLocal() as db:
        with pytest.raises(import_legacy_blog.LegacyBlogImportError) as error:
            import_legacy_blog.import_legacy_blog(
                db,
                tmp_path,
                now=IMPORT_NOW,
            )

        assert "futura" in str(error.value)
        assert db.scalar(select(func.count()).select_from(Article)) == 0


def test_empty_legacy_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(import_legacy_blog.LegacyBlogImportError) as error:
        import_legacy_blog.load_legacy_articles(tmp_path)

    assert "nenhum arquivo Markdown" in str(error.value)


def test_import_normalizes_duplicate_tags_that_only_differ_by_case(
    tmp_path: Path,
) -> None:
    write_legacy_post(tmp_path, tags='["FastAPI", "fastapi", "FASTAPI"]')

    with SessionLocal() as db:
        report = import_legacy_blog.import_legacy_blog(
            db,
            tmp_path,
            now=IMPORT_NOW,
        )
        article = article_repository.get_published_by_slug(
            db, "blog", "legacy-post"
        )

        assert report.created == 1
        assert article is not None
        assert [(tag.name, tag.slug) for tag in article.tags] == [
            ("FastAPI", "fastapi")
        ]


def test_invalid_tag_collision_is_reported_as_controlled_import_error(
    tmp_path: Path,
) -> None:
    write_legacy_post(tmp_path, tags='["C++", "C#"]')

    with SessionLocal() as db:
        with pytest.raises(import_legacy_blog.LegacyBlogImportError) as error:
            import_legacy_blog.import_legacy_blog(
                db,
                tmp_path,
                now=IMPORT_NOW,
            )

        assert "tags:" in str(error.value)
        assert db.scalar(select(func.count()).select_from(Article)) == 0


def test_import_failure_rolls_back_article_and_new_taxonomy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_legacy_post(tmp_path)
    original_flush = article_repository.flush

    def fail_after_flush(db) -> None:
        original_flush(db)
        raise RuntimeError("simulated import failure")

    monkeypatch.setattr(article_repository, "flush", fail_after_flush)

    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="simulated import failure"):
            import_legacy_blog.import_legacy_blog(
                db,
                tmp_path,
                now=IMPORT_NOW,
            )

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Article)) == 0
        assert db.scalar(select(func.count()).select_from(Category)) == 0
        assert db.scalar(select(func.count()).select_from(Tag)) == 0
