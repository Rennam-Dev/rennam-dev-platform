from types import MappingProxyType

import pytest
from pydantic import ValidationError

from app.schemas.project import PROJECT_URL_MAX_LENGTH, ProjectForm


def valid_form_mapping(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "title": "Projeto modular",
        "slug": "projeto-modular",
        "summary": "Um resumo suficientemente detalhado para validação.",
        "problem": "Problema",
        "solution": "Solução",
        "architecture": "Arquitetura",
        "decisions": "Decisões",
        "results": "Resultados",
        "learnings": "Aprendizados",
        "course": "Engenharia de dados",
        "status": "building",
        "visibility": "published",
        "technologies": "Python, FastAPI",
        "repo_url": "https://github.com/example/project",
        "demo_url": "https://example.com/project/demo",
        "cover_image_url": "https://example.com/project/cover.png",
        "seo_description": "Descrição para mecanismos de busca.",
    }
    values.update(overrides)
    return values


def url_with_length(length: int) -> str:
    prefix = "https://example.com/"
    assert length >= len(prefix)
    return prefix + ("a" * (length - len(prefix)))


@pytest.mark.no_database
def test_project_form_builds_equivalent_payload_from_mapping() -> None:
    raw = MappingProxyType(valid_form_mapping(featured="on", csrf_token="ignored"))

    form = ProjectForm.from_mapping(raw)

    assert form.featured is True
    assert form.technologies == "Python, FastAPI"
    assert form.as_model_data() == {
        "title": "Projeto modular",
        "slug": "projeto-modular",
        "summary": "Um resumo suficientemente detalhado para validação.",
        "problem": "Problema",
        "solution": "Solução",
        "architecture": "Arquitetura",
        "decisions": "Decisões",
        "results": "Resultados",
        "learnings": "Aprendizados",
        "course": "Engenharia de dados",
        "status": "building",
        "visibility": "published",
        "featured": True,
        "repo_url": "https://github.com/example/project",
        "demo_url": "https://example.com/project/demo",
        "cover_image_url": "https://example.com/project/cover.png",
        "seo_description": "Descrição para mecanismos de busca.",
    }


@pytest.mark.no_database
def test_project_form_coerces_featured_checkbox() -> None:
    assert ProjectForm.from_mapping(valid_form_mapping()).featured is False
    assert (
        ProjectForm.from_mapping(valid_form_mapping(featured="on")).featured
        is True
    )
    assert (
        ProjectForm.from_mapping(valid_form_mapping(featured="true")).featured
        is False
    )


@pytest.mark.no_database
def test_project_form_converts_empty_optional_urls_for_persistence() -> None:
    form = ProjectForm.from_mapping(
        valid_form_mapping(repo_url="", demo_url=None, cover_image_url="")
    )

    assert form.repo_url is None
    assert form.demo_url is None
    assert form.cover_image_url is None
    payload = form.as_model_data()
    assert payload["repo_url"] == ""
    assert payload["demo_url"] == ""
    assert payload["cover_image_url"] == ""


@pytest.mark.no_database
def test_project_form_strips_text_whitespace() -> None:
    form = ProjectForm.from_mapping(
        valid_form_mapping(
            title="  Projeto modular  ",
            slug="  projeto-modular  ",
            summary="  Um resumo suficientemente detalhado para validação.  ",
            technologies="  Python, FastAPI  ",
        )
    )

    assert form.title == "Projeto modular"
    assert form.slug == "projeto-modular"
    assert form.summary == "Um resumo suficientemente detalhado para validação."
    assert form.technologies == "Python, FastAPI"


@pytest.mark.no_database
@pytest.mark.parametrize("field", ["repo_url", "demo_url", "cover_image_url"])
def test_project_form_accepts_url_at_model_limit_and_rejects_above_it(
    field: str,
) -> None:
    accepted_url = url_with_length(PROJECT_URL_MAX_LENGTH)
    form = ProjectForm.from_mapping(valid_form_mapping(**{field: accepted_url}))
    assert str(getattr(form, field)) == accepted_url

    rejected_url = url_with_length(PROJECT_URL_MAX_LENGTH + 1)
    with pytest.raises(ValidationError) as error:
        ProjectForm.from_mapping(valid_form_mapping(**{field: rejected_url}))

    detail = next(item for item in error.value.errors() if item["loc"] == (field,))
    assert detail["type"] == "url_too_long"
    assert "500" in detail["msg"]


@pytest.mark.no_database
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "unknown", "Status inválido."),
        ("visibility", "private", "Visibilidade inválida."),
        ("slug", "Slug Inválido", "String should match pattern"),
    ],
)
def test_project_form_preserves_controlled_validation_errors(
    field: str,
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        ProjectForm.from_mapping(valid_form_mapping(**{field: value}))

    detail = next(item for item in error.value.errors() if item["loc"] == (field,))
    assert message in detail["msg"]
