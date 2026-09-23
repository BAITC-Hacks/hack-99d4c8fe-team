from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import AIAssessmentResult, AIQuestionsResult, Question, TaskFields


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        yield test_client


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


def test_no_key_completes_three_blocks_without_openai(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_MODE", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    start = client.post(
        "/api/task-drafts",
        json={
            "title": "Community garden",
            "description": "Help make a shared garden for residents",
            "category": "Ecology",
        },
    )
    assert start.status_code == 200
    draft_id = start.json()["draftId"]
    questions = start.json()["questions"]
    for round_number in (1, 2, 3):
        result = client.post(
            f"/api/task-drafts/{draft_id}/answers",
            json={
                "round": round_number,
                "answers": [
                    {"questionId": question["id"], "answer": "Detailed example answer"}
                    for question in questions
                ],
            },
        )
        assert result.status_code == 200
        assert result.json()["ready"] is (round_number == 3)
        questions = result.json().get("questions", [])
    assert result.json()["rating"] == 100
    publish = client.post(
        f"/api/task-drafts/{draft_id}/publish",
        json={
            "category": "Ecology",
            "fields": result.json()["taskFields"],
            "finalText": result.json()["finalText"],
            "useGeneratedText": True,
        },
    )
    assert publish.status_code == 200
    assert len(client.get("/api/tasks").json()["items"]) == 1


def test_auto_mode_falls_back_when_provider_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.clarification import generate_questions

    monkeypatch.setenv("AI_MODE", "auto")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")
    with patch("app.services.clarification.generate_with_openai", side_effect=OSError("offline")):
        result = generate_questions({"title": "Title", "description": "Description"}, 1)
    assert len(result.questions) == 2


def test_shared_catalog_owner_actions_and_restart(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_MODE", "demo")
    start = client.post(
        "/api/task-drafts",
        json={"title": "Local task", "description": "Shared task description", "category": "Tech"},
    )
    assert start.status_code == 200
    draft_id = start.json()["draftId"]
    questions = start.json()["questions"]
    for round_number in (1, 2, 3):
        step = client.post(
            f"/api/task-drafts/{draft_id}/answers",
            json={
                "round": round_number,
                "answers": [
                    {"questionId": q["id"], "answer": f"Answer {round_number}"} for q in questions
                ],
            },
        )
        assert step.status_code == 200
        questions = step.json().get("questions", [])
    created = client.post(
        f"/api/task-drafts/{draft_id}/publish",
        json={
            "category": "Tech",
            "fields": step.json()["taskFields"],
            "finalText": step.json()["finalText"],
            "useGeneratedText": True,
        },
    )
    task_id = created.json()["task"]["id"]

    with TestClient(app) as another_browser:
        listing = another_browser.get("/api/tasks").json()["items"]
        assert listing[0]["id"] == task_id
        assert listing[0]["author"] == "Автор задачи"
        assert another_browser.delete(f"/api/tasks/{task_id}").status_code == 403
        proposal = another_browser.post(
            f"/api/tasks/{task_id}/responses",
            json={"teamName": "Team", "idea": "Solution", "plan": "Plan"},
        )
        assert proposal.status_code == 200
        response_id = proposal.json()["response"]["id"]
        assert another_browser.get("/api/tasks").json()["items"][0]["responseCount"] == 1
        assert another_browser.get("/api/tasks").json()["items"][0]["responses"] == []
        assert (
            another_browser.patch(
                f"/api/tasks/{task_id}/responses/{response_id}", json={"status": "accepted"}
            ).status_code
            == 403
        )

    # A fresh app client with the same owner cookie sees data saved on disk.
    with TestClient(app) as returning_owner:
        returning_owner.cookies.update(client.cookies)
        own_task = returning_owner.get("/api/tasks").json()["items"][0]
        assert own_task["author"] == "Вы"
        assert own_task["responses"][0]["idea"] == "Solution"
        accepted = returning_owner.patch(
            f"/api/tasks/{task_id}/responses/{response_id}", json={"status": "accepted"}
        )
        assert accepted.status_code == 200
        fields = {
            key: own_task[key]
            for key in (
                "title",
                "context",
                "need",
                "users",
                "data",
                "constraints",
                "expectedResult",
                "successCriteria",
                "contact",
                "collaboration",
            )
        }
        fields["users"] = ""
        edited = returning_owner.patch(f"/api/tasks/{task_id}", json={"fields": fields})
        assert edited.status_code == 200
        assert edited.json()["task"]["rating"] < own_task["rating"]
        assert returning_owner.delete(f"/api/tasks/{task_id}").status_code == 200
    assert client.get("/api/tasks").json()["items"] == []


def test_health_reports_database_misconfiguration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path))
    result = client.get("/api/health")
    assert result.status_code == 503
    assert "База данных" in result.json()["detail"]
