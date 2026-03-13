from pathlib import Path

import pytest

import __autoversion__


def test_try_fix_num_numeric_and_non_numeric():
    assert __autoversion__.try_fix_num("07") == 7
    assert __autoversion__.try_fix_num("abc") == "abc"


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.3", ((1, 0, 3),)),
        ("1.0.3-dev", ((1, 0, 3), ("dev",))),
        ("1.0.3-rc-5", ((1, 0, 3), ("rc",), (5,))),
        (None, (("unknown",),)),
    ],
)
def test_tupleize_version(version, expected):
    assert __autoversion__.tupleize_version(version) == expected


def test_getversion_uses_distribution_version_when_not_repo(monkeypatch):
    class FakeDistribution:
        version = "9.9.9"

        def locate_file(self, _):
            return Path("/tmp/not-a-repo")

    monkeypatch.setattr(
        __autoversion__.metadata, "distribution", lambda _: FakeDistribution()
    )
    monkeypatch.setitem(
        __autoversion__.getversion.__globals__, "get_repo_type", lambda _: None
    )

    assert __autoversion__.getversion("example") == "9.9.9"


def test_getversion_uses_repo_version_when_repo(monkeypatch):
    class FakeDistribution:
        version = "9.9.9"

        def locate_file(self, _):
            return Path("/tmp/repo")

    class FakeRepoType:
        @staticmethod
        def get_version(path):
            return f"git-{path}"

    monkeypatch.setattr(
        __autoversion__.metadata, "distribution", lambda _: FakeDistribution()
    )
    monkeypatch.setitem(
        __autoversion__.getversion.__globals__, "get_repo_type", lambda _: FakeRepoType
    )

    assert __autoversion__.getversion("example") == "git-/tmp/repo"
