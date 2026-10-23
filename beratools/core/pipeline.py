"""
Copyright (C) 2025 Applied Geospatial Research Group.

This script is licensed under the GNU General Public License v3.0.
See <https://gnu.org/licenses/gpl-3.0> for full license details.

Description:
    This script is part of the BERA Tools.
    Webpage: https://github.com/BERATool/beratools

    The purpose of this script is to provide user-built pipelines: an ordered list of tool steps,
    saved as JSON and run one after another. A step's input can be linked to an earlier step's
    output, so the pipeline can be rerun on other data by changing only the first step's input.

    Which inputs can be linked to which outputs comes from beratools.json, so a new tool takes part
    in pipelines without changes here:
      - an input parameter with "accepts": "<kind>" can be linked;
      - an output parameter with "produces": {"<kind>": [patterns]} provides that kind. An empty
        list means the output itself (e.g. a vector file|layer); otherwise the first
        pattern that matches files in the output folder is used, newest file first.

Usage:
    python -m beratools.core.pipeline my_pipeline.json [--processes 4]
"""

import argparse
import functools
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

PIPELINE_FORMAT = 2
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
TOOLS_JSON = Path(__file__).resolve().parents[1] / "gui" / "assets" / "beratools.json"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


@functools.lru_cache(maxsize=None)
def _tool_params():
    with open(TOOLS_JSON, "r") as tool_json_file:
        bera_tools = json.load(tool_json_file)
    return {
        tool["tool_api"]: tool.get("parameters", [])
        for toolbox in bera_tools["toolbox"]
        for tool in toolbox["tools"]
    }


def linkable_inputs(tool_api):
    """{input variable: kind} for the tool's inputs that can come from an earlier step."""
    return {p["variable"]: p["accepts"] for p in _tool_params().get(tool_api, []) if p.get("accepts")}


def produced_kinds(tool_api):
    """{kind: (output variable, file patterns)} for what the tool writes."""
    kinds = {}
    for p in _tool_params().get(tool_api, []):
        for kind, patterns in p.get("produces", {}).items():
            kinds[kind] = (p["variable"], patterns)
    return kinds


def new_step(tool_api, args=None, links=None, step_id=None):
    return {
        "id": step_id or uuid.uuid4().hex[:8],
        "tool_api": tool_api,
        "args": dict(args or {}),
        "links": dict(links or {}),
    }


def step_index(steps, step_id):
    for i, step in enumerate(steps):
        if step["id"] == step_id:
            return i
    return None


def link_sources(steps, kind):
    """Steps (from the given list) that produce kind."""
    return [step for step in steps if kind in produced_kinds(step["tool_api"])]


def default_links(steps, tool_api):
    """Link each of the tool's linkable inputs to the latest step (from steps) that produces its kind."""
    links = {}
    for variable, kind in linkable_inputs(tool_api).items():
        sources = link_sources(steps, kind)
        if sources:
            links[variable] = sources[-1]["id"]
    return links


def relink(steps):
    """Reset every step's links to the defaults for its place in the list.

    Called after adding, moving or removing a step.
    """
    for i, step in enumerate(steps):
        step["links"] = default_links(steps[:i], step["tool_api"])


def validate_pipeline(steps):
    """Return a list of problems with the step links; empty when the pipeline can run."""
    errors = []
    if not steps:
        errors.append("The pipeline has no steps.")
    for n, step in enumerate(steps, 1):
        accepts = linkable_inputs(step["tool_api"])
        for variable, source_id in step["links"].items():
            i = step_index(steps, source_id)
            if variable not in accepts:
                errors.append(f"Step {n}: '{variable}' can't be linked to another step.")
            elif i is None:
                errors.append(f"Step {n}: the step '{variable}' reads from no longer exists.")
            elif i >= n - 1:
                errors.append(f"Step {n}: '{variable}' reads the output of step {i + 1}, which runs after it.")
            elif accepts[variable] not in produced_kinds(steps[i]["tool_api"]):
                errors.append(f"Step {n}: step {i + 1} doesn't produce the {accepts[variable]} that '{variable}' needs.")
            else:
                out_variable, _ = produced_kinds(steps[i]["tool_api"])[accepts[variable]]
                if not steps[i]["args"].get(out_variable):
                    errors.append(f"Step {n}: step {i + 1} has no '{out_variable}' set.")
    return errors


