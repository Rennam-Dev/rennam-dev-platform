import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

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


class ArticleImportError(ValueError):
    pass


class ArticleImportConflictError(ArticleImportError):
    pass


@dataclass(frozen=True)
class PublishedArticleImport:
    title: str
    slug: str
    summary: str
    content_markdown: str
    section: str
    category_name: str
    category_slug: str
    tags: tuple[str, ...]
    published_at: datetime


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


def prepare_tag_names(names: Iterable[str]) -> list[tuple[str, str]]:
    prepared: list[tuple[str, str]] = []
    names_by_slug: dict[str, str] = {}
    unique_names: dict[str, str] = {}
    for raw_name in names:
        name = raw_name.strip()
        if name:
            unique_names.setdefault(name.casefold(), name)
    for name in unique_names.values():
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


def prepare_tags(raw: str) -> list[tuple[str, str]]:
    return prepare_tag_names(parse_tags(raw))


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


def _normalize_aware_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ArticleImportError(f"{field}: informe um timestamp com timezone.")
    return value.astimezone(UTC)


def _validate_import_payload(data: PublishedArticleImport) -> None:
    text_limits = (
        ("title", data.title, 180),
        ("slug", data.slug, 120),
        ("summary", data.summary, 320),
        ("content_markdown", data.content_markdown, 200_000),
        ("category_name", data.category_name, 80),
        ("category_slug", data.category_slug, 80),
    )
    for field, value, limit in text_limits:
        if not value or not value.strip():
            raise ArticleImportError(f"{field}: campo obrigatório na importação.")
        if len(value) > limit:
            raise ArticleImportError(
                f"{field}: deve ter no máximo {limit} caracteres."
            )
    if data.section not in {"blog", "journal"}:
        raise ArticleImportError("section: seção inválida na importação.")
    slug_pattern = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    if re.fullmatch(slug_pattern, data.slug) is None:
        raise ArticleImportError("slug: formato inválido na importação.")
    if re.fullmatch(slug_pattern, data.category_slug) is None:
        raise ArticleImportError("category_slug: formato inválido na importação.")
    if slugify(data.category_name) != data.category_slug:
        raise ArticleImportError(
            "category_slug: não corresponde ao nome determinístico da categoria."
        )


def _published_at_matches(
    actual: datetime | None,
    expected: datetime,
) -> bool:
    if actual is None or actual.tzinfo is None or actual.utcoffset() is None:
        return False
    return actual.astimezone(UTC) == expected


def _matches_published_import(
    article: Article,
    data: PublishedArticleImport,
    published_at: datetime,
    tag_data: list[tuple[str, str]],
) -> bool:
    category_matches = (
        article.category is not None
        and article.category.slug == data.category_slug
        and article.category.name.casefold() == data.category_name.casefold()
    )
    actual_tag_slugs = {tag.slug.casefold() for tag in article.tags}
    expected_tag_slugs = {tag_slug.casefold() for _name, tag_slug in tag_data}
    return (
        article.title == data.title
        and article.summary == data.summary
        and article.content_markdown == data.content_markdown
        and article.section == data.section
        and article.status == "published"
        and category_matches
        and actual_tag_slugs == expected_tag_slugs
        and _published_at_matches(article.published_at, published_at)
    )


def import_published_article(
    db: Session,
    data: PublishedArticleImport,
    *,
    now: datetime | None = None,
) -> Literal["created", "unchanged"]:
    """Import one published Article and its taxonomy in a single transaction."""
    _validate_import_payload(data)
    published_at = _normalize_aware_utc(data.published_at, "published_at")
    current_time = _normalize_aware_utc(now or datetime.now(UTC), "now")
    if published_at > current_time:
        raise ArticleImportError(
            "published_at: data futura não é permitida na importação."
        )
    try:
        tag_data = prepare_tag_names(data.tags)
    except ArticleTagError as error:
        raise ArticleImportError(str(error)) from None
    existing = article_repository.get_by_section_slug(db, data.section, data.slug)
    if existing is not None:
        if _matches_published_import(existing, data, published_at, tag_data):
            return "unchanged"
        if db.in_transaction():
            db.rollback()
        raise ArticleImportConflictError(
            "o Article existente diverge do conteúdo legado; corrija-o manualmente."
        )

    try:
        category = article_repository.get_category_by_slug(db, data.category_slug)
        if category is None:
            category = Category(name=data.category_name, slug=data.category_slug)
            article_repository.add_category(db, category)
        elif category.name.casefold() != data.category_name.casefold():
            raise ArticleImportConflictError(
                "a Category existente diverge da categoria legada esperada."
            )

        tags, new_tags = _resolve_tags(db, tag_data)
        _add_new_tags(db, new_tags)
        article = Article(
            title=data.title,
            slug=data.slug,
            summary=data.summary,
            content_markdown=data.content_markdown,
            section=data.section,
            status="published",
            published_at=published_at,
            category=category,
            tags=tags,
        )
        article_repository.add_article(db, article)
        article_repository.flush(db)
        db.commit()
        return "created"
    except ArticleImportError:
        if db.in_transaction():
            db.rollback()
        raise
    except ArticleTagError as error:
        db.rollback()
        raise ArticleImportConflictError(str(error)) from None
    except IntegrityError:
        db.rollback()
        raise ArticleImportConflictError(
            "conflito de persistência durante a importação do Article."
        ) from None
    except Exception:
        db.rollback()
        raise


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
