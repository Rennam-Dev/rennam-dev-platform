import re
import unicodedata

from sqlalchemy.orm import Session

from app.models import Project, Technology
from app.repositories import projects as project_repository
from app.schemas.project import ProjectForm


class ProjectSlugImmutableError(ValueError):
    pass


class ProjectDeletionDisabledError(RuntimeError):
    pass


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
        technology = project_repository.get_technology_by_slug(db, technology_slug)
        if technology is None:
            technology = Technology(name=name, slug=technology_slug)
            project_repository.add_technology(db, technology)
        technologies.append(technology)
    project.technologies = technologies


def create_project(db: Session, form: ProjectForm) -> Project:
    project = Project(**form.as_model_data())
    sync_technologies(db, project, form.technologies)
    project_repository.add_project(db, project)
    db.commit()
    project_repository.refresh_project(db, project)
    return project


def update_project(db: Session, project: Project, form: ProjectForm) -> Project:
    if form.slug != project.slug:
        raise ProjectSlugImmutableError(
            "slug: não pode ser alterado após a criação."
        )

    model_data = form.as_model_data()
    model_data.pop("slug")
    for field, value in model_data.items():
        setattr(project, field, value)
    sync_technologies(db, project, form.technologies)
    db.commit()
    project_repository.refresh_project(db, project)
    return project


def delete_project(db: Session, project: Project) -> None:
    raise ProjectDeletionDisabledError(
        "Exclusão definitiva está desabilitada na v0.2.1. "
        "Arquivamento e restauração serão implementados futuramente."
    )
