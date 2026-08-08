import re


def csrf_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def login(client):
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


def test_admin_requires_login(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_admin_can_create_project(client):
    login(client)
    form_page = client.get("/admin/projetos/novo")
    response = client.post(
        "/admin/projetos/novo",
        data={
            "csrf_token": csrf_from(form_page),
            "title": "Rennam Semantic Docs",
            "slug": "rennam-semantic-docs",
            "summary": "Busca semântica em documentos com fontes verificáveis.",
            "status": "building",
            "visibility": "published",
            "featured": "on",
            "technologies": "Python, FastAPI, pgvector",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    public_page = client.get("/projetos/rennam-semantic-docs")
    assert public_page.status_code == 200
    assert "Rennam Semantic Docs" in public_page.text
    assert "pgvector" in public_page.text


def test_csrf_is_required(client):
    login(client)
    response = client.post(
        "/admin/projetos/novo",
        data={
            "title": "Sem CSRF",
            "slug": "sem-csrf",
            "summary": "Esta requisição deve ser recusada pelo servidor.",
        },
    )
    assert response.status_code == 403
