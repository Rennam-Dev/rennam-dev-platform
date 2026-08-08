from app.core.database import SessionLocal
from app.models import Project


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_draft_is_not_public(client):
    with SessionLocal() as db:
        db.add(
            Project(
                title="Projeto secreto",
                slug="projeto-secreto",
                summary="Este projeto ainda está sendo preparado.",
                visibility="draft",
            )
        )
        db.commit()

    assert client.get("/projetos/projeto-secreto").status_code == 404
    assert "Projeto secreto" not in client.get("/projetos").text


def test_published_project_is_public(client):
    with SessionLocal() as db:
        db.add(
            Project(
                title="Busca semântica",
                slug="busca-semantica",
                summary="Busca por significado em documentos técnicos.",
                visibility="published",
                featured=True,
            )
        )
        db.commit()

    detail = client.get("/projetos/busca-semantica")
    assert detail.status_code == 200
    assert "Busca semântica" in detail.text
    assert "Busca semântica" in client.get("/").text
