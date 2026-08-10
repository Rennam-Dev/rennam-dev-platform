from collections import Counter

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.repositories import projects as project_repository
from app.schemas.project import ProjectForm
from app.services import projects as project_service


def make_project_form(**overrides: object) -> ProjectForm:
    values: dict[str, object] = {
        "title": "Service Project",
        "slug": "service-project",
        "summary": "Projeto usado para testar a fronteira transacional.",
        "status": "building",
        "visibility": "draft",
        "technologies": "Python, FastAPI",
    }
    values.update(overrides)
    return ProjectForm.model_validate(values)


def track_transactions(db: Session) -> Counter[str]:
    transactions: Counter[str] = Counter()

    def record_commit(_session: Session) -> None:
        transactions["commit"] += 1

    def record_rollback(_session: Session) -> None:
        transactions["rollback"] += 1

    event.listen(db, "after_commit", record_commit)
    event.listen(db, "after_rollback", record_rollback)
    return transactions


def fail_if_called(*_args, **_kwargs) -> None:
    raise AssertionError("repository write should not be called")


def test_create_project_commits_exactly_once() -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)

        project = project_service.create_project(db, make_project_form())

        assert project.id is not None
        assert transactions["commit"] == 1
        assert transactions["rollback"] == 0


def test_update_project_commits_exactly_once() -> None:
    with SessionLocal() as db:
        project = project_service.create_project(db, make_project_form())
        transactions = track_transactions(db)

        updated = project_service.update_project(
            db,
            project,
            make_project_form(
                title="Service Project atualizado",
                technologies="Python, PostgreSQL",
            ),
        )

        assert updated.title == "Service Project atualizado"
        assert {technology.slug for technology in updated.technologies} == {
            "python",
            "postgresql",
        }
        assert transactions["commit"] == 1
        assert transactions["rollback"] == 0


def test_duplicate_slug_raises_domain_conflict_before_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with SessionLocal() as db:
        project_service.create_project(db, make_project_form())
        transactions = track_transactions(db)
        monkeypatch.setattr(project_repository, "add_project", fail_if_called)
        monkeypatch.setattr(project_repository, "add_technology", fail_if_called)

        with pytest.raises(project_service.ProjectConflictError) as error:
            project_service.create_project(
                db,
                make_project_form(title="Outro projeto"),
            )

        assert str(error.value) == "slug: já está sendo usado por outro projeto."
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1


@pytest.mark.parametrize(
    ("technologies", "message"),
    [
        ("+++", "nome inválido"),
        ("C++, C#", "nomes diferentes não podem gerar o mesmo slug"),
    ],
)
def test_invalid_technology_fails_before_repository_access(
    monkeypatch: pytest.MonkeyPatch,
    technologies: str,
    message: str,
) -> None:
    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(project_repository, "get_by_slug", fail_if_called)
        monkeypatch.setattr(project_repository, "add_project", fail_if_called)
        monkeypatch.setattr(project_repository, "add_technology", fail_if_called)

        with pytest.raises(project_service.ProjectTechnologyError) as error:
            project_service.create_project(
                db,
                make_project_form(technologies=technologies),
            )

        assert message in str(error.value)
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0
        assert db.get_transaction() is None


def test_integrity_error_rolls_back_and_becomes_domain_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_flush = project_repository.flush

    def fail_after_flush(db: Session) -> None:
        original_flush(db)
        raise IntegrityError(
            "internal statement",
            {},
            RuntimeError("private database detail"),
        )

    with SessionLocal() as db:
        transactions = track_transactions(db)
        monkeypatch.setattr(project_repository, "flush", fail_after_flush)

        with pytest.raises(project_service.ProjectConflictError) as error:
            project_service.create_project(db, make_project_form())

        assert str(error.value) == (
            "Não foi possível salvar devido a um conflito de persistência."
        )
        assert "private database detail" not in str(error.value)
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1

    with SessionLocal() as db:
        assert project_repository.get_by_slug(db, "service-project") is None
        assert project_repository.get_technology_by_slug(db, "python") is None


def test_unexpected_update_error_rolls_back_and_is_reraised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = RuntimeError("unexpected persistence failure")
    original_flush = project_repository.flush

    def fail_after_flush(db: Session) -> None:
        original_flush(db)
        raise failure

    with SessionLocal() as db:
        project = project_service.create_project(db, make_project_form())
        project_id = project.id
        transactions = track_transactions(db)
        monkeypatch.setattr(project_repository, "flush", fail_after_flush)

        with pytest.raises(RuntimeError) as error:
            project_service.update_project(
                db,
                project,
                make_project_form(
                    title="Alteração que deve ser revertida",
                    technologies="PostgreSQL",
                ),
            )

        assert error.value is failure
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 1
        assert project.title == "Service Project"
        assert {technology.slug for technology in project.technologies} == {
            "python",
            "fastapi",
        }

    with SessionLocal() as db:
        persisted = project_repository.get_by_id(db, project_id)
        assert persisted is not None
        assert persisted.title == "Service Project"
        assert {technology.slug for technology in persisted.technologies} == {
            "python",
            "fastapi",
        }


def test_invalid_update_does_not_mutate_project() -> None:
    with SessionLocal() as db:
        project = project_service.create_project(db, make_project_form())
        transactions = track_transactions(db)

        with pytest.raises(project_service.ProjectTechnologyError):
            project_service.update_project(
                db,
                project,
                make_project_form(
                    title="Alteração inválida",
                    technologies="+++",
                ),
            )

        assert project.title == "Service Project"
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0


def test_immutable_slug_fails_before_mutating_other_fields() -> None:
    with SessionLocal() as db:
        project = project_service.create_project(db, make_project_form())
        transactions = track_transactions(db)

        with pytest.raises(project_service.ProjectSlugImmutableError):
            project_service.update_project(
                db,
                project,
                make_project_form(
                    slug="changed-service-project",
                    title="Alteração que não pode ocorrer",
                ),
            )

        assert project.slug == "service-project"
        assert project.title == "Service Project"
        assert transactions["commit"] == 0
        assert transactions["rollback"] == 0
