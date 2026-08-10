from collections import Counter
from datetime import UTC, datetime

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Tag
from app.repositories import articles as article_repository
from app.schemas.article import ArticleForm, CategoryForm
from app.services import articles as article_service

EXPANDING_UNICODE_NAME = "\N{LATIN SMALL LIGATURE FFI}" * 27


def make_article_form(**overrides: object) -> ArticleForm:
    values: dict[str, object] = {
        "title": "Service Article",
        "slug": "service-article",
        "summary": "Article used to test the authorship transaction boundary.",
        "content_markdown": "# Service Article",
        "section": "blog",
        "category_id": None,
        "tags": "Python, FastAPI",
    }
    values.update(overrides)
    return ArticleForm.model_validate(values)


def track_transactions(db: Session) -> Counter[str]:
    transactions: Counter[str] = Counter()

    def record_commit(_session: Session) -> None:
        transactions["commit"] += 1

    def record_rollback(_session: Session) -> None:
        transactions["rollback"] += 1

    event.listen(db, "after_commit", record_commit)
    event.listen(db, "after_rollback", record_rollback)
    return transactions


def fail_if_called(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("repository write should not be called")


def test_create_article_is_draft_and_commits_exactly_once() -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)

        article = article_service.create_article(
            db,
            make_article_form(tags="Python, python, FastAPI, fastapi"),
        )

        assert article.id is not None
        assert article.status == "draft"
        assert article.published_at is None
        assert article.section == "blog"
        assert article.category is None
        assert {tag.slug for tag in article.tags} == {"python", "fastapi"}
        assert transactions["commit"] == 1
        assert transactions["rollback"] == 0


def test_create_article_accepts_an_existing_optional_category() -> None:
    with SessionLocal() as db:
        category = article_service.create_category(
            db,
            CategoryForm(name="Engineering"),
        )
        transactions = track_transactions(db)

        article = article_service.create_article(
            db,
            make_article_form(category_id=category.id),
        )

        assert article.category is category
        assert article.category_id == category.id
        assert transactions["commit"] == 1
        assert transactions["rollback"] == 0


def test_missing_category_is_a_controlled_error_before_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(article_repository, "add_article", fail_if_called)
        monkeypatch.setattr(article_repository, "add_tag", fail_if_called)

        with pytest.raises(article_service.ArticleCategoryError) as error:
            article_service.create_article(
                db,
                make_article_form(category_id=999_999),
            )

        assert str(error.value) == "category_id: categoria não encontrada."
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1


def test_update_article_preserves_editorial_state_and_commits_once() -> None:
    first_publication = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    with SessionLocal() as db:
        category = article_service.create_category(
            db,
            CategoryForm(name="Architecture"),
        )
        article = article_service.create_article(db, make_article_form())
        article.status = "published"
        article.published_at = first_publication
        db.commit()
        transactions = track_transactions(db)

        updated = article_service.update_article(
            db,
            article,
            make_article_form(
                title="Updated Service Article",
                category_id=category.id,
                tags="Python, PostgreSQL, postgresql",
            ),
        )

        assert updated.title == "Updated Service Article"
        assert updated.status == "published"
        assert updated.published_at == first_publication
        assert updated.category is category
        assert {tag.slug for tag in updated.tags} == {"python", "postgresql"}
        assert transactions["commit"] == 1
        assert transactions["rollback"] == 0


def test_never_published_draft_can_change_slug_and_section() -> None:
    with SessionLocal() as db:
        article = article_service.create_article(db, make_article_form())
        transactions = track_transactions(db)

        updated = article_service.update_article(
            db,
            article,
            make_article_form(
                slug="renamed-article",
                section="journal",
            ),
        )

        assert updated.slug == "renamed-article"
        assert updated.section == "journal"
        assert updated.status == "draft"
        assert updated.published_at is None
        assert transactions["commit"] == 1
        assert transactions["rollback"] == 0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"slug": "changed-article", "title": "Forbidden change"},
            "slug: não pode ser alterado após a primeira publicação.",
        ),
        (
            {"section": "journal", "title": "Forbidden change"},
            "section: não pode ser alterada após a primeira publicação.",
        ),
    ],
)
def test_published_history_freezes_url_before_other_mutations(
    overrides: dict[str, object],
    message: str,
) -> None:
    with SessionLocal() as db:
        article = article_service.create_article(db, make_article_form())
        article.published_at = datetime(2026, 8, 10, tzinfo=UTC)
        db.commit()
        transactions = track_transactions(db)

        with pytest.raises(article_service.ArticleUrlImmutableError) as error:
            article_service.update_article(
                db,
                article,
                make_article_form(**overrides),
            )

        assert str(error.value) == message
        assert article.title == "Service Article"
        assert article.slug == "service-article"
        assert article.section == "blog"
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0


