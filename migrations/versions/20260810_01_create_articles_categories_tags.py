"""create articles, categories, and tags

Revision ID: 20260810_01
Revises: 20260728_01
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_01"
down_revision: str | None = "20260728_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint("slug", name="uq_tags_slug"),
    )

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=320), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("section", sa.String(length=24), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "section IN ('blog', 'journal')",
            name="ck_articles_section",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published')",
            name="ck_articles_status",
        ),
        sa.CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_articles_published_at_when_published",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_articles_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_articles"),
        sa.UniqueConstraint(
            "section",
            "slug",
            name="uq_articles_section_slug",
        ),
    )
    op.create_index(
        "ix_articles_category_id",
        "articles",
        ["category_id"],
    )
    op.create_index(
        "ix_articles_section_status_published_at",
        "articles",
        ["section", "status", "published_at"],
    )

    op.create_table(
        "article_tags",
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name="fk_article_tags_article_id_articles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_article_tags_tag_id_tags",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "article_id",
            "tag_id",
            name="pk_article_tags",
        ),
    )


def downgrade() -> None:
    op.drop_table("article_tags")
    op.drop_index(
        "ix_articles_section_status_published_at",
        table_name="articles",
    )
    op.drop_index("ix_articles_category_id", table_name="articles")
    op.drop_table("articles")
    op.drop_table("tags")
    op.drop_table("categories")
