from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

article_tags = Table(
    "article_tags",
    Base.metadata,
    Column(
        "article_id",
        ForeignKey(
            "articles.id",
            name="fk_article_tags_article_id_articles",
            ondelete="CASCADE",
        ),
        nullable=False,
    ),
    Column(
        "tag_id",
        ForeignKey(
            "tags.id",
            name="fk_article_tags_tag_id_tags",
            ondelete="RESTRICT",
        ),
        nullable=False,
    ),
    PrimaryKeyConstraint(
        "article_id",
        "tag_id",
        name="pk_article_tags",
    ),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_categories"),
        UniqueConstraint("slug", name="uq_categories_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)

    articles: Mapped[list[Article]] = relationship(
        back_populates="category",
        lazy="selectin",
        passive_deletes=True,
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_tags"),
        UniqueConstraint("slug", name="uq_tags_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)

    articles: Mapped[list[Article]] = relationship(
        secondary=article_tags,
        back_populates="tags",
        lazy="selectin",
        passive_deletes=True,
    )


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_articles"),
        UniqueConstraint(
            "section",
            "slug",
            name="uq_articles_section_slug",
        ),
        CheckConstraint(
            "section IN ('blog', 'journal')",
            name="ck_articles_section",
        ),
        CheckConstraint(
            "status IN ('draft', 'published')",
            name="ck_articles_status",
        ),
        CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_articles_published_at_when_published",
        ),
        Index(
            "ix_articles_section_status_published_at",
            "section",
            "status",
            "published_at",
        ),
        Index("ix_articles_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(String(320), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "categories.id",
            name="fk_articles_category_id_categories",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    category: Mapped[Category | None] = relationship(
        back_populates="articles",
        lazy="selectin",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=article_tags,
        back_populates="articles",
        lazy="selectin",
        passive_deletes=True,
    )
