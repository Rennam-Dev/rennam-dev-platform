"""create projects and technologies

Revision ID: 20260728_01
Revises:
Create Date: 2026-07-28
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=320), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("architecture", sa.Text(), nullable=False),
        sa.Column("decisions", sa.Text(), nullable=False),
        sa.Column("results", sa.Text(), nullable=False),
        sa.Column("learnings", sa.Text(), nullable=False),
        sa.Column("course", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("visibility", sa.String(length=24), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("repo_url", sa.String(length=500), nullable=False),
        sa.Column("demo_url", sa.String(length=500), nullable=False),
        sa.Column("cover_image_url", sa.String(length=500), nullable=False),
        sa.Column("seo_description", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_featured", "projects", ["featured"])
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_visibility", "projects", ["visibility"])

    op.create_table(
        "technologies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_technologies_name", "technologies", ["name"], unique=True)
    op.create_index("ix_technologies_slug", "technologies", ["slug"], unique=True)

    op.create_table(
        "project_technologies",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("technology_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["technology_id"], ["technologies.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("project_id", "technology_id"),
    )


def downgrade() -> None:
    op.drop_table("project_technologies")
    op.drop_index("ix_technologies_slug", table_name="technologies")
    op.drop_index("ix_technologies_name", table_name="technologies")
    op.drop_table("technologies")
    op.drop_index("ix_projects_visibility", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_index("ix_projects_featured", table_name="projects")
    op.drop_table("projects")
