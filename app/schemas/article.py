from collections.abc import Mapping
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROTECTED_AUTHORSHIP_FIELDS = frozenset({"published_at", "status"})


class ArticleForm(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    slug: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    summary: str = Field(min_length=1, max_length=320)
    content_markdown: str = Field(min_length=1)
    section: Literal["blog", "journal"]
    category_id: int | None = Field(default=None, gt=0)
    tags: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("section", mode="before")
    @classmethod
    def strip_section_whitespace(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="before")
    @classmethod
    def reject_protected_authorship_fields(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        received = sorted(PROTECTED_AUTHORSHIP_FIELDS.intersection(value))
        if received:
            fields = ", ".join(received)
            raise ValueError(
                f"Campos editoriais protegidos não são aceitos na autoria: {fields}."
            )
        return value

    @classmethod
    def values_from_mapping(cls, raw: Mapping[str, object]) -> dict[str, object]:
        raw_category_id = raw.get("category_id")
        category_id = (
            None
            if raw_category_id is None
            or isinstance(raw_category_id, str)
            and not raw_category_id.strip()
            else raw_category_id
        )
        values: dict[str, object] = {
            "title": raw.get("title", ""),
            "slug": raw.get("slug", ""),
            "summary": raw.get("summary", ""),
            "content_markdown": raw.get("content_markdown", ""),
            "section": raw.get("section", ""),
            "category_id": category_id,
            "tags": raw.get("tags", ""),
        }
        for field in PROTECTED_AUTHORSHIP_FIELDS:
            if field in raw:
                values[field] = raw[field]
        return values

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        return cls.model_validate(cls.values_from_mapping(raw))

    def as_model_data(self) -> dict[str, object]:
        return self.model_dump(exclude={"tags"})


class CategoryForm(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    model_config = ConfigDict(str_strip_whitespace=True)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        return cls.model_validate({"name": raw.get("name", "")})
