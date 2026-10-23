"""Tests for user-built pipelines (beratools.core.pipeline)."""

import json
import os
import subprocess

import pytest

from beratools.core import pipeline


def _steps():
    seeds = pipeline.new_step("check_seed_line", {"in_line": "seeds.gpkg|seed_lines", "out_line": "lines.gpkg|checked"})
    centerline = pipeline.new_step(
        "centerline", {"in_line": "", "out_line": "lines.gpkg|centerline"}, links={"in_line": seeds["id"]}
    )
    return [seeds, centerline]


def test_link_kinds_come_from_beratools_json():
    assert pipeline.linkable_inputs("centerline") == {"in_line": "line"}
    assert pipeline.linkable_inputs("ground_footprint") == {"in_line": "line", "in_footprint": "footprint"}
    assert pipeline.produced_kinds("check_seed_line") == {"line": ("out_line", [])}
    assert set(pipeline.produced_kinds("line_footprint_relative")) == {"footprint", "line"}
    assert pipeline.produced_kinds("tool_template") == {}


def test_every_accepted_kind_has_a_producer():
    tools = pipeline._tool_params()
    produced = {kind for api in tools for kind in pipeline.produced_kinds(api)}
    accepted = {kind for api in tools for kind in pipeline.linkable_inputs(api).values()}
    assert accepted <= produced


def test_link_without_patterns_passes_output_on():
    steps = _steps()
    assert pipeline.resolve_step_args(steps, 1) == {"in_line": "lines.gpkg|checked", "out_line": "lines.gpkg|centerline"}
    # resolving doesn't change the stored step
    assert steps[1]["args"]["in_line"] == ""


def test_file_link_picks_first_matching_pattern_newest_first(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_tool_params", lambda: {
        "maker": [{"variable": "out_folder", "produces": {"dtm": ["Merged_*_DTM.tif", "*_DTM.tif"]}}],
        "user": [{"variable": "in_dtm", "accepts": "dtm"}],
    })
    rasters = tmp_path / "rasters"
    maker = pipeline.new_step("maker", {"out_folder": rasters.as_posix()})
    user = pipeline.new_step("user", links={"in_dtm": maker["id"]})
    steps = [maker, user]

    with pytest.raises(FileNotFoundError, match="Step 1 wrote no file matching"):
        pipeline.resolve_step_args(steps, 1)

    rasters.mkdir()
    (rasters / "tile_TIN_DTM.tif").write_text("")
    (rasters / "Merged_TIN_DSM.tif").write_text("")
    assert pipeline.resolve_step_args(steps, 1)["in_dtm"] == (rasters / "tile_TIN_DTM.tif").as_posix()

    old, new = rasters / "Merged_TIN_DTM.tif", rasters / "Merged_K_DTM.tif"
    old.write_text("")
    new.write_text("")
    os.utime(old, (1, 1))
    assert pipeline.resolve_step_args(steps, 1)["in_dtm"] == new.as_posix()

    assert pipeline.describe_link(steps, user, "in_dtm") == f"{rasters.as_posix()}/Merged_*_DTM.tif"


def test_default_links_pick_latest_matching_step():
    seeds = pipeline.new_step("check_seed_line")
    centerline = pipeline.new_step("centerline")
    footprint = pipeline.new_step("canopy_footprint_absolute")
    relative = pipeline.new_step("line_footprint_relative")
    assert pipeline.default_links([seeds], "centerline") == {"in_line": seeds["id"]}
    assert pipeline.default_links([seeds, centerline, footprint], "ground_footprint") == {
        "in_line": centerline["id"], "in_footprint": footprint["id"]
    }
    assert pipeline.default_links([seeds, relative], "ground_footprint") == {
        "in_line": relative["id"], "in_footprint": relative["id"]
    }
    assert pipeline.default_links([centerline], "tool_template") == {}


