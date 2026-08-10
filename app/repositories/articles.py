from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Article, Category, Tag


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
