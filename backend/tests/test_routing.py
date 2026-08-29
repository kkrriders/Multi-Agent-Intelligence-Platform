from langgraph.graph import END

from app.graph.routing import MAX_TOOL_CALLS, MAX_TURNS, allowed_routes, decide_route, route_edge


def _state(**over):
    base = {
        "turn": 1,
        "tool_specs": [{"name": "W"}],
        "tool_calls_made": 0,
        "researcher_runs": 0,
        "scratch": {},
        "verdict": {},
        "route": "",
    }
    base.update(over)
    return base


def test_allowed_routes_basic():
    assert allowed_routes(_state()) == ["researcher", "tool_runner", "executor"]


def test_allowed_routes_drops_tool_runner_when_no_tools():
    assert "tool_runner" not in allowed_routes(_state(tool_specs=[]))


def test_allowed_routes_drops_tool_runner_at_call_cap():
    assert "tool_runner" not in allowed_routes(_state(tool_calls_made=MAX_TOOL_CALLS))


def test_allowed_routes_adds_verifier_once_executor_ran():
    assert "verifier" in allowed_routes(_state(scratch={"executor": "draft"}))


def test_decide_route_passes_through_a_legal_choice():
    assert decide_route(_state(), "researcher") == "researcher"


def test_decide_route_premature_done_walks_the_skeleton_in_order():
    assert decide_route(_state(), "done") == "researcher"
    assert decide_route(_state(scratch={"researcher": "r"}), "done") == "executor"
    assert decide_route(_state(scratch={"researcher": "r", "executor": "d"}), "done") == "verifier"


def test_decide_route_allows_done_after_verdict():
    assert decide_route(_state(scratch={"executor": "d", "researcher": "r"}, verdict={"supported": True}), "done") == "done"


def test_decide_route_allows_researcher_rerun_under_cap():
    assert decide_route(_state(route="researcher", researcher_runs=1), "researcher") == "researcher"


def test_decide_route_blocks_second_researcher_rerun():
    s = _state(route="researcher", researcher_runs=1 + 1, scratch={"researcher": "r"})
    assert decide_route(s, "researcher") == "executor"


def test_decide_route_illegal_choice_falls_back_to_next_skeleton_step():
    assert decide_route(_state(), "banana") == "researcher"
    assert decide_route(_state(scratch={"researcher": "r"}), "banana") == "executor"


def test_decide_route_force_closes_at_max_turns():
    assert decide_route(_state(turn=MAX_TURNS, scratch={}), "researcher") == "executor"
    assert decide_route(_state(turn=MAX_TURNS, scratch={"executor": "d"}, verdict={}), "researcher") == "verifier"
    assert decide_route(_state(turn=MAX_TURNS, scratch={"executor": "d"}, verdict={"supported": True}), "researcher") == "done"


def test_route_edge_maps_done_to_end():
    assert route_edge({"route": "done"}) == END
    assert route_edge({"route": "researcher"}) == "researcher"
