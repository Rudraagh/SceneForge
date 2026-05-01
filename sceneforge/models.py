"""Shared models and typed helpers for scene generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator
    HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - compatibility fallback
    HAS_PYDANTIC = False

    class ValidationError(ValueError):
        """Fallback validation error when pydantic is unavailable."""

    class BaseModel:
        """Tiny subset of the Pydantic API used by this project."""

        model_config: Dict[str, object] = {}

        def __init__(self, **kwargs):
            annotations = getattr(self, "__annotations__", {})
            for name in annotations:
                if name in kwargs:
                    setattr(self, name, kwargs[name])
                elif hasattr(type(self), name):
                    value = getattr(type(self), name)
                    setattr(self, name, value() if callable(value) and getattr(value, "__name__", "") == "<lambda>" else value)
                else:
                    raise ValidationError(f"Missing required field: {name}")

        @classmethod
        def model_validate(cls, value):
            if isinstance(value, cls):
                return value
            if not isinstance(value, dict):
                raise ValidationError(f"{cls.__name__} expects a mapping.")
            return cls(**value)

        def model_dump(self):
            return {
                name: getattr(self, name)
                for name in getattr(self, "__annotations__", {})
            }

    def Field(default=None, **kwargs):  # noqa: N802
        if "default_factory" in kwargs:
            return kwargs["default_factory"]
        return default

    def field_validator(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


SUPPORTED_RELATIONS = (
    "on",
    "under",
    "inside",
    "beside",
    "near",
    "facing",
    "aligned_with",
    "orbits",
)


class SceneObjectModel(BaseModel):
    """Normalized object entry for a scene graph."""

    name: str
    position: List[float] = Field(min_length=3, max_length=3)
    rotation: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    scale: List[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0], min_length=3, max_length=3)

    @field_validator("position", "rotation", "scale")
    @classmethod
    def _coerce_numeric_triplet(cls, value: List[float]) -> List[float]:
        return [float(value[0]), float(value[1]), float(value[2])]

    @classmethod
    def model_validate(cls, value):
        instance = super().model_validate(value)
        instance.position = instance._coerce_numeric_triplet(instance.position)
        instance.rotation = instance._coerce_numeric_triplet(instance.rotation)
        instance.scale = instance._coerce_numeric_triplet(instance.scale)
        return instance


class RelationModel(BaseModel):
    """Structured relation between two scene objects."""

    source: str = Field(alias="from")
    relation: Literal[
        "on",
        "under",
        "inside",
        "beside",
        "near",
        "facing",
        "aligned_with",
        "orbits",
    ]
    target: str = Field(alias="to")

    model_config = {"populate_by_name": True}

    @classmethod
    def model_validate(cls, value):
        if isinstance(value, dict):
            if "from" in value and "source" not in value:
                value = dict(value)
                value["source"] = value.pop("from")
            if "to" in value and "target" not in value:
                value = dict(value)
                value["target"] = value.pop("to")
        instance = super().model_validate(value)
        if instance.relation not in SUPPORTED_RELATIONS:
            raise ValidationError(f"Unsupported relation: {instance.relation}")
        return instance


class SceneGraphModel(BaseModel):
    """Structured scene graph output."""

    nodes: List[SceneObjectModel]
    edges: List[RelationModel] = Field(default_factory=list)
    layout: Dict[str, object] = Field(default_factory=dict)
    metadata: Dict[str, object] = Field(default_factory=dict)


class SceneClassification(BaseModel):
    """Scene-family prediction with fallback provenance."""

    scene_type: str
    mode_label: str = "generative"
    confidence: float = 0.0
    source: str = "rules"
    reasoning: Optional[str] = None


class LLMSceneResult(BaseModel):
    """Validated LLM scene output plus quality metadata."""

    objects: List[SceneObjectModel]
    confidence: float = Field(ge=0.0, le=1.0)
    repaired: bool = False
    raw_response: str = ""
    errors: List[str] = Field(default_factory=list)


Position3D = Tuple[float, float, float]
