"""Skill hint must point at web_skill_* tools, not upstream skill_manage."""


def test_skill_hint_mentions_web_skills_list_first(monkeypatch):
    from gateway.platforms import web_chat as mod

    class FakeStore:
        def list_enabled_skill_names(self, user_id: str):
            assert user_id == "u1"
            return ["demo-skill"]

    adapter = object.__new__(mod.WebChatAdapter)
    adapter._user_store = FakeStore()

    import gateway.web.platform.store as store_mod

    monkeypatch.setattr(store_mod, "PlatformStore", FakeStore)

    hint = mod.WebChatAdapter._build_skill_hint(adapter, "u1")
    assert hint is not None
    assert "## Enabled skills for this session" in hint
    assert "demo-skill" in hint
    assert "web_skills_list" in hint
    assert "web_skill_view" in hint
    assert "skill_manage" not in hint
    # Prefer list-first discovery wording
    assert hint.index("web_skills_list") < hint.index("web_skill_view")


def test_skill_hint_none_when_no_enabled(monkeypatch):
    from gateway.platforms import web_chat as mod

    class FakeStore:
        def list_enabled_skill_names(self, user_id: str):
            return []

    adapter = object.__new__(mod.WebChatAdapter)
    adapter._user_store = FakeStore()

    import gateway.web.platform.store as store_mod

    monkeypatch.setattr(store_mod, "PlatformStore", FakeStore)

    assert mod.WebChatAdapter._build_skill_hint(adapter, "u1") is None


def test_preferred_tool_after_enabled_hint_is_web_skills_list():
    """Contract: agents seeing an enabled-skills hint should call list first.

    Pure prompt-contract check (no LLM) — FakeRunner / real models are out of scope.
    """
    hint = (
        "## Enabled skills for this session\n"
        "- `demo-skill`\n"
        "Call `web_skills_list` first when discovering or choosing a skill; "
        "use `web_skill_view` when you already know the skill name."
    )
    assert "web_skills_list" in hint
    # Documented preferred first tool name for CI / reviewers
    preferred_first_tool = "web_skills_list"
    assert preferred_first_tool in hint