def missing_inputs(steps):
    """Return a problem for each input file or folder a step reads that doesn't exist.

    Linked inputs are skipped, since an earlier step writes them while the pipeline runs.
    """
    errors = []
    for n, step in enumerate(steps, 1):
        for p in _tool_params().get(step["tool_api"], []):
            variable = p.get("variable")
            if p.get("type") not in ("file", "directory") or p.get("output") or variable in step["links"]:
                continue
            value = step["args"].get(variable)
            if not value or not isinstance(value, str):
                continue
            path = value.rsplit("|", 1)[0]  # vector inputs are stored as path|layer
            if not Path(path).exists():
                label = p.get("label", variable).rstrip(".")
                errors.append(f"Step {n}: {label} not found: {path}")
    return errors


def describe_link(steps, step, variable):
    """What a linked input will read, e.g. 'D:/rasters/Merged_*_DTM.tif', for showing in the GUI."""
    source = steps[step_index(steps, step["links"][variable])]
    out_variable, patterns = produced_kinds(source["tool_api"])[linkable_inputs(step["tool_api"])[variable]]
    folder = source["args"].get(out_variable, "")
    return Path(folder, patterns[0]).as_posix() if patterns and folder else folder


def resolve_link(steps, step, variable):
    """The path a linked input reads; call it after the source step has run."""
    source_index = step_index(steps, step["links"][variable])
    source = steps[source_index]
    out_variable, patterns = produced_kinds(source["tool_api"])[linkable_inputs(step["tool_api"])[variable]]
    folder = source["args"][out_variable]
    if not patterns:
        return folder

    for pattern in patterns:
        matches = sorted(Path(folder).glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
        if matches:
            return matches[0].as_posix()
    raise FileNotFoundError(
        f"Step {source_index + 1} wrote no file matching {' or '.join(patterns)} in {folder} for '{variable}'"
    )


def resolve_step_args(steps, index):
    """Step arguments with the linked inputs filled in from the earlier steps' outputs."""
    step = steps[index]
    args = dict(step["args"])
    for variable in step["links"]:
        args[variable] = resolve_link(steps, step, variable)
    return args


def stringify_args(args):
    # Same conversion as the GUI's Run button: the tools validate and convert string values.
    return {key: value if isinstance(value, str) else str(value) for key, value in args.items()}


def save_pipeline(path, steps):
    with open(path, "w") as pipeline_file:
        json.dump({"format": PIPELINE_FORMAT, "steps": steps}, pipeline_file, indent=4)


def load_pipeline(path):
    with open(path, "r") as pipeline_file:
        data = json.load(pipeline_file)
    file_format = data.get("format")
    if file_format != PIPELINE_FORMAT:
        raise ValueError(f"Unsupported pipeline format: {file_format}")

    return [new_step(s["tool_api"], s.get("args"), s.get("links"), s.get("id")) for s in data.get("steps", [])]


def tool_command(tool_api, args, processes, call_mode="CLI"):
    """Arguments to run one tool script in its own process, as the GUI does."""
    return [
        (TOOLS_DIR / f"{tool_api}.py").as_posix(),
        "-i", json.dumps(stringify_args(args)),
        "-p", str(processes),
        "-c", call_mode,
        "-l", "INFO",
    ]  # fmt: skip


def run_pipeline(steps, processes=0):
    errors = validate_pipeline(steps) + missing_inputs(steps)
    if errors:
        raise ValueError("\n".join(errors))

    # the tool scripts import beratools, which may be run from a source checkout rather than installed
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [PACKAGE_ROOT.as_posix(), env.get("PYTHONPATH")]))

    for i, step in enumerate(steps):
        print("\n" + "-" * 50)
        print(f"Step {i + 1}/{len(steps)}: {step['tool_api']}")
        print("-" * 50, flush=True)
        args = resolve_step_args(steps, i)
        result = subprocess.run([sys.executable] + tool_command(step["tool_api"], args, processes), env=env)
        if result.returncode != 0:
            raise RuntimeError(f"Step {i + 1} ({step['tool_api']}) failed with exit code {result.returncode}")


def main():
    parser = argparse.ArgumentParser(description="Run a pipeline saved from the BERA Tools GUI.")
    parser.add_argument("pipeline_file", help="pipeline .json file")
    parser.add_argument("--processes", type=int, default=0, help="worker count (0 = all CPU cores)")
    args = parser.parse_args()

    start_time = time.time()
    run_pipeline(load_pipeline(args.pipeline_file), args.processes)
    print(f"Pipeline done in {round(time.time() - start_time, 1)} seconds")


if __name__ == "__main__":
    main()
