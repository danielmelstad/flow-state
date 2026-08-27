import os
import subprocess
from pathlib import Path

from tempo_log.sources.git_commits import discover_repos, read_events


def _git(repo: Path, *args, env=None):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def make_repo(path: Path, commits):
    """commits: list of (iso_date, author_email, subject) or (iso_date, author_email, subject, committer_date)."""
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    for i, commit in enumerate(commits):
        (path / f"f{i}").write_text(str(i))
        _git(path, "add", ".")
        when = commit[0]
        email = commit[1]
        subject = commit[2]
        committer_date = commit[3] if len(commit) > 3 else when
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=committer_date,
                   GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_EMAIL=email,
                   GIT_AUTHOR_NAME="t", GIT_COMMITTER_NAME="t")
        _git(path, "commit", "-q", "-m", subject, env=env)


def test_discover_repos_finds_top_level_and_worktree_dirs(tmp_path):
    make_repo(tmp_path / "repo-a", [("2026-08-25T10:00:00+00:00", "a@x", "init")])
    (tmp_path / "not-a-repo").mkdir()
    wt = tmp_path / ".worktrees" / "T-1" / "repo-a"
    make_repo(wt, [("2026-08-25T10:00:00+00:00", "a@x", "init")])
    found = discover_repos(tmp_path)
    assert found == [tmp_path / "repo-a", wt]


def test_read_events_filters_by_author_and_range(tmp_path, utc):
    repo = tmp_path / "r"
    make_repo(repo, [
        ("2026-08-25T10:00:00+00:00", "me@x", "ADA-1: first"),
        ("2026-08-25T11:00:00+00:00", "other@x", "ADA-2: not mine"),
        ("2026-08-26T09:00:00+00:00", "me@x", "ADA-3: next day"),
    ])
    events = read_events([repo], ["me@x"], utc(2026, 8, 25), utc(2026, 8, 26))
    assert [e.text for e in events] == ["ADA-1: first"]
    e = events[0]
    assert e.source == "git" and e.session is None and e.branch is None
    assert e.cwd == str(repo)
    assert e.ts == utc(2026, 8, 25, 10)


def test_unreadable_repo_is_skipped(tmp_path, utc):
    assert read_events([tmp_path / "missing"], ["me@x"], utc(2026, 1, 1), utc(2026, 1, 2)) == []


def test_author_date_inside_window_counts_even_if_committed_later(tmp_path, utc):
    repo = tmp_path / "r"
    make_repo(repo, [
        ("2026-08-25T10:00:00+00:00", "me@x", "ADA-1: early author date",
         "2026-08-27T10:00:00+00:00"),
    ])
    events = read_events([repo], ["me@x"], utc(2026, 8, 25), utc(2026, 8, 26))
    assert len(events) == 1
    assert events[0].text == "ADA-1: early author date"
    assert events[0].ts == utc(2026, 8, 25, 10)


def test_author_date_inside_window_counts_even_if_committed_earlier(tmp_path, utc):
    repo = tmp_path / "r"
    make_repo(repo, [
        ("2026-08-25T10:00:00+00:00", "me@x", "ADA-1: late author date",
         "2026-08-01T10:00:00+00:00"),
    ])
    events = read_events([repo], ["me@x"], utc(2026, 8, 25), utc(2026, 8, 26))
    assert len(events) == 1
    assert events[0].text == "ADA-1: late author date"
    assert events[0].ts == utc(2026, 8, 25, 10)


def test_same_commit_in_repo_and_worktree_counted_once(tmp_path, utc):
    repo = tmp_path / "repo"
    make_repo(repo, [("2026-08-25T10:00:00+00:00", "me@x", "ADA-1: shared")])
    wt = tmp_path / "worktree"
    _git(repo, "worktree", "add", str(wt), "-b", "T-1")
    events = read_events([repo, wt], ["me@x"], utc(2026, 8, 25), utc(2026, 8, 26))
    assert len(events) == 1
    assert events[0].text == "ADA-1: shared"


def test_case_insensitive_author_match(tmp_path, utc):
    repo = tmp_path / "r"
    make_repo(repo, [("2026-08-25T10:00:00+00:00", "Me@X", "ADA-1: upper")])
    events = read_events([repo], ["me@x"], utc(2026, 8, 25), utc(2026, 8, 26))
    assert len(events) == 1
    assert events[0].text == "ADA-1: upper"