def test_duplicate_article_url_is_detected_before_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with SessionLocal() as db:
        article_service.create_article(db, make_article_form(tags=""))
        transactions = track_transactions(db)
        monkeypatch.setattr(article_repository, "add_article", fail_if_called)
        monkeypatch.setattr(article_repository, "add_tag", fail_if_called)

        with pytest.raises(article_service.ArticleConflictError) as error:
            article_service.create_article(
                db,
                make_article_form(title="Conflicting Article", tags=""),
            )

        assert str(error.value) == (
            "slug: já está sendo usado por outro artigo nesta seção."
        )
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1


def test_update_to_existing_article_url_does_not_mutate_article() -> None:
    with SessionLocal() as db:
        article_service.create_article(
            db,
            make_article_form(slug="existing-url"),
        )
        article = article_service.create_article(
            db,
            make_article_form(slug="editable-url", title="Editable Article"),
        )
        transactions = track_transactions(db)

        with pytest.raises(article_service.ArticleConflictError):
            article_service.update_article(
                db,
                article,
                make_article_form(
                    slug="existing-url",
                    title="Should Not Change",
                ),
            )

        assert article.slug == "editable-url"
        assert article.title == "Editable Article"
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1


def test_integrity_error_rolls_back_and_becomes_controlled_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_flush = article_repository.flush

    def fail_after_flush(db: Session) -> None:
        original_flush(db)
        raise IntegrityError(
            "private statement",
            {},
            RuntimeError("private database detail"),
        )

    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(article_repository, "flush", fail_after_flush)

        with pytest.raises(article_service.ArticleConflictError) as error:
            article_service.create_article(db, make_article_form())

        assert str(error.value) == (
            "Não foi possível salvar devido a um conflito de persistência."
        )
        assert "private database detail" not in str(error.value)
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1

    with SessionLocal() as db:
        assert article_repository.get_by_section_slug(
            db, "blog", "service-article"
        ) is None
        assert article_repository.get_tag_by_slug(db, "python") is None


def test_unexpected_update_error_rolls_back_and_is_reraised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = RuntimeError("unexpected persistence failure")
    original_flush = article_repository.flush

    def fail_after_flush(db: Session) -> None:
        original_flush(db)
        raise failure

    with SessionLocal() as db:
        article = article_service.create_article(db, make_article_form())
        article_id = article.id
        transactions = track_transactions(db)
        monkeypatch.setattr(article_repository, "flush", fail_after_flush)

        with pytest.raises(RuntimeError) as error:
            article_service.update_article(
                db,
                article,
                make_article_form(
                    title="Change that must be rolled back",
                    tags="PostgreSQL",
                ),
            )

        assert error.value is failure
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1
        assert article.title == "Service Article"
        assert {tag.slug for tag in article.tags} == {"python", "fastapi"}

    with SessionLocal() as db:
        persisted = article_repository.get_by_id(db, article_id)
        assert persisted is not None
        assert persisted.title == "Service Article"
        assert {tag.slug for tag in persisted.tags} == {"python", "fastapi"}


def test_create_category_normalizes_slug_and_commits_once() -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)

        category = article_service.create_category(
            db,
            CategoryForm(name="Ciência de Dados"),
        )

        assert category.name == "Ciência de Dados"
        assert category.slug == "ciencia-de-dados"
        assert transactions["commit"] == 1
        assert transactions["rollback"] == 0


def test_category_slug_conflict_is_controlled() -> None:
    with SessionLocal() as db:
        article_service.create_category(db, CategoryForm(name="Café"))
        transactions = track_transactions(db)

        with pytest.raises(article_service.CategoryConflictError) as error:
            article_service.create_category(db, CategoryForm(name="Cafe"))

        assert str(error.value) == (
            "slug: já está sendo usado por outra categoria."
        )
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1


def test_invalid_or_colliding_tag_names_fail_before_persistence() -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)

        with pytest.raises(article_service.ArticleTagError):
            article_service.create_article(
                db,
                make_article_form(tags="C++, C#"),
            )

        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0
        assert db.get_transaction() is None


