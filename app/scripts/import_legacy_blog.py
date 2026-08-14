import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path

import frontmatter
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.core.database import SessionLocal
from app.services import articles as article_service

LEGACY_BLOG_DIR = BASE_DIR / "content" / "blog"
LEGACY_CATEGORY_NAME = "Conteúdo legado"
LEGACY_CATEGORY_SLUG = "conteudo-legado"


class LegacyBlogImportError(ValueError):
    pass


@dataclass(frozen=True)
class LegacyBlogImportReport:
    created: int
    unchanged: int


def _required_text(
    document: frontmatter.Post,
    key: str,
    path: Path,
) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LegacyBlogImportError(
            f"{path.name}: frontmatter '{key}' deve ser texto não vazio."
        )
    return value


def _parse_published_at(value: object, path: Path) -> datetime:
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            return datetime.combine(value, time.min, tzinfo=UTC)
        elif isinstance(value, str):
            stripped = value.strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped):
                return datetime.combine(
                    date.fromisoformat(stripped),
                    time.min,
                    tzinfo=UTC,
                )
            parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        else:
            raise TypeError
    except (TypeError, ValueError) as error:
        raise LegacyBlogImportError(
            f"{path.name}: frontmatter 'data' possui formato inválido."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_tags(value: object, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise LegacyBlogImportError(
            f"{path.name}: frontmatter 'tags' deve ser uma lista de textos."
        )
    return tuple(item.strip() for item in value)


def _load_legacy_article(path: Path) -> article_service.PublishedArticleImport:
    try:
        document = frontmatter.load(path)
    except Exception as error:
        raise LegacyBlogImportError(
            f"{path.name}: não foi possível interpretar o frontmatter."
        ) from error
    slug = path.stem
    if (
        len(slug) > 120
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) is None
    ):
        raise LegacyBlogImportError(f"{path.name}: slug de arquivo inválido.")
    content_markdown = document.content
    if not content_markdown.strip():
        raise LegacyBlogImportError(f"{path.name}: conteúdo Markdown vazio.")
    return article_service.PublishedArticleImport(
        title=_required_text(document, "titulo", path),
        slug=slug,
        summary=_required_text(document, "resumo", path),
        content_markdown=content_markdown,
        section="blog",
        category_name=LEGACY_CATEGORY_NAME,
        category_slug=LEGACY_CATEGORY_SLUG,
        tags=_parse_tags(document.get("tags"), path),
        published_at=_parse_published_at(document.get("data"), path),
    )


def load_legacy_articles(
    content_dir: Path = LEGACY_BLOG_DIR,
) -> list[article_service.PublishedArticleImport]:
    if not content_dir.is_dir():
        raise LegacyBlogImportError(
            f"Diretório legado não encontrado: {content_dir}."
        )
    paths = sorted(content_dir.glob("*.md"))
    if not paths:
        raise LegacyBlogImportError(
            f"Diretório legado sem nenhum arquivo Markdown: {content_dir}."
        )
    return [_load_legacy_article(path) for path in paths]


def import_legacy_blog(
    db: Session,
    content_dir: Path = LEGACY_BLOG_DIR,
    *,
    now: datetime | None = None,
) -> LegacyBlogImportReport:
    created = 0
    unchanged = 0
    for article in load_legacy_articles(content_dir):
        try:
            outcome = article_service.import_published_article(
                db,
                article,
                now=now,
            )
        except article_service.ArticleImportError as error:
            raise LegacyBlogImportError(
                f"{article.section}/{article.slug}: {error}"
            ) from None
        if outcome == "created":
            created += 1
        else:
            unchanged += 1
    return LegacyBlogImportReport(created=created, unchanged=unchanged)


def main() -> int:
    try:
        with SessionLocal() as db:
            report = import_legacy_blog(db)
    except LegacyBlogImportError as error:
        print(f"Importação abortada: {error}", file=sys.stderr)
        return 1
    print(
        "Importação concluída: "
        f"{report.created} criado(s), {report.unchanged} inalterado(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
