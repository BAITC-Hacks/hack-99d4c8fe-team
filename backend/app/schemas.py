from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class Question(BaseModel):
    id: str
    text: str
    label: str | None = None
    placeholder: str | None = None


class StartDraftRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=10000)
    category: str = Field(min_length=1, max_length=100)


class AnswerItem(BaseModel):
    questionId: str
    answer: str = Field(min_length=1, max_length=10000)


class AnswerRoundRequest(BaseModel):
    round: int = Field(ge=1, le=3)
    answers: list[AnswerItem] = Field(min_length=1)


class TaskFields(BaseModel):
    title: str = ""
    context: str = ""
    need: str = ""
    users: str = ""
    data: str = ""
    constraints: str = ""
    expectedResult: str = ""
    successCriteria: str = ""
    contact: str = ""
    collaboration: str = ""


class PublishDraftRequest(BaseModel):
    category: str
    fields: TaskFields
    finalText: str = Field(min_length=1, max_length=20000)
    useGeneratedText: bool


class AIQuestionsResult(BaseModel):
    questions: list[Question]


class AIAssessmentResult(BaseModel):
    ready: bool
    questions: list[Question] = Field(default_factory=list)
    finalText: str | None = None
    taskFields: TaskFields | None = None
    rating: int | None = Field(default=None, ge=0, le=100)
    message: str | None = None


class UpdateTaskRequest(BaseModel):
    fields: TaskFields


class TeamResponseRequest(BaseModel):
    teamName: str = Field(min_length=1, max_length=160)
    idea: str = Field(min_length=1, max_length=10000)
    plan: str = Field(min_length=1, max_length=10000)
    prototypeUrl: str = Field(default="", max_length=2000)

    @field_validator("prototypeUrl")
    @classmethod
    def valid_prototype_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if value and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
            raise ValueError("Ссылка на прототип должна начинаться с https:// или http://.")
        return value


class ResponseStatusRequest(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")