def test_overlong_tag_name_fails_before_repository_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(
            article_repository,
            "get_by_section_slug",
            fail_if_called,
        )
        monkeypatch.setattr(article_repository, "add_tag", fail_if_called)
        monkeypatch.setattr(article_repository, "add_article", fail_if_called)
        monkeypatch.setattr(article_repository, "flush", fail_if_called)

        with pytest.raises(article_service.ArticleTagError) as error:
            article_service.create_article(
                db,
                make_article_form(tags="a" * 81),
            )

        assert "nome deve ter no máximo 80 caracteres" in str(error.value)
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0
        assert db.get_transaction() is None


def test_expanding_unicode_tag_slug_fails_before_repository_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert len(EXPANDING_UNICODE_NAME) <= 80
    assert len(article_service.slugify(EXPANDING_UNICODE_NAME)) > 80

    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(
            article_repository,
            "get_by_section_slug",
            fail_if_called,
        )
        monkeypatch.setattr(article_repository, "add_tag", fail_if_called)
        monkeypatch.setattr(article_repository, "add_article", fail_if_called)
        monkeypatch.setattr(article_repository, "flush", fail_if_called)

        with pytest.raises(article_service.ArticleTagError) as error:
            article_service.create_article(
                db,
                make_article_form(tags=EXPANDING_UNICODE_NAME),
            )

        assert "slug normalizado deve ter no máximo 80 caracteres" in str(
            error.value
        )
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0
        assert db.get_transaction() is None


def test_existing_tag_slug_collision_is_controlled() -> None:
    with SessionLocal() as db:
        article_service.create_article(
            db,
            make_article_form(slug="cpp", tags="C++"),
        )
        transactions = track_transactions(db)

        with pytest.raises(article_service.ArticleTagError) as error:
            article_service.create_article(
                db,
                make_article_form(slug="c-sharp", tags="C#"),
            )

        assert "tag existente" in str(error.value)
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1

    with SessionLocal() as db:
        assert article_repository.get_by_section_slug(
            db, "blog", "c-sharp"
        ) is None
        tag = article_repository.get_tag_by_slug(db, "c")
        assert tag is not None
        assert tag.name == "C++"


def test_failure_during_tag_synchronization_rolls_back_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = RuntimeError("tag synchronization failed")
    original_add_tag = article_repository.add_tag

    def fail_on_second_tag(db: Session, tag: Tag) -> None:
        if tag.slug == "second":
            raise failure
        original_add_tag(db, tag)

    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(article_repository, "add_tag", fail_on_second_tag)

        with pytest.raises(RuntimeError) as error:
            article_service.create_article(
                db,
                make_article_form(tags="First, Second"),
            )

        assert error.value is failure
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1

    with SessionLocal() as db:
        assert article_repository.get_by_section_slug(
            db, "blog", "service-article"
        ) is None
        assert article_repository.get_tag_by_slug(db, "first") is None
        assert article_repository.get_tag_by_slug(db, "second") is None


def test_category_integrity_error_rolls_back_as_controlled_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_flush(_db: Session) -> None:
        raise IntegrityError(
            "private statement",
            {},
            RuntimeError("private database detail"),
        )

    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(article_repository, "flush", fail_flush)

        with pytest.raises(article_service.CategoryConflictError) as error:
            article_service.create_category(db, CategoryForm(name="Conflict"))

        assert str(error.value) == (
            "Não foi possível salvar devido a um conflito de persistência."
        )
        assert "private database detail" not in str(error.value)
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1


def test_empty_category_slug_fails_before_repository_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(
            article_repository,
            "get_category_by_slug",
            fail_if_called,
        )

        with pytest.raises(article_service.CategoryError):
            article_service.create_category(db, CategoryForm(name="+++"))

        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0
        assert db.get_transaction() is None


def test_expanding_unicode_category_slug_fails_before_repository_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert len(EXPANDING_UNICODE_NAME) <= 80
    assert len(article_service.slugify(EXPANDING_UNICODE_NAME)) > 80

    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(
            article_repository,
            "get_category_by_slug",
            fail_if_called,
        )
        monkeypatch.setattr(article_repository, "add_category", fail_if_called)
        monkeypatch.setattr(article_repository, "flush", fail_if_called)

        with pytest.raises(article_service.CategoryError) as error:
            article_service.create_category(
                db,
                CategoryForm(name=EXPANDING_UNICODE_NAME),
            )

        assert "slug normalizado deve ter no máximo 80 caracteres" in str(
            error.value
        )
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0
        assert db.get_transaction() is None
