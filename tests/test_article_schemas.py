from types import MappingProxyType

import pytest
from pydantic import ValidationError

from app.schemas.article import ArticleForm, CategoryForm

pytestmark = pytest.mark.no_database


def valid_article_mapping(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "title": "Autoria modular",
        "slug": "autoria-modular",
        "summary": "Contrato de autoria para o CMS.",
        "content_markdown": "# Conteúdo\n\nMarkdown **bruto**.",
        "section": "blog",
        "category_id": "",
        "tags": "Python, FastAPI",
    }
    values.update(overrides)
    return values


def test_article_form_builds_allowed_model_data_from_mapping() -> None:
    raw = MappingProxyType(
        valid_article_mapping(
            category_id="42",
            csrf_token="ignored",
            id="999",
            created_at="2026-08-10T00:00:00Z",
            updated_at="2026-08-10T00:00:00Z",
        )
    )

    form = ArticleForm.from_mapping(raw)

    assert form.category_id == 42
    assert form.tags == "Python, FastAPI"
    assert form.as_model_data() == {
        "title": "Autoria modular",
        "slug": "autoria-modular",
        "summary": "Contrato de autoria para o CMS.",
        "content_markdown": "# Conteúdo\n\nMarkdown **bruto**.",
        "section": "blog",
        "category_id": 42,
    }


def test_article_form_strips_authorship_whitespace() -> None:
    form = ArticleForm.from_mapping(
        valid_article_mapping(
            title="  Autoria modular  ",
            slug="  autoria-modular  ",
            summary="  Contrato de autoria para o CMS.  ",
            content_markdown="  # Conteúdo  ",
            section="  blog  ",
            tags="  Python, FastAPI  ",
        )
    )

    assert form.title == "Autoria modular"
    assert form.slug == "autoria-modular"
    assert form.summary == "Contrato de autoria para o CMS."
    assert form.content_markdown == "# Conteúdo"
    assert form.section == "blog"
    assert form.tags == "Python, FastAPI"


@pytest.mark.parametrize("section", ["blog", "journal"])
def test_article_form_accepts_approved_sections(section: str) -> None:
    assert ArticleForm.from_mapping(valid_article_mapping(section=section)).section == (
        section
    )


@pytest.mark.parametrize("section", ["", "news", "BLOG"])
def test_article_form_rejects_invalid_or_missing_section(section: str) -> None:
    with pytest.raises(ValidationError):
        ArticleForm.from_mapping(valid_article_mapping(section=section))


@pytest.mark.parametrize(
    "slug",
    [
        "Slug-Invalido",
        "slug invalido",
        "slug/invalido",
        "-slug",
        "slug-",
        "slug--invalido",
    ],
)
def test_article_form_rejects_invalid_slug(slug: str) -> None:
    with pytest.raises(ValidationError):
        ArticleForm.from_mapping(valid_article_mapping(slug=slug))


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("title", 180),
        ("slug", 120),
        ("summary", 320),
    ],
)
def test_article_form_preserves_model_length_limits(field: str, limit: int) -> None:
    accepted = "a" * limit
    form = ArticleForm.from_mapping(valid_article_mapping(**{field: accepted}))
    assert getattr(form, field) == accepted

    with pytest.raises(ValidationError):
        ArticleForm.from_mapping(
            valid_article_mapping(**{field: "a" * (limit + 1)})
        )


@pytest.mark.parametrize("category_id", ["", "   ", None])
def test_article_form_accepts_empty_optional_category(category_id: object) -> None:
    form = ArticleForm.from_mapping(
        valid_article_mapping(category_id=category_id)
    )

    assert form.category_id is None


def test_article_form_preserves_textual_tags_for_the_service() -> None:
    form = ArticleForm.from_mapping(
        valid_article_mapping(tags="Python, python, Data Engineering")
    )

    assert form.tags == "Python, python, Data Engineering"
    assert "tags" not in form.as_model_data()


@pytest.mark.parametrize("field", ["status", "published_at"])
def test_article_form_explicitly_rejects_editorial_mass_assignment(
    field: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        ArticleForm.from_mapping(
            valid_article_mapping(**{field: "adulterated"})
        )

    assert "Campos editoriais protegidos" in str(error.value)
    assert field in str(error.value)


def test_article_form_does_not_render_or_sanitize_markdown() -> None:
    markdown = "# Título\n\n<script>alert('x')</script>"

    form = ArticleForm.from_mapping(
        valid_article_mapping(content_markdown=markdown)
    )

    assert form.content_markdown == markdown


def test_category_form_strips_and_requires_a_name() -> None:
    assert CategoryForm.from_mapping({"name": "  Data Engineering  "}).name == (
        "Data Engineering"
    )

    with pytest.raises(ValidationError):
        CategoryForm.from_mapping({"name": "   "})
