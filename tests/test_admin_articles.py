import re
from datetime import UTC, datetime

import pytest
from fastapi import Request

from app.core.database import SessionLocal
from app.models import Article, Category
from app.repositories import articles as article_repository
from app.routes import admin_articles as admin_article_routes


def csrf_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def login(client) -> None:
    login_page = client.get("/admin/login")
    response = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_from(login_page),
            "username": "rennam",
            "password": "test-password",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def article_data(csrf_token: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "csrf_token": csrf_token,
        "title": "Admin Article",
        "slug": "admin-article",
        "summary": "Article created through the protected admin authorship flow.",
        "content_markdown": "# Admin Article\n\nMarkdown **bruto**.",
        "section": "blog",
        "category_id": "",
        "tags": "Python, FastAPI",
    }
    values.update(overrides)
    return values


def create_article(client, **overrides: object) -> int:
    page = client.get("/admin/artigos/novo")
    response = client.post(
        "/admin/artigos/novo",
        data=article_data(csrf_from(page), **overrides),
        follow_redirects=False,
    )
    assert response.status_code == 303
    match = re.fullmatch(
        r"/admin/artigos/(\d+)/editar\?saved=1",
        response.headers["location"],
    )
    assert match
    return int(match.group(1))


def create_category(client, name: str = "Engineering") -> int:
    page = client.get("/admin/categorias")
    response = client.post(
        "/admin/categorias/nova",
        data={"csrf_token": csrf_from(page), "name": name},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with SessionLocal() as db:
        category = article_repository.get_category_by_slug(
            db,
            admin_article_routes.article_service.slugify(name),
        )
        assert category is not None
        return category.id


def test_authenticated_article_and_category_pages_render(client) -> None:
    login(client)

    article_list = client.get("/admin/artigos")
    new_article = client.get("/admin/artigos/novo")
    categories = client.get("/admin/categorias")

    assert article_list.status_code == 200
    assert new_article.status_code == 200
    assert categories.status_code == 200
    assert article_list.headers["cache-control"] == "no-store"
    assert new_article.headers["cache-control"] == "no-store"
    assert categories.headers["cache-control"] == "no-store"
    assert 'name="status"' not in new_article.text
    assert 'name="published_at"' not in new_article.text
    assert 'name="content_markdown"' in new_article.text
    assert 'href="/admin">projetos</a>' in article_list.text
    assert 'href="/admin/artigos">artigos</a>' in article_list.text
    assert 'href="/admin/categorias">categorias</a>' in article_list.text


def test_admin_can_create_and_list_draft_article_with_category_and_tags(
    client,
) -> None:
    login(client)
    category_id = create_category(client)

    article_id = create_article(client, category_id=str(category_id))

    with SessionLocal() as db:
        article = article_repository.get_by_id(db, article_id)
        assert article is not None
        assert article.status == "draft"
        assert article.published_at is None
        assert article.category is not None
        assert article.category.name == "Engineering"
        assert {tag.slug for tag in article.tags} == {"python", "fastapi"}

    article_list = client.get("/admin/artigos")
    assert article_list.status_code == 200
    assert "Admin Article" in article_list.text
    assert "Engineering" in article_list.text
    assert "draft" in article_list.text
    assert "blog" in article_list.text


def test_admin_can_edit_article_and_redisplay_current_tags(client) -> None:
    login(client)
    article_id = create_article(client)
    edit_page = client.get(f"/admin/artigos/{article_id}/editar")

    assert edit_page.status_code == 200
    assert 'value="Python, FastAPI"' in edit_page.text

    response = client.post(
        f"/admin/artigos/{article_id}/editar",
        data=article_data(
            csrf_from(edit_page),
            title="Updated Admin Article",
            section="journal",
            tags="Python, PostgreSQL",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/admin/artigos/{article_id}/editar?saved=1"
    )
    with SessionLocal() as db:
        article = article_repository.get_by_id(db, article_id)
        assert article is not None
        assert article.title == "Updated Admin Article"
        assert article.section == "journal"
        assert article.status == "draft"
        assert article.published_at is None
        assert {tag.slug for tag in article.tags} == {"python", "postgresql"}


@pytest.mark.parametrize("method", ["get", "post"])
def test_missing_article_edit_returns_controlled_404(client, method: str) -> None:
    login(client)
    if method == "get":
        response = client.get("/admin/artigos/999999/editar")
    else:
        page = client.get("/admin/artigos/novo")
        response = client.post(
            "/admin/artigos/999999/editar",
            data=article_data(csrf_from(page)),
        )

    assert response.status_code == 404
    assert "Artigo não encontrado" in response.text
    assert "sqlalchemy" not in response.text.lower()


def test_article_validation_error_redisplays_all_authorship_values(client) -> None:
    login(client)
    category_id = create_category(client, "Data Engineering")
    page = client.get("/admin/artigos/novo")

    response = client.post(
        "/admin/artigos/novo",
        data=article_data(
            csrf_from(page),
            title="",
            slug="valor-digitado",
            summary="Resumo digitado deve permanecer.",
            content_markdown="# Markdown digitado\n\nNão pode desaparecer.",
            section="journal",
            category_id=str(category_id),
            tags="Data, PostgreSQL",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert 'name="slug" value="valor-digitado"' in response.text
    assert "Resumo digitado deve permanecer." in response.text
    assert "# Markdown digitado" in response.text
    assert "Não pode desaparecer." in response.text
    assert re.search(r'<option value="journal" selected>', response.text)
    assert re.search(
        rf'<option value="{category_id}" selected>',
        response.text,
    )
    assert 'name="tags" value="Data, PostgreSQL"' in response.text


@pytest.mark.parametrize("field", ["status", "published_at"])
@pytest.mark.parametrize("operation", ["create", "update"])
def test_protected_editorial_fields_return_422_without_mutation_service(
    client,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    operation: str,
) -> None:
    login(client)
    if operation == "create":
        path = "/admin/artigos/novo"
        page = client.get(path)
        monkeypatch.setattr(
            admin_article_routes.article_service,
            "create_article",
            lambda *_args, **_kwargs: pytest.fail("create service must not run"),
        )
    else:
        article_id = create_article(client)
        path = f"/admin/artigos/{article_id}/editar"
        page = client.get(path)
        monkeypatch.setattr(
            admin_article_routes.article_service,
            "update_article",
            lambda *_args, **_kwargs: pytest.fail("update service must not run"),
        )
    data = article_data(csrf_from(page))
    data[field] = "published" if field == "status" else "2026-08-13T12:00:00Z"

    response = client.post(path, data=data, follow_redirects=False)

    assert response.status_code == 422
    assert "Campos editoriais protegidos" in response.text
    assert field in response.text
    assert f'name="{field}"' not in response.text


@pytest.mark.parametrize(
    ("path", "service_name", "data_factory"),
    [
        (
            "/admin/artigos/novo",
            "create_article",
            lambda token: article_data(token),
        ),
        (
            "/admin/categorias/nova",
            "create_category",
            lambda token: {"csrf_token": token, "name": "Security"},
        ),
    ],
)
def test_invalid_csrf_stops_create_services(
    client,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    service_name: str,
    data_factory,
) -> None:
    login(client)
    monkeypatch.setattr(
        admin_article_routes.article_service,
        service_name,
        lambda *_args, **_kwargs: pytest.fail("service must not run before CSRF"),
    )

    response = client.post(
        path,
        data=data_factory("invalid-csrf"),
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_invalid_csrf_stops_edit_repository_and_service(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    monkeypatch.setattr(
        admin_article_routes.article_repository,
        "get_by_id",
        lambda *_args, **_kwargs: pytest.fail("repository must not run before CSRF"),
    )
    monkeypatch.setattr(
        admin_article_routes.article_service,
        "update_article",
        lambda *_args, **_kwargs: pytest.fail("service must not run before CSRF"),
    )

    response = client.post(
        "/admin/artigos/999/editar",
        data=article_data("invalid-csrf"),
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_article_domain_conflict_returns_controlled_422(client) -> None:
    login(client)
    create_article(client)
    page = client.get("/admin/artigos/novo")

    response = client.post(
        "/admin/artigos/novo",
        data=article_data(
            csrf_from(page),
            title="Conflicting Article",
            content_markdown="# Value preserved",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "já está sendo usado por outro artigo nesta seção" in response.text
    assert "# Value preserved" in response.text
    assert "sqlalchemy" not in response.text.lower()


def test_invalid_article_update_returns_422_without_calling_service(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    article_id = create_article(client)
    edit_page = client.get(f"/admin/artigos/{article_id}/editar")
    monkeypatch.setattr(
        admin_article_routes.article_service,
        "update_article",
        lambda *_args, **_kwargs: pytest.fail("invalid form must not reach service"),
    )

    response = client.post(
        f"/admin/artigos/{article_id}/editar",
        data=article_data(
            csrf_from(edit_page),
            title="",
            summary="Updated summary must not be persisted.",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "title:" in response.text
    assert "Updated summary must not be persisted." in response.text
    with SessionLocal() as db:
        article = db.get(Article, article_id)
        assert article is not None
        assert article.title == "Admin Article"
        assert article.summary == (
            "Article created through the protected admin authorship flow."
        )


def test_article_update_url_conflict_returns_controlled_422(client) -> None:
    login(client)
    create_article(client, slug="existing-url")
    article_id = create_article(
        client,
        slug="editable-url",
        title="Editable Article",
    )
    edit_page = client.get(f"/admin/artigos/{article_id}/editar")

    response = client.post(
        f"/admin/artigos/{article_id}/editar",
        data=article_data(
            csrf_from(edit_page),
            slug="existing-url",
            title="Must Not Persist",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "já está sendo usado por outro artigo nesta seção" in response.text
    assert 'name="slug" value="existing-url"' in response.text
    with SessionLocal() as db:
        article = db.get(Article, article_id)
        assert article is not None
        assert article.slug == "editable-url"
        assert article.title == "Editable Article"


def test_published_history_url_change_returns_controlled_422(client) -> None:
    login(client)
    article_id = create_article(client)
    first_publication = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    with SessionLocal() as db:
        article = db.get(Article, article_id)
        assert article is not None
        article.published_at = first_publication
        db.commit()
    edit_page = client.get(f"/admin/artigos/{article_id}/editar")

    response = client.post(
        f"/admin/artigos/{article_id}/editar",
        data=article_data(
            csrf_from(edit_page),
            slug="changed-url",
            title="Must Not Persist",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "não pode ser alterado após a primeira publicação" in response.text
    assert 'name="slug" value="changed-url"' in response.text
    with SessionLocal() as db:
        article = db.get(Article, article_id)
        assert article is not None
        assert article.slug == "admin-article"
        assert article.title == "Admin Article"
        assert article.published_at == first_publication


def test_category_create_validation_conflict_and_redisplay(client) -> None:
    login(client)
    category_id = create_category(client, "Ciência de Dados")
    with SessionLocal() as db:
        category = db.get(Category, category_id)
        assert category is not None
        assert category.slug == "ciencia-de-dados"

    page = client.get("/admin/categorias")
    conflict = client.post(
        "/admin/categorias/nova",
        data={"csrf_token": csrf_from(page), "name": "Ciencia de Dados"},
        follow_redirects=False,
    )
    assert conflict.status_code == 422
    assert "já está sendo usado por outra categoria" in conflict.text
    assert 'name="name" value="Ciencia de Dados"' in conflict.text

    invalid = client.post(
        "/admin/categorias/nova",
        data={"csrf_token": csrf_from(conflict), "name": ""},
        follow_redirects=False,
    )
    assert invalid.status_code == 422
    assert "name:" in invalid.text


def test_each_admin_authorship_post_reads_form_once(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    calls: dict[str, int] = {}
    original_form = Request.form

    def counted_form(request: Request, *args: object, **kwargs: object):
        calls[request.url.path] = calls.get(request.url.path, 0) + 1
        return original_form(request, *args, **kwargs)

    monkeypatch.setattr(Request, "form", counted_form)

    new_page = client.get("/admin/artigos/novo")
    article_response = client.post(
        "/admin/artigos/novo",
        data=article_data(csrf_from(new_page)),
        follow_redirects=False,
    )
    assert article_response.status_code == 303
    article_id = int(article_response.headers["location"].split("/")[3])

    edit_page = client.get(f"/admin/artigos/{article_id}/editar")
    edit_response = client.post(
        f"/admin/artigos/{article_id}/editar",
        data=article_data(csrf_from(edit_page), title="Read Once"),
        follow_redirects=False,
    )
    assert edit_response.status_code == 303

    categories_page = client.get("/admin/categorias")
    category_response = client.post(
        "/admin/categorias/nova",
        data={"csrf_token": csrf_from(categories_page), "name": "Read Once"},
        follow_redirects=False,
    )
    assert category_response.status_code == 303

    assert calls == {
        "/admin/artigos/novo": 1,
        f"/admin/artigos/{article_id}/editar": 1,
        "/admin/categorias/nova": 1,
    }


def test_service_error_redisplay_uses_controlled_values(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    page = client.get("/admin/artigos/novo")

    def controlled_failure(*_args: object, **_kwargs: object) -> None:
        raise admin_article_routes.article_service.ArticleTagError(
            "tags: conflito controlado."
        )

    monkeypatch.setattr(
        admin_article_routes.article_service,
        "create_article",
        controlled_failure,
    )
    response = client.post(
        "/admin/artigos/novo",
        data=article_data(
            csrf_from(page),
            title="Preserved title",
            tags="Conflicting, Tags",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "tags: conflito controlado." in response.text
    assert 'name="title" value="Preserved title"' in response.text
    assert 'name="tags" value="Conflicting, Tags"' in response.text


def test_no_article_publication_or_preview_routes_exist(client) -> None:
    login(client)
    article_id = create_article(client)
    page = client.get("/admin/artigos")
    csrf_token = csrf_from(page)

    assert client.get(f"/admin/artigos/{article_id}/preview").status_code == 404
    assert client.post(
        f"/admin/artigos/{article_id}/publicar",
        data={"csrf_token": csrf_token},
    ).status_code == 404
    assert client.get("/journal").status_code == 404
