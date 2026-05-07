"""Tests for routing resume / cover-letter output through `oj capture`.

Spec: beacon-route-resume-cover-letter-output-through-the-vault-spec.md
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from beacon.cli import _capture_to_vault, _slugify


class TestSlugify:
    def test_basic(self):
        assert _slugify("Anthropic") == "anthropic"

    def test_punctuation_collapses(self):
        assert _slugify("Anthropic, Inc.") == "anthropic-inc"

    def test_case_and_spaces(self):
        assert _slugify("Forward Deployed Engineer") == "forward-deployed-engineer"

    def test_empty_falls_back(self):
        assert _slugify("") == "unknown"
        assert _slugify("!!!") == "unknown"

    def test_strips_outer_hyphens(self):
        assert _slugify("--foo--") == "foo"


class TestCaptureToVault:
    def test_invokes_oj_capture_with_expected_args(self):
        fake_proc = MagicMock(returncode=0, stdout=json.dumps({
            "_oj_version": "0.3",
            "path": "Job Search/Resumes/2026-05-06-anthropic-resume.md",
            "absolute_path": "/x/Job Search/Resumes/2026-05-06-anthropic-resume.md",
            "title": "2026-05-06 anthropic resume",
            "slug": "2026-05-06-anthropic-resume",
            "folder": "Job Search/Resumes",
            "frontmatter": {},
        }), stderr="")

        with patch("beacon.cli.shutil.which", return_value="/usr/bin/oj"), \
             patch("beacon.cli.subprocess.run", return_value=fake_proc) as run_mock:
            info = _capture_to_vault(
                body="# resume body\n",
                folder="Job Search/Resumes",
                title="2026-05-06 anthropic resume",
                fm_type="resume",
                company="Anthropic",
                role="Forward Deployed Engineer",
                extra_tags=["resume"],
            )

        assert info["path"] == "Job Search/Resumes/2026-05-06-anthropic-resume.md"
        cmd = run_mock.call_args.args[0]
        assert cmd[0].endswith("oj")  # may be absolute path from shutil.which
        assert "--json" in cmd
        assert "capture" in cmd
        assert "--folder" in cmd
        assert "Job Search/Resumes" in cmd
        assert "--type" in cmd
        assert "resume" in cmd
        # Default tags are present
        tag_idxs = [i for i, v in enumerate(cmd) if v == "--tag"]
        tag_values = [cmd[i + 1] for i in tag_idxs]
        assert "job-search" in tag_values
        assert "beacon" in tag_values
        assert "generated" in tag_values
        assert "resume" in tag_values  # extra_tags
        # Frontmatter extras
        extra_idxs = [i for i, v in enumerate(cmd) if v == "--extra"]
        extra_values = [cmd[i + 1] for i in extra_idxs]
        assert "company=Anthropic" in extra_values
        assert "role=Forward Deployed Engineer" in extra_values
        assert "source=beacon" in extra_values
        # Body is piped via stdin (--body-file -)
        assert "--body-file" in cmd
        assert cmd[cmd.index("--body-file") + 1] == "-"
        # The body was passed as input
        kwargs = run_mock.call_args.kwargs
        assert kwargs["input"] == "# resume body\n"
        assert kwargs["text"] is True

    def test_raises_when_oj_missing(self, monkeypatch):
        monkeypatch.delenv("OJ_BIN", raising=False)
        with patch("beacon.cli.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="oj.*not found"):
                _capture_to_vault(
                    body="x",
                    folder="f",
                    title="t",
                    fm_type="resume",
                    company="c",
                    role="r",
                )

    def test_oj_bin_env_overrides_path_lookup(self):
        fake_proc = MagicMock(returncode=0, stdout='{"path": "x.md"}', stderr="")
        with patch("beacon.cli.shutil.which", return_value=None), \
             patch.dict("os.environ", {"OJ_BIN": "/custom/oj"}, clear=False), \
             patch("beacon.cli.subprocess.run", return_value=fake_proc) as run_mock:
            _capture_to_vault(
                body="x", folder="f", title="t", fm_type="resume",
                company="c", role="r",
            )
        cmd = run_mock.call_args.args[0]
        assert cmd[0] == "/custom/oj"

    def test_raises_on_subprocess_failure(self):
        fake_proc = MagicMock(returncode=1, stdout="", stderr="vault path missing")
        with patch("beacon.cli.shutil.which", return_value="/usr/bin/oj"), \
             patch("beacon.cli.subprocess.run", return_value=fake_proc):
            with pytest.raises(RuntimeError, match="oj capture failed"):
                _capture_to_vault(
                    body="x", folder="f", title="t", fm_type="resume",
                    company="c", role="r",
                )

    def test_raises_on_non_json_output(self):
        fake_proc = MagicMock(returncode=0, stdout="not json", stderr="")
        with patch("beacon.cli.shutil.which", return_value="/usr/bin/oj"), \
             patch("beacon.cli.subprocess.run", return_value=fake_proc):
            with pytest.raises(RuntimeError, match="non-JSON"):
                _capture_to_vault(
                    body="x", folder="f", title="t", fm_type="resume",
                    company="c", role="r",
                )
