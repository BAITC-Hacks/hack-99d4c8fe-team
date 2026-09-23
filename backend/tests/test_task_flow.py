from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, drafts, tasks
from app.schemas import AIAssessmentResult, AIQuestionsResult, Question, TaskFields


@pytest.fixture()
def client() -> Iterator[TestClient]:
    drafts.clear()
    tasks.clear()
    with TestClient(app) as test_client:
        yield test_client
    drafts.clear()
    tasks.clear()


def questions_for_round(_draft: dict[str, object], round_number: int) -> AIQuestionsResult:
    return AIQuestionsResult(
        questions=[Question(id=f"q{round_number}", text=f"Question {round_number}")]
    )


def test_task_draft_waits_for_three_rounds_and_publishes(client: TestClient) -> None:
    with patch("app.main.generate_questions", side_effect=questions_for_round) as generate:
        response = client.post(
            "/api/task-drafts",
            json={
                "title": "Test task",
                "description": "A sufficiently detailed task",
                "category": "Tech",
            },
        )

    assert response.status_code == 200
    draft_id = response.json()["draftId"]
    assert response.json()["questions"][0]["id"] == "q1"
    generate.assert_called_once()

    def assessment(_draft, round_number: int, _answers: list[dict[str, str]]) -> AIAssessmentResult:
        if round_number < 3:
            return AIAssessmentResult(
                ready=True,
                finalText="Not final yet",
                taskFields=TaskFields(title="Test task"),
                rating=80,
            )
        return AIAssessmentResult(
            ready=True,
            finalText="Final task text",
            taskFields=TaskFields(title="Test task", context="Final task text"),
            rating=91,
        )

    with (
        patch("app.main.assess_answers", side_effect=assessment),
        patch("app.main.generate_questions", side_effect=questions_for_round) as generate,
    ):
        for round_number in (1, 2):
            result = client.post(
                f"/api/task-drafts/{draft_id}/answers",
                json={
                    "round": round_number,
                    "answers": [{"questionId": f"q{round_number}", "answer": "Answer"}],
                },
            )
            assert result.status_code == 200
            assert result.json()["ready"] is False
            assert result.json()["questions"][0]["id"] == f"q{round_number + 1}"
        final = client.post(
            f"/api/task-drafts/{draft_id}/answers",
            json={"round": 3, "answers": [{"questionId": "q3", "answer": "Answer"}]},
        )
        assert final.status_code == 200
        assert final.json()["ready"] is True
        assert final.json()["rating"] == 91
        assert generate.call_count == 2

    published = client.post(
        f"/api/task-drafts/{draft_id}/publish",
        json={
            "category": "Tech",
            "fields": {"title": "Test task", "context": "Final task text"},
            "finalText": "Final task text",
            "useGeneratedText": True,
        },
    )
    assert published.status_code == 200
    task_id = published.json()["task"]["id"]

    listing = client.get("/api/tasks")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == task_id

    deleted = client.delete(f"/api/tasks/{task_id}")
    assert deleted.status_code == 200
    assert client.get("/api/tasks").json()["items"] == []


def test_missing_openai_key_returns_actionable_error(client: TestClient) -> None:
    with patch(
        "app.main.generate_questions", side_effect=RuntimeError("OPENAI_API_KEY is missing")
    ):
        response = client.post(
            "/api/task-drafts",
            json={
                "title": "Test task",
                "description": "A sufficiently detailed task",
                "category": "Tech",
            },
        )

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_model_json_parser_accepts_fences_and_short_preamble() -> None:
    from app.services.ai_service import _json_from_model

    result = _json_from_model('Ответ:\n```json\n{"ready": true}\n```')
    assert result == {"ready": True}