def test_relink_follows_step_order():
    seeds = pipeline.new_step("check_seed_line")
    centerline = pipeline.new_step("centerline", links={"in_line": seeds["id"]})
    vertex = pipeline.new_step("vertex_optimization")
    pipeline.relink([seeds, vertex, centerline])
    assert seeds["links"] == {}
    assert vertex["links"] == {"in_line": seeds["id"]}
    assert centerline["links"] == {"in_line": vertex["id"]}

    pipeline.relink([centerline, seeds, vertex])
    assert centerline["links"] == {}
    assert vertex["links"] == {"in_line": seeds["id"]}


def test_validate_pipeline_reports_bad_links():
    assert pipeline.validate_pipeline([]) == ["The pipeline has no steps."]
    assert pipeline.validate_pipeline(_steps()) == []

    seeds, centerline = _steps()
    assert "runs after it" in pipeline.validate_pipeline([centerline, seeds])[0]
    assert "no longer exists" in pipeline.validate_pipeline([centerline])[0]

    seeds["args"]["out_line"] = ""
    assert "no 'out_line' set" in pipeline.validate_pipeline([seeds, centerline])[0]

    seeds, centerline = _steps()
    centerline["links"] = {"out_line": seeds["id"]}
    assert "can't be linked" in pipeline.validate_pipeline([seeds, centerline])[0]

    ground = pipeline.new_step("ground_footprint", links={"in_footprint": seeds["id"]})
    assert "doesn't produce the footprint" in pipeline.validate_pipeline([seeds, ground])[0]


def test_save_and_load_round_trip(tmp_path):
    steps = _steps()
    path = tmp_path / "my_pipeline.json"
    pipeline.save_pipeline(path, steps)

    assert json.loads(path.read_text())["format"] == pipeline.PIPELINE_FORMAT
    assert pipeline.load_pipeline(path) == steps


def test_load_rejects_unknown_format(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"format": 99, "steps": []}))
    with pytest.raises(ValueError, match="Unsupported pipeline format"):
        pipeline.load_pipeline(path)


def test_tool_command_stringifies_args():
    cmd = pipeline.tool_command("centerline", {"in_line": "lines.gpkg|seeds", "line_radius": 15}, 4)
    assert cmd[0].endswith("beratools/tools/centerline.py")
    assert json.loads(cmd[2]) == {"in_line": "lines.gpkg|seeds", "line_radius": "15"}
    assert cmd[3:] == ["-p", "4", "-c", "CLI", "-l", "INFO"]


def test_missing_inputs_skips_linked_and_output_paths(tmp_path):
    seeds, centerline = _steps()
    assert pipeline.missing_inputs([seeds, centerline]) == ["Step 1: Seed Line not found: seeds.gpkg"]

    (tmp_path / "seeds.gpkg").write_text("")
    seeds["args"]["in_line"] = f"{(tmp_path / 'seeds.gpkg').as_posix()}|seed_lines"
    assert pipeline.missing_inputs([seeds, centerline]) == []

    ground = pipeline.new_step(
        "ground_footprint", {"in_footprint": f"{(tmp_path / 'gone.gpkg').as_posix()}|footprint"}
    )
    assert pipeline.missing_inputs([ground]) == [
        f"Step 1: Input Footprint not found: {(tmp_path / 'gone.gpkg').as_posix()}"
    ]


def test_run_pipeline_refuses_missing_inputs(monkeypatch):
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *a, **k: pytest.fail("a step was run"))
    with pytest.raises(ValueError, match="not found: seeds.gpkg"):
        pipeline.run_pipeline(_steps())


def test_run_pipeline_runs_steps_in_order_and_stops_on_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "seeds.gpkg").write_text("")
    calls = []

    def fake_run(cmd, env=None):
        calls.append((cmd[1], json.loads(cmd[3])))
        return subprocess.CompletedProcess(cmd, 0 if len(calls) == 1 else 1)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    steps = _steps() + [pipeline.new_step("tool_template", {"out_feature": "buffered.gpkg|buffer"})]

    with pytest.raises(RuntimeError, match="Step 2"):
        pipeline.run_pipeline(steps)

    assert [c[0].rsplit("/", 1)[1] for c in calls] == ["check_seed_line.py", "centerline.py"]
    assert calls[1][1]["in_line"] == "lines.gpkg|checked"
