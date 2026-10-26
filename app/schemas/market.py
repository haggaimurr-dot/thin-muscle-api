from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


Kind = Literal["plan", "lesson"]
Cycle = Literal["week", "month", "full"]
Level = Literal["入门", "进阶"]
DayType = Literal["push", "pull", "legs", "rest"]
Session = Literal["am", "pm", "both"]
MediaType = Literal["image", "video", "audio"]


class MediaItem(BaseModel):
    type: MediaType
    url: str
    title: str = ""


class ExerciseItem(BaseModel):
    name: str
    sets: str | int
    reps: str
    load: str = ""
    notes: str = ""
    lesson_node_id: Optional[int] = None  # 学法位：挂具体动作


class DayItem(BaseModel):
    day_type: DayType
    session: Session = "both"
    exercises: list[ExerciseItem] = []


class ListingCreate(BaseModel):
    kind: Kind
    title: str = Field(min_length=1, max_length=128)
    level: Level
    body_range: str = ""
    price_fen: int = Field(gt=0, description="标价（分）=买家实付")
    cover_url: str = ""
    media: list[MediaItem] = []
    body_text: str = ""
    # plan
    cycle: Optional[Cycle] = None
    week_index: Optional[int] = Field(default=None, ge=1, le=52)
    days: Optional[list[DayItem]] = None
    rhythm: str = ""
    # lesson
    topic: Optional[str] = None
    skill_tags: list[str] = []
    steps: list[str] = []
    cues: list[str] = []
    demo_media: list[MediaItem] = []

    @model_validator(mode="after")
    def validate_by_kind(self):
        if self.kind == "plan":
            if self.cycle not in ("week", "month", "full"):
                raise ValueError("plan 须指定 cycle: week|month|full")
            if not self.days:
                raise ValueError("plan 须包含 days[]")
            strength = [d for d in self.days if d.day_type in ("push", "pull", "legs")]
            if len(strength) < 1:
                raise ValueError("plan 至少含一个力量日（push/pull/legs）")
            for d in strength:
                if not d.exercises:
                    raise ValueError(f"{d.day_type} 日至少需要一个动作")
                for ex in d.exercises:
                    if not ex.name or ex.sets in (None, "") or not ex.reps:
                        raise ValueError("动作须含 name / sets / reps")
            if self.topic or self.demo_media:
                # allow empty; but forbid treating as lesson-only
                pass
        else:
            if not self.topic:
                raise ValueError("lesson 须有 topic")
            if not self.demo_media:
                raise ValueError("lesson 须至少 1 条 demo_media")
            if self.days:
                raise ValueError("lesson 禁止带 days[] 当作负荷方案上架")
            if self.cycle:
                raise ValueError("lesson 不要填 cycle")
        return self


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ReplicateRequest(BaseModel):
    ack_weight: bool
    ack_level: bool


class AssembleExercise(BaseModel):
    name: str
    sets: str | int = ""
    reps: str = ""
    load: str = ""
    notes: str = ""
    from_plan_node_id: Optional[int] = None
    lesson_node_id: Optional[int] = None  # 挂到该动作的学法位


class AssembleDay(BaseModel):
    day_type: DayType
    session: Session = "both"
    exercises: list[AssembleExercise] = []


class AssembleRequest(BaseModel):
    title: str = "我的拼装方案"
    cycle: Cycle = "week"
    days: list[AssembleDay]
    ack_weight: bool
    ack_level: bool

    @field_validator("days")
    @classmethod
    def strength_ok(cls, v: list[AssembleDay]):
        strength = [d for d in v if d.day_type in ("push", "pull", "legs")]
        if not strength:
            raise ValueError("拼装须含至少一个力量日")
        for d in strength:
            if not d.exercises:
                raise ValueError(f"{d.day_type} 不能为空力量日")
            # lesson 不能单独填满：每个 exercise 必须有 name（可执行），lesson 只是附加
            for ex in d.exercises:
                if not ex.name:
                    raise ValueError("学法位必须挂在具体动作上，不能用 lesson 单独占满力量日")
        return v
