import os
import subprocess
from pathlib import Path

from tempo_log.sources.git_commits import discover_repos, read_events


def _git(repo: Path, *args, env=None):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def make_repo(path: Path, commits):
    """commits: list of (iso_date, author_email, subject)."""
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    for i, (when, email, subject) in enumerate(commits):
        (path / f"f{i}").write_text(str(i))
        _git(path, "add", ".")
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when,
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
