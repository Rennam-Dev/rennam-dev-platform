from pathlib import Path

import bleach
import frontmatter
import markdown
from markupsafe import Markup
from starlette.templating import Jinja2Templates

from app.core.config import BASE_DIR, settings

templates = Jinja2Templates(directory=BASE_DIR / "templates")


def render_markdown(value: str) -> Markup:
    html = markdown.markdown(
        value or "",
        extensions=["fenced_code", "tables", "sane_lists"],
    )
    cleaned = bleach.clean(
        html,
        tags={
            "p",
            "br",
            "strong",
            "em",
            "a",
            "ul",
            "ol",
            "li",
            "h2",
            "h3",
            "h4",
            "blockquote",
            "code",
            "pre",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        },
        attributes={"a": ["href", "title", "rel"]},
        protocols={"http", "https", "mailto"},
    )
    return Markup(cleaned)


templates.env.filters["markdown"] = render_markdown


def public_context(request, active: str, **extra) -> dict:
    return {
        "request": request,
        "active": active,
        "settings": settings,
        **extra,
    }


def load_posts() -> list[dict]:
    posts = []
    blog_dir = BASE_DIR / "content" / "blog"
    for path in blog_dir.glob("*.md"):
        document = frontmatter.load(path)
        posts.append(
            {
                "slug": path.stem,
                "title": document.get("titulo", path.stem),
                "date": document.get("data", ""),
                "summary": document.get("resumo", ""),
                "tags": document.get("tags", []),
                "body": document.content,
            }
        )
    return sorted(posts, key=lambda post: str(post["date"]), reverse=True)


def load_post(slug: str) -> dict | None:
    path = Path(BASE_DIR / "content" / "blog" / f"{slug}.md")
    if not path.exists() or not path.is_file():
        return None
    document = frontmatter.load(path)
    return {
        "slug": slug,
        "title": document.get("titulo", slug),
        "date": document.get("data", ""),
        "summary": document.get("resumo", ""),
        "tags": document.get("tags", []),
        "body": document.content,
    }
