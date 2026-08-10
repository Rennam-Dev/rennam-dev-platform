import re
import unicodedata

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Project, Technology
from app.repositories import projects as project_repository
from app.schemas.project import ProjectForm


class ProjectSlugImmutableError(ValueError):
    pass


class ProjectConflictError(ValueError):
    pass


class ProjectTechnologyError(ValueError):
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


def prepare_technologies(raw: str) -> list[tuple[str, str]]:
    prepared: list[tuple[str, str]] = []
    names_by_slug: dict[str, str] = {}
    for name in parse_technologies(raw):
        technology_slug = slugify(name)
        if not technology_slug:
            raise ProjectTechnologyError(
                "technologies: nome inválido; informe ao menos uma letra ou número."
            )
        if technology_slug in names_by_slug:
            raise ProjectTechnologyError(
                "technologies: nomes diferentes não podem gerar o mesmo slug."
            )
        names_by_slug[technology_slug] = name
        prepared.append((name, technology_slug))
    return prepared


def sync_technologies(
    db: Session,
    project: Project,
    technologies_data: list[tuple[str, str]],
) -> None:
    technologies: list[Technology] = []
    for name, technology_slug in technologies_data:
        technology = project_repository.get_technology_by_slug(db, technology_slug)
        if technology is None:
            technology = Technology(name=name, slug=technology_slug)
            project_repository.add_technology(db, technology)
        technologies.append(technology)
    project.technologies = technologies


def create_project(db: Session, form: ProjectForm) -> Project:
    technologies_data = prepare_technologies(form.technologies)
    try:
        if project_repository.get_by_slug(db, form.slug) is not None:
            raise ProjectConflictError(
                "slug: já está sendo usado por outro projeto."
            )
        project = Project(**form.as_model_data())
        sync_technologies(db, project, technologies_data)
        project_repository.add_project(db, project)
        project_repository.flush(db)
        db.commit()
        return project
    except IntegrityError:
        db.rollback()
        raise ProjectConflictError(
            "Não foi possível salvar devido a um conflito de persistência."
        ) from None
    except Exception:
        db.rollback()
        raise


def update_project(db: Session, project: Project, form: ProjectForm) -> Project:
    if form.slug != project.slug:
        raise ProjectSlugImmutableError(
            "slug: não pode ser alterado após a criação."
        )

    technologies_data = prepare_technologies(form.technologies)
    try:
        model_data = form.as_model_data()
        model_data.pop("slug")
        for field, value in model_data.items():
            setattr(project, field, value)
        sync_technologies(db, project, technologies_data)
        project_repository.flush(db)
        db.commit()
        return project
    except IntegrityError:
        db.rollback()
        raise ProjectConflictError(
            "Não foi possível salvar devido a um conflito de persistência."
        ) from None
    except Exception:
        db.rollback()
        raise


def delete_project(db: Session, project: Project) -> None:
    raise ProjectDeletionDisabledError(
        "Exclusão definitiva está desabilitada na v0.2.1. "
        "Arquivamento e restauração serão implementados futuramente."
    )
