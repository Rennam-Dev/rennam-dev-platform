import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, Technology
from app.schemas.project import ProjectForm


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def parse_technologies(raw: str) -> list[str]:
    unique: dict[str, str] = {}
    for item in raw.split(","):
        name = item.strip()
        if name:
            unique.setdefault(name.casefold(), name)
    return list(unique.values())


def sync_technologies(
    db: Session, project: Project, raw_technologies: str
) -> None:
    technologies: list[Technology] = []
    for name in parse_technologies(raw_technologies):
        technology_slug = slugify(name)
        technology = db.scalar(
            select(Technology).where(Technology.slug == technology_slug)
        )
        if technology is None:
            technology = Technology(name=name, slug=technology_slug)
            db.add(technology)
        technologies.append(technology)
    project.technologies = technologies


def create_project(db: Session, form: ProjectForm) -> Project:
    project = Project(**form.as_model_data())
    sync_technologies(db, project, form.technologies)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, form: ProjectForm) -> Project:
    for field, value in form.as_model_data().items():
        setattr(project, field, value)
    sync_technologies(db, project, form.technologies)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    db.delete(project)
    db.commit()
