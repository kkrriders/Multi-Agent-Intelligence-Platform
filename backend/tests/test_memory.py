import uuid

from app.memory import history_to_messages, search_memory, upsert_memory


def test_history_to_messages_converts_runs_to_alternating_turns():
    history = [
        {"input": "hello", "output": "hi there"},
        {"input": "how are you", "output": "doing well"},
    ]
    assert history_to_messages(history) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "how are you"},
        {"role": "assistant", "content": "doing well"},
    ]


def test_history_to_messages_empty_history_returns_empty_list():
    assert history_to_messages([]) == []


def test_upsert_then_search_returns_matching_memory(qdrant_available):
    run_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    upsert_memory(
        run_id=run_id,
        project_id=project_id,
        conversation_id=conversation_id,
        input="The launch codeword for our rocket is Bluebird.",
        output="Got it, noted.",
    )

    results = search_memory(project_id, "rocket launch codeword")

    assert any(r["run_id"] == run_id for r in results)
    assert all(r["project_id"] == project_id for r in results)
