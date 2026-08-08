from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

ALLOWED_STATUSES = {"planned", "building", "complete"}
ALLOWED_VISIBILITIES = {"draft", "published"}


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
    repo_url: HttpUrl | None = None
    demo_url: HttpUrl | None = None
    cover_image_url: HttpUrl | None = None
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

    def as_model_data(self) -> dict:
        data = self.model_dump(exclude={"technologies"})
        for key in ("repo_url", "demo_url", "cover_image_url"):
            data[key] = str(data[key]) if data[key] else ""
        return data
