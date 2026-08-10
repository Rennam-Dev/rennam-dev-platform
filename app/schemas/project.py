from collections.abc import Mapping
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    UrlConstraints,
    field_validator,
)

ALLOWED_STATUSES = {"planned", "building", "complete"}
ALLOWED_VISIBILITIES = {"draft", "published"}
PROJECT_URL_MAX_LENGTH = 500
ProjectUrl = Annotated[HttpUrl, UrlConstraints(max_length=PROJECT_URL_MAX_LENGTH)]


class ProjectForm(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    summary: str = Field(min_length=10, max_length=320)
    problem: str = ""
    solution: str = ""
    architecture: str = ""
    decisions: str = ""
    results: str = ""
    learnings: str = ""
    course: str = Field(default="", max_length=180)
    status: str = "planned"
    visibility: str = "draft"
    featured: bool = False
    technologies: str = ""
    repo_url: ProjectUrl | None = None
    demo_url: ProjectUrl | None = None
    cover_image_url: ProjectUrl | None = None
    seo_description: str = Field(default="", max_length=320)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in ALLOWED_STATUSES:
            raise ValueError("Status inválido.")
        return value

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        if value not in ALLOWED_VISIBILITIES:
            raise ValueError("Visibilidade inválida.")
        return value

    @classmethod
    def values_from_mapping(cls, raw: Mapping[str, object]) -> dict[str, object]:
        return {
            "title": raw.get("title", ""),
            "slug": raw.get("slug", ""),
            "summary": raw.get("summary", ""),
            "problem": raw.get("problem", ""),
            "solution": raw.get("solution", ""),
            "architecture": raw.get("architecture", ""),
            "decisions": raw.get("decisions", ""),
            "results": raw.get("results", ""),
            "learnings": raw.get("learnings", ""),
            "course": raw.get("course", ""),
            "status": raw.get("status", "planned"),
            "visibility": raw.get("visibility", "draft"),
            "featured": raw.get("featured") == "on",
            "technologies": raw.get("technologies", ""),
            "repo_url": raw.get("repo_url") or None,
            "demo_url": raw.get("demo_url") or None,
            "cover_image_url": raw.get("cover_image_url") or None,
            "seo_description": raw.get("seo_description", ""),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        return cls.model_validate(cls.values_from_mapping(raw))

    def as_model_data(self) -> dict:
        data = self.model_dump(exclude={"technologies"})
        for key in ("repo_url", "demo_url", "cover_image_url"):
            data[key] = str(data[key]) if data[key] else ""
        return data
