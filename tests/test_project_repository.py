from app.core.database import SessionLocal
from app.models import Project, Technology
from app.repositories import projects as project_repository
from app.schemas.project import ProjectForm
from app.services import projects as project_service


def make_project(slug: str = "repository-project") -> Project:
    return Project(
        title="Repository Project",
        slug=slug,
        summary="Projeto usado para testar a fronteira de persistência.",
        visibility="draft",
    )


def make_project_form(technologies: str) -> ProjectForm:
    return ProjectForm(
        title="Service Project",
        slug="service-project",
        summary="Projeto usado para testar a sincronização de tecnologias.",
        status="building",
        visibility="draft",
        technologies=technologies,
    )


def test_get_technology_by_slug_finds_existing_technology() -> None:
    with SessionLocal() as db:
        technology = Technology(name="Python", slug="python")
        project_repository.add_technology(db, technology)
        db.commit()

        found = project_repository.get_technology_by_slug(db, "python")

    assert found is not None
    assert found.id == technology.id
    assert found.name == "Python"


def test_get_technology_by_slug_returns_none_when_missing() -> None:
    with SessionLocal() as db:
        assert project_repository.get_technology_by_slug(db, "missing") is None


def test_repository_adds_and_flushes_without_ending_transaction() -> None:
    with SessionLocal() as db:
        transaction = db.begin()
        technology = Technology(name="PostgreSQL", slug="postgresql")
        project = make_project()
        project.technologies = [technology]

        project_repository.add_technology(db, technology)
        project_repository.add_project(db, project)

        assert db.get_transaction() is transaction
        assert transaction.is_active
        assert technology in db.new
        assert project in db.new
        assert technology.id is None
        assert project.id is None

        project_repository.flush(db)

        assert db.get_transaction() is transaction
        assert transaction.is_active
        assert technology.id is not None
        assert project.id is not None
        assert {item.slug for item in project.technologies} == {"postgresql"}

        transaction.rollback()

    with SessionLocal() as db:
        assert project_repository.get_by_slug(db, "repository-project") is None
        assert (
            project_repository.get_technology_by_slug(db, "postgresql") is None
        )


def test_caller_can_commit_project_and_technology_from_same_session() -> None:
    with SessionLocal() as db:
        technology = Technology(name="FastAPI", slug="fastapi")
        project = make_project(slug="committed-project")
        project.technologies = [technology]
        project_repository.add_technology(db, technology)
        project_repository.add_project(db, project)
        db.commit()
        project_id = project.id

    with SessionLocal() as db:
        persisted = project_repository.get_by_id(db, project_id)

    assert persisted is not None
    assert persisted.slug == "committed-project"
    assert {item.slug for item in persisted.technologies} == {"fastapi"}


def test_service_preserves_case_insensitive_technology_synchronization() -> None:
    with SessionLocal() as db:
        project = project_service.create_project(
            db,
            make_project_form("Python, python, FastAPI, fastapi"),
        )
        assert {item.slug for item in project.technologies} == {
            "python",
            "fastapi",
        }

        updated = project_service.update_project(
            db,
            project,
            make_project_form("PYTHON, PostgreSQL, postgresql"),
        )

        assert {item.slug for item in updated.technologies} == {
            "python",
            "postgresql",
        }
        python_technology = project_repository.get_technology_by_slug(db, "python")
        assert python_technology is not None
        assert python_technology.name == "Python"
