"""Run release guards in a disposable Git repo; requires PyYAML, Bash, and pwsh.

Run: python tests/check_publish_workflows.py
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml


def check():
    root = Path(__file__).resolve().parents[1]
    workflows = {}
    for filename, job in (("publish_to_pypi.yml", "pypi"), ("build-win-installer.yml", "build")):
        workflow = yaml.load((root / ".github/workflows" / filename).read_text(), Loader=yaml.BaseLoader)
        assert set(workflow["on"]) == {"workflow_dispatch"}
        if filename.startswith("build-win"):
            assert workflow["on"]["workflow_dispatch"]["inputs"]["skip_signing"]["default"] == "true"
        workflows[filename] = workflow["jobs"][job]["steps"]

    bash = shutil.which("bash")
    if os.name == "nt":
        git_bash = Path(shutil.which("git")).parent.parent / "bin/bash.exe"
        if git_bash.is_file():
            bash = str(git_bash)
    pwsh = shutil.which("pwsh")
    assert bash and pwsh, "Install Bash and PowerShell 7 to run the workflow checks"

    with tempfile.TemporaryDirectory(prefix="publish-check-") as directory:
        repo = Path(directory)

        def git(*args):
            return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()

        git("init", "-b", "main")
        git("remote", "add", "origin", str(repo))
        for version in ("1.0.0", "1.0.1"):
            (repo / "version.txt").write_text(version)
            git("add", "version.txt")
            git("-c", "user.name=Workflow Check", "-c", "user.email=check@example.invalid",
                "commit", "-m", version)
            git("tag", version)
        sha = git("rev-parse", "HEAD")
        # A newer tag on the same commit distinguishes the latest-tag check
        # from the exact-commit check.
        git("tag", "1.0.2")

        cases = (
            ("", "refs/heads/test", "dry"),
            ("1.0.2", "refs/heads/main", "publish"),
            ("1.0.2", "refs/heads/test", "ineligible"),
            ("1.0.1", "refs/heads/main", "ineligible"),
            ("1.0.0", "refs/heads/main", "ineligible"),
            ("9.9.9", "refs/heads/main", "invalid"),
            ("1.0.2; echo unexpected", "refs/heads/main", "invalid"),
        )
        for filename, steps in workflows.items():
            guard = next(step for step in steps if step.get("id") in ("tag_guard", "signing"))
            for tag, ref, mode in cases:
                # Each run starts at the dispatched commit, including after checkout.
                git("checkout", "--quiet", "--detach", sha)
                output = repo / "github-output"
                env_file = repo / "github-env"
                output.write_text("")
                env_file.write_text("")
                env = dict(os.environ, GITHUB_SHA=sha, GITHUB_REF=ref,
                           GITHUB_OUTPUT=output.as_posix(), GITHUB_ENV=env_file.as_posix(),
                           GITHUB_STEP_SUMMARY=(repo / "summary").as_posix(),
                           INPUT_RELEASE_TAG=tag, RELEASE_TAG=tag)
                command = ([pwsh, "-NoProfile", "-NonInteractive", "-Command"]
                           if filename.startswith("build-win") else [bash, "-c"])
                result = subprocess.run([*command, guard["run"]], cwd=repo, env=env,
                                        text=True, capture_output=True)
                invalid = mode == "invalid" or (filename.startswith("build-win") and mode == "ineligible")
                assert (result.returncode != 0) == invalid, (filename, tag, ref, result.stdout, result.stderr)
                if not invalid:
                    values = dict(
                        line.split("=", 1) for line in output.read_text(encoding="utf-8-sig").splitlines()
                    )
                    key = "publish_release" if filename.startswith("build-win") else "publish"
                    assert values[key] == str(mode == "publish").lower(), (filename, tag, ref, values)
                    if key == "publish" and mode == "publish":
                        assert env_file.read_text().strip() == f"SETUPTOOLS_SCM_PRETEND_VERSION={tag}"

        label = next(
            step for step in workflows["build-win-installer.yml"]
            if step["name"] == "Label unsigned installer"
        )
        dist = repo / "packaging/dist"
        dist.mkdir(parents=True)
        (dist / "beratools-installer-1.0.2.exe").write_bytes(b"unsigned check artifact")
        subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", label["run"]],
                       cwd=repo, env=dict(os.environ, INSTALLER_VERSION="1.0.2"), check=True)
        assert (dist / "beratools-installer-1.0.2-unsigned.exe").read_bytes() == b"unsigned check artifact"
        assert not (dist / "beratools-installer-1.0.2.exe").exists()

    print("Publishing guards passed (14 scenarios); unsigned installer labeling passed.")


if __name__ == "__main__":
    check()
