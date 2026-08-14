from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload, selectinload

from app.models import Article, Category, Tag


def list_all(db: Session) -> list[Article]:
    statement = (
        select(Article)
        .options(
            selectinload(Article.category),
            selectinload(Article.tags),
        )
        .order_by(Article.updated_at.desc(), Article.id.desc())
    )
    return list(db.scalars(statement))


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name, Category.id)))


def get_by_id(db: Session, article_id: int) -> Article | None:
    statement = (
        select(Article)
        .where(Article.id == article_id)
        .options(
            selectinload(Article.category),
            selectinload(Article.tags),
        )
    )
    return db.scalar(statement)


def get_by_section_slug(db: Session, section: str, slug: str) -> Article | None:
    statement = (
        select(Article)
        .where(Article.section == section, Article.slug == slug)
        .options(
            selectinload(Article.category),
            selectinload(Article.tags),
        )
    )
    return db.scalar(statement)


def list_published_by_section(db: Session, section: str) -> list[Article]:
    statement = (
        select(Article)
        .where(
            Article.section == section,
            Article.status == "published",
        )
        .options(
            selectinload(Article.category),
            selectinload(Article.tags),
        )
        .order_by(Article.published_at.desc(), Article.id.desc())
    )
    return list(db.scalars(statement))


def list_recent_published_blog(db: Session, limit: int) -> list[Article]:
    statement = (
        select(Article)
        .where(
            Article.section == "blog",
            Article.status == "published",
        )
        .options(
            load_only(
                Article.id,
                Article.slug,
                Article.title,
                Article.published_at,
            ),
            raiseload(Article.category),
            raiseload(Article.tags),
        )
        .order_by(Article.published_at.desc(), Article.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def list_published_section_slugs(db: Session) -> list[tuple[str, str]]:
    statement = (
        select(Article.section, Article.slug)
        .where(Article.status == "published")
        .order_by(Article.section, Article.slug)
    )
    return [(section, slug) for section, slug in db.execute(statement)]


def get_published_by_slug(
    db: Session,
    section: str,
    slug: str,
) -> Article | None:
    statement = (
        select(Article)
        .where(
            Article.section == section,
            Article.status == "published",
            Article.slug == slug,
        )
        .options(
            selectinload(Article.category),
            selectinload(Article.tags),
        )
    )
    return db.scalar(statement)


def get_category_by_id(db: Session, category_id: int) -> Category | None:
    return db.get(Category, category_id)


def get_category_by_slug(db: Session, slug: str) -> Category | None:
    return db.scalar(select(Category).where(Category.slug == slug))


def get_tag_by_slug(db: Session, slug: str) -> Tag | None:
    return db.scalar(select(Tag).where(Tag.slug == slug))


def add_category(db: Session, category: Category) -> None:
    db.add(category)


def add_tag(db: Session, tag: Tag) -> None:
    db.add(tag)


def add_article(db: Session, article: Article) -> None:
    db.add(article)


def flush(db: Session) -> None:
    db.flush()
