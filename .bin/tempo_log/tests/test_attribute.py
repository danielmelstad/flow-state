import re

from tempo_log.attribute import attribute, ticket_from_raw
from tempo_log.models import RawEvent

PAT = re.compile(r"[A-Z][A-Z0-9]+-[0-9]+")


def raw(utc, h, m=0, session="s", cwd="/hub", branch="main", paths=(), text="", source="claude"):
    return RawEvent(utc(2026, 8, 25, h, m), source, session, cwd, branch, tuple(paths), text)


def test_rule_worktree_cwd(utc):
    assert ticket_from_raw(raw(utc, 9, cwd="/hub/.worktrees/ADA-486/repo"), PAT) == "ADA-486"


def test_rule_worktree_path_in_tool_call(utc):
    e = raw(utc, 9, paths=["/hub/.worktrees/WI-100/svc/a.py"], text="ADA-1 mentioned")
    assert ticket_from_raw(e, PAT) == "WI-100"  # path beats text


def test_rule_branch(utc):
    assert ticket_from_raw(raw(utc, 9, branch="ADA-486-aca-hostname"), PAT) == "ADA-486"


def test_rule_commit_prefix(utc):
    e = raw(utc, 9, source="git", session=None, branch=None, text="FTT-72: Fix thing")
    assert ticket_from_raw(e, PAT) == "FTT-72"


def test_commit_without_prefix_is_unattributed(utc):
    e = raw(utc, 9, source="git", session=None, branch=None, text="ci: tidy up FTT-72 later")
    assert ticket_from_raw(e, PAT) is None


def test_rule_text_mention(utc):
    assert ticket_from_raw(raw(utc, 9, text="please work on WNR-69 today"), PAT) == "WNR-69"


def test_main_branch_and_plain_cwd_unattributed(utc):
    assert ticket_from_raw(raw(utc, 9), PAT) is None


def test_stickiness_within_session(utc):
    events = attribute([
        raw(utc, 9, 0, text="hello"),
        raw(utc, 9, 5, text="work on ADA-486"),
        raw(utc, 9, 10),
        raw(utc, 9, 15, text="switch to WI-100"),
        raw(utc, 9, 20),
        raw(utc, 9, 25, session="other"),
    ], PAT)
    assert [e.ticket for e in events] == [None, "ADA-486", "ADA-486", "WI-100", "WI-100", None]


def test_stickiness_respects_time_order_not_input_order(utc):
    events = attribute([raw(utc, 9, 10), raw(utc, 9, 5, text="ADA-1")], PAT)
    assert [(e.ts.minute, e.ticket) for e in events] == [(5, "ADA-1"), (10, "ADA-1")]


def test_git_events_never_sticky(utc):
    events = attribute([
        raw(utc, 9, 0, source="git", session=None, branch=None, text="ADA-1: x"),
        raw(utc, 9, 1, source="git", session=None, branch=None, text="tidy"),
    ], PAT)
    assert [e.ticket for e in events] == ["ADA-1", None]
