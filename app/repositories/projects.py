from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, Technology


def list_published(db: Session, technology: str | None = None) -> list[Project]:
    statement = (
        select(Project)
        .where(Project.visibility == "published")
        .options(selectinload(Project.technologies))
        .order_by(Project.featured.desc(), Project.updated_at.desc())
    )
    if technology:
        statement = statement.join(Project.technologies).where(
            Technology.slug == technology
        )
    return list(db.scalars(statement).unique())


def list_featured(db: Session, limit: int = 3) -> list[Project]:
    statement = (
        select(Project)
        .where(Project.visibility == "published", Project.featured.is_(True))
        .options(selectinload(Project.technologies))
        .order_by(Project.updated_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def list_all(db: Session) -> list[Project]:
    statement = (
        select(Project)
        .options(selectinload(Project.technologies))
        .order_by(Project.updated_at.desc())
    )
    return list(db.scalars(statement))


def get_by_slug(db: Session, slug: str, published_only: bool = False) -> Project | None:
    statement = (
        select(Project)
        .where(Project.slug == slug)
        .options(selectinload(Project.technologies))
    )
    if published_only:
        statement = statement.where(Project.visibility == "published")
    return db.scalar(statement)


def get_by_id(db: Session, project_id: int) -> Project | None:
    statement = (
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.technologies))
    )
    return db.scalar(statement)


def list_technologies(db: Session) -> list[Technology]:
    statement = (
        select(Technology)
        .join(Technology.projects)
        .where(Project.visibility == "published")
        .order_by(Technology.name)
        .distinct()
    )
    return list(db.scalars(statement))
