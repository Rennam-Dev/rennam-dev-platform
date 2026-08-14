import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Article, Category, Tag
from app.repositories import articles as article_repository
from app.schemas.article import ArticleForm, CategoryForm


class ArticleConflictError(ValueError):
    pass


class ArticleUrlImmutableError(ValueError):
    pass


class ArticleCategoryError(ValueError):
    pass


class ArticleTagError(ValueError):
    pass


class ArticlePublicationError(ValueError):
    pass


class CategoryConflictError(ValueError):
    pass


class CategoryError(ValueError):
    pass


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def parse_tags(raw: str) -> list[str]:
    unique: dict[str, str] = {}
    for item in raw.split(","):
        name = item.strip()
        if name:
            unique.setdefault(name.casefold(), name)
    return list(unique.values())


def prepare_tags(raw: str) -> list[tuple[str, str]]:
    prepared: list[tuple[str, str]] = []
    names_by_slug: dict[str, str] = {}
    for name in parse_tags(raw):
        if len(name) > 80:
            raise ArticleTagError(
                "tags: cada nome deve ter no máximo 80 caracteres."
            )
        tag_slug = slugify(name)
        if not tag_slug:
            raise ArticleTagError(
                "tags: nome inválido; informe ao menos uma letra ou número."
            )
        if len(tag_slug) > 80:
            raise ArticleTagError(
                "tags: slug normalizado deve ter no máximo 80 caracteres."
            )
        if tag_slug in names_by_slug:
            raise ArticleTagError(
                "tags: nomes diferentes não podem gerar o mesmo slug."
            )
        names_by_slug[tag_slug] = name
        prepared.append((name, tag_slug))
    return prepared


def _get_category(db: Session, category_id: int | None) -> Category | None:
    if category_id is None:
        return None
    category = article_repository.get_category_by_id(db, category_id)
    if category is None:
        raise ArticleCategoryError("category_id: categoria não encontrada.")
    return category


def _resolve_tags(
    db: Session,
    tags_data: list[tuple[str, str]],
) -> tuple[list[Tag], list[Tag]]:
    tags: list[Tag] = []
    new_tags: list[Tag] = []
    for name, tag_slug in tags_data:
        tag = article_repository.get_tag_by_slug(db, tag_slug)
        if tag is not None and tag.name.casefold() != name.casefold():
            raise ArticleTagError(
                "tags: nome conflita com uma tag existente de mesmo slug."
            )
        if tag is None:
            tag = Tag(name=name, slug=tag_slug)
            new_tags.append(tag)
        tags.append(tag)
    return tags, new_tags


def _add_new_tags(db: Session, new_tags: list[Tag]) -> None:
    for tag in new_tags:
        article_repository.add_tag(db, tag)


def _ensure_available_url(
    db: Session,
    section: str,
    slug: str,
    *,
    current_article_id: int | None = None,
) -> None:
    existing = article_repository.get_by_section_slug(db, section, slug)
    if existing is not None and existing.id != current_article_id:
        raise ArticleConflictError(
            "slug: já está sendo usado por outro artigo nesta seção."
        )


def _validate_url_stability(article: Article, form: ArticleForm) -> None:
    if article.published_at is None:
        return
    if form.slug != article.slug:
        raise ArticleUrlImmutableError(
            "slug: não pode ser alterado após a primeira publicação."
        )
    if form.section != article.section:
        raise ArticleUrlImmutableError(
            "section: não pode ser alterada após a primeira publicação."
        )


def _validate_publication_preconditions(article: Article) -> None:
    if article.category_id is None or article.category is None:
        raise ArticlePublicationError(
            "category_id: selecione uma categoria antes de publicar."
        )
    required_fields = (
        ("title", article.title),
        ("summary", article.summary),
        ("content_markdown", article.content_markdown),
    )
    for field, value in required_fields:
        if not value or not value.strip():
            raise ArticlePublicationError(
                f"{field}: campo obrigatório para publicação."
            )


def publish_article(db: Session, article: Article) -> Article:
    """Publish idempotently while preserving the first publication instant."""
    try:
        _validate_publication_preconditions(article)
        if article.published_at is None:
            article.published_at = datetime.now(UTC)
        article.status = "published"
        article_repository.flush(db)
        db.commit()
        return article
    except ArticlePublicationError:
        if db.in_transaction():
            db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise ArticlePublicationError(
            "Não foi possível publicar devido a um conflito de persistência."
        ) from None
    except Exception:
        db.rollback()
        raise


def unpublish_article(db: Session, article: Article) -> Article:
    """Unpublish idempotently without clearing publication history."""
    try:
        article.status = "draft"
        article_repository.flush(db)
        db.commit()
        return article
    except IntegrityError:
        db.rollback()
        raise ArticlePublicationError(
            "Não foi possível retirar a publicação devido a um conflito "
            "de persistência."
        ) from None
    except Exception:
        db.rollback()
        raise


def create_article(db: Session, form: ArticleForm) -> Article:
    tags_data = prepare_tags(form.tags)
    try:
        category = _get_category(db, form.category_id)
        _ensure_available_url(db, form.section, form.slug)
        tags, new_tags = _resolve_tags(db, tags_data)

        model_data = form.as_model_data()
        model_data.pop("category_id")
        article = Article(
            **model_data,
            status="draft",
            published_at=None,
            category=category,
        )
        _add_new_tags(db, new_tags)
        article.tags = tags
        article_repository.add_article(db, article)
        article_repository.flush(db)
        db.commit()
        return article
    except IntegrityError:
        db.rollback()
        raise ArticleConflictError(
            "Não foi possível salvar devido a um conflito de persistência."
        ) from None
    except Exception:
        db.rollback()
        raise


def update_article(db: Session, article: Article, form: ArticleForm) -> Article:
    _validate_url_stability(article, form)
    tags_data = prepare_tags(form.tags)
    try:
        category = _get_category(db, form.category_id)
        if article.status == "published" and category is None:
            raise ArticlePublicationError(
                "category_id: um artigo publicado deve manter uma categoria."
            )
        _ensure_available_url(
            db,
            form.section,
            form.slug,
            current_article_id=article.id,
        )
        tags, new_tags = _resolve_tags(db, tags_data)

        model_data = form.as_model_data()
        model_data.pop("category_id")
        _add_new_tags(db, new_tags)
        for field, value in model_data.items():
            setattr(article, field, value)
        article.category = category
        article.tags = tags
        article.updated_at = datetime.now(UTC)
        article_repository.flush(db)
        db.commit()
        return article
    except IntegrityError:
        db.rollback()
        raise ArticleConflictError(
            "Não foi possível salvar devido a um conflito de persistência."
        ) from None
    except Exception:
        db.rollback()
        raise


def create_category(db: Session, form: CategoryForm) -> Category:
    category_slug = slugify(form.name)
    if not category_slug:
        raise CategoryError(
            "name: nome inválido; informe ao menos uma letra ou número."
        )
    if len(category_slug) > 80:
        raise CategoryError(
            "slug: slug normalizado deve ter no máximo 80 caracteres."
        )
    try:
        if article_repository.get_category_by_slug(db, category_slug) is not None:
            raise CategoryConflictError(
                "slug: já está sendo usado por outra categoria."
            )
        category = Category(name=form.name, slug=category_slug)
        article_repository.add_category(db, category)
        article_repository.flush(db)
        db.commit()
        return category
    except IntegrityError:
        db.rollback()
        raise CategoryConflictError(
            "Não foi possível salvar devido a um conflito de persistência."
        ) from None
    except Exception:
        db.rollback()
        raise
