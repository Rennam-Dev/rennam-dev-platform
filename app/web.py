import bleach
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
