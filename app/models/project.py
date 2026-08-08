from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

project_technologies = Table(
    "project_technologies",
    Base.metadata,
    Column(
        "project_id",
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technology_id",
        ForeignKey("technologies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(320))
    problem: Mapped[str] = mapped_column(Text, default="")
    solution: Mapped[str] = mapped_column(Text, default="")
    architecture: Mapped[str] = mapped_column(Text, default="")
    decisions: Mapped[str] = mapped_column(Text, default="")
    results: Mapped[str] = mapped_column(Text, default="")
    learnings: Mapped[str] = mapped_column(Text, default="")
    course: Mapped[str] = mapped_column(String(180), default="")
    status: Mapped[str] = mapped_column(String(24), default="planned", index=True)
    visibility: Mapped[str] = mapped_column(
        String(24), default="draft", index=True
    )
    featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    repo_url: Mapped[str] = mapped_column(String(500), default="")
    demo_url: Mapped[str] = mapped_column(String(500), default="")
    cover_image_url: Mapped[str] = mapped_column(String(500), default="")
    seo_description: Mapped[str] = mapped_column(String(320), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    technologies: Mapped[list["Technology"]] = relationship(
        secondary=project_technologies,
        back_populates="projects",
        lazy="selectin",
    )


class Technology(Base):
    __tablename__ = "technologies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    projects: Mapped[list[Project]] = relationship(
        secondary=project_technologies,
        back_populates="technologies",
    )
