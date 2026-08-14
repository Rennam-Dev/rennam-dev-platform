from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.repositories import projects as project_repository
from app.web import load_posts, public_context, templates

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]

STATUS_LABELS = {
    "planned": "planejado",
    "building": "em desenvolvimento",
    "complete": "concluído",
}


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: DBSession):
    return templates.TemplateResponse(
        request=request,
        name="public/index.html",
        context=public_context(
            request,
            "home",
            featured_projects=project_repository.list_featured(db),
            posts=load_posts()[:2],
            status_labels=STATUS_LABELS,
        ),
    )


@router.get("/sobre", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="public/about.html",
        context=public_context(request, "about"),
    )


@router.get("/projetos", response_class=HTMLResponse)
def projects(
    request: Request,
    db: DBSession,
    tecnologia: str | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name="public/projects.html",
        context=public_context(
            request,
            "projects",
            projects=project_repository.list_published(db, tecnologia),
            technologies=project_repository.list_technologies(db),
            selected_technology=tecnologia,
            status_labels=STATUS_LABELS,
        ),
    )


@router.get("/projetos/{slug}", response_class=HTMLResponse)
def project_detail(request: Request, slug: str, db: DBSession):
    project = project_repository.get_by_slug(db, slug, published_only=True)
    if project is None:
        return templates.TemplateResponse(
            request=request,
            name="public/404.html",
            context=public_context(request, "projects"),
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request,
        name="public/project_detail.html",
        context=public_context(
            request,
            "projects",
            project=project,
            status_labels=STATUS_LABELS,
        ),
    )


@router.get("/contato", response_class=HTMLResponse)
def contact(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="public/contact.html",
        context=public_context(request, "contact"),
    )


@router.get("/health")
def health(db: DBSession):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "rennam.dev"}


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return f"User-agent: *\nAllow: /\nSitemap: {settings.site_url}/sitemap.xml\n"


@router.get("/sitemap.xml")
def sitemap(db: DBSession):
    static_paths = ["", "/sobre", "/projetos", "/blog", "/contato"]
    project_paths = [
        f"/projetos/{project.slug}" for project in project_repository.list_published(db)
    ]
    post_paths = [f"/blog/{post['slug']}" for post in load_posts()]
    urls = "".join(
        f"<url><loc>{settings.site_url}{path}</loc></url>"
        for path in static_paths + project_paths + post_paths
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
