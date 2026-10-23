"""
Pipeline panel tests using pytest-qt.

Tests dragging tools into the pipeline, linking, reordering, editing a step in the tool form,
saving/loading, and running the steps one after another.
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt5 import QtCore, QtWidgets

from beratools.gui.pipeline_panel import tool_name_from_mime

pytestmark = pytest.mark.gui_qt

SEEDS = "Check Seed Lines"
VERTEX = "Vertex Optimization"
CENTERLINE = "Centerline"
FOOTPRINT = "Canopy Footprint (Absolute Threshold)"
GROUND = "Ground Footprint"
BUFFER = "Feature Buffer"


@pytest.fixture
def panel(main_window):
    main_window.left_tabs.setCurrentWidget(main_window.pipeline_panel)
    return main_window.pipeline_panel


def _labels(panel):
    return [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]


def test_tool_tree_drag_carries_tool_name(main_window):
    tree = main_window.tree_view
    index = tree.tags_model.mapFromSource(tree.get_tool_index(CENTERLINE))
    mime = tree.tags_model.mimeData([index])
    assert tool_name_from_mime(mime) == CENTERLINE


def test_added_tool_links_to_line_step(panel):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.add_tool(BUFFER)

    assert _labels(panel) == [f"1. {SEEDS}", f"2. {CENTERLINE}   \u2190 step 1", f"3. {BUFFER}"]
    assert panel.steps[1]["links"] == {"in_line": panel.steps[0]["id"]}


def test_inputs_link_to_matching_steps(panel):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.add_tool(FOOTPRINT)
    panel.add_tool(GROUND)

    seeds, centerline, footprint, ground = panel.steps
    assert ground["links"] == {"in_line": centerline["id"], "in_footprint": footprint["id"]}
    assert _labels(panel)[3] == f"4. {GROUND}   \u2190 steps 2, 3"
    # only steps that produce a footprint are offered for in_footprint
    combo = panel.link_combos["in_footprint"]
    assert [combo.itemData(i) for i in range(combo.count())] == [None, footprint["id"]]
    assert set(panel.link_combos) == {"in_line", "in_footprint"}


def test_category_drop_is_ignored(panel):
    panel.add_tool("Mapping")
    assert panel.steps == []


def test_move_and_remove_steps(panel):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.add_tool(BUFFER)

    panel.move_step(2, 0)
    assert [s["tool_api"] for s in panel.steps] == ["tool_template", "check_seed_line", "centerline"]

    panel.list_widget.setCurrentRow(1)
    panel.remove_step()
    assert [s["tool_api"] for s in panel.steps] == ["tool_template", "centerline"]
    # links to the removed step are dropped
    assert all(s["links"] == {} for s in panel.steps)


def test_remove_relinks_to_earlier_step(panel):
    panel.add_tool(SEEDS)
    panel.add_tool(VERTEX)
    panel.add_tool(CENTERLINE)
    assert panel.steps[2]["links"] == {"in_line": panel.steps[1]["id"]}

    panel.list_widget.setCurrentRow(1)
    panel.remove_step()
    assert panel.steps[1]["links"] == {"in_line": panel.steps[0]["id"]}


def test_insert_and_move_relink_steps(panel):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.add_tool(BUFFER, row=1)  # doesn't produce lines, so the centerline still reads the seeds
    seeds, buffer, centerline = panel.steps
    assert centerline["links"] == {"in_line": seeds["id"]}

    panel.add_tool(VERTEX, row=1)  # the centerline now reads the optimized lines
    vertex = panel.steps[1]
    assert vertex["links"] == {"in_line": seeds["id"]}
    assert buffer["links"] == {}
    assert centerline["links"] == {"in_line": vertex["id"]}

    panel.move_step(1, 4)  # vertex optimization last: the centerline reads the seeds again
    assert [s["tool_api"] for s in panel.steps] == ["check_seed_line", "tool_template", "centerline", "vertex_optimization"]
    assert centerline["links"] == {"in_line": seeds["id"]}
    assert vertex["links"] == {"in_line": centerline["id"]}


def test_link_combo_unlinks_step(panel, qtbot):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)

    combo = panel.link_combos["in_line"]
    assert combo.currentData() == panel.steps[0]["id"]
    panel.link_changed("in_line", combo.findData(None))
    assert panel.steps[1]["links"] == {}
    qtbot.waitUntil(lambda: _labels(panel)[1] == f"2. {CENTERLINE}")


def test_selected_step_edits_are_stored(main_window, panel):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.steps[0]["args"]["out_line"] = "D:/lines.gpkg|checked"
    panel.list_widget.setCurrentRow(0)
    panel.list_widget.setCurrentRow(1)

    assert main_window.pipeline_step is panel.steps[1]
    assert main_window.btn_layout_top.itemAt(0).widget().text() == f"Step 2: {CENTERLINE}"
    in_widget = main_window.tool_widget.widgets_by_variable["in_line"]
    assert not in_widget.isEnabled()
    assert in_widget.in_file.placeholderText() == "D:/lines.gpkg|checked"

    main_window.tool_widget.widgets_by_variable["line_radius"].data_input.setValue(25)
    assert float(panel.steps[1]["args"]["line_radius"]) == 25

    # choosing a tool from the tree stops editing the step
    main_window.set_tool(BUFFER)
    assert main_window.pipeline_step is None
    assert float(panel.steps[1]["args"]["line_radius"]) == 25


def test_clicking_selected_tool_leaves_step(main_window, panel):
    main_window.set_tool(BUFFER)
    panel.add_tool(SEEDS)
    assert main_window.pipeline_step is panel.steps[0]

    # the tool is still selected in the tree, so only the click tells the window to show it
    tree = main_window.tree_view
    tree.tree_item_clicked(tree.tags_model.mapFromSource(tree.get_tool_index(BUFFER)))
    assert main_window.pipeline_step is None
    assert main_window.btn_layout_top.itemAt(0).widget().text() == BUFFER


def test_clicking_history_tool_leaves_step(main_window, panel):
    main_window.set_tool(BUFFER)
    panel.add_tool(SEEDS)
    assert main_window.pipeline_step is panel.steps[0]

    history = main_window.tool_history
    history.set_data_list([BUFFER])
    history.item_clicked(history.list_model.index(0, 0))
    assert main_window.pipeline_step is None
    assert main_window.btn_layout_top.itemAt(0).widget().text() == BUFFER


def test_tool_values_kept_while_editing_steps(main_window, panel):
    main_window.set_tool(CENTERLINE)
    main_window.tool_widget.widgets_by_variable["line_radius"].data_input.setValue(30)
    panel.add_tool(CENTERLINE)
    main_window.tool_widget.widgets_by_variable["line_radius"].data_input.setValue(40)

    main_window.set_tool(CENTERLINE)
    assert main_window.tool_widget.widgets_by_variable["line_radius"].data_input.value() == 30
    assert float(panel.steps[0]["args"]["line_radius"]) == 40


def test_switching_tabs_switches_between_tool_and_step(main_window, panel):
    main_window.set_tool(BUFFER)
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.list_widget.setCurrentRow(0)

    main_window.left_tabs.setCurrentWidget(main_window.tool_history)
    assert main_window.pipeline_step is None
    assert main_window.btn_layout_top.itemAt(0).widget().text() == BUFFER

    main_window.left_tabs.setCurrentWidget(panel)
    assert main_window.pipeline_step is panel.steps[0]
    assert main_window.btn_layout_top.itemAt(0).widget().text() == f"Step 1: {SEEDS}"


def test_removing_last_step_shows_tool_again(main_window, panel):
    main_window.set_tool(BUFFER)
    panel.add_tool(SEEDS)
    panel.remove_step()
    assert main_window.pipeline_step is None
    assert main_window.btn_layout_top.itemAt(0).widget().text() == BUFFER


def test_linked_footprint_input_shows_source_output(main_window, panel):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.add_tool(FOOTPRINT)
    panel.add_tool(GROUND)
    panel.steps[2]["args"]["out_footprint"] = "D:/footprint.gpkg|footprint"
    panel.list_widget.setCurrentRow(0)
    panel.list_widget.setCurrentRow(3)

    footprint_widget = main_window.tool_widget.widgets_by_variable["in_footprint"]
    assert not footprint_widget.isEnabled()
    assert footprint_widget.in_file.placeholderText() == "D:/footprint.gpkg|footprint"


def test_save_and_load(panel, tmp_path):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    path = (tmp_path / "p.json").as_posix()

    with patch("PyQt5.QtWidgets.QFileDialog.getSaveFileName", return_value=(path, "")):
        panel.save()
    saved = [dict(s) for s in panel.steps]

    panel.steps = []
    with patch("PyQt5.QtWidgets.QFileDialog.getOpenFileName", return_value=(path, "")):
        panel.load()
    assert panel.steps == saved
    assert panel.list_widget.currentRow() == 0


def test_clear_asks_first(panel):
    panel.add_tool(SEEDS)
    no = QtWidgets.QMessageBox.StandardButton.No
    with patch("PyQt5.QtWidgets.QMessageBox.question", return_value=no):
        panel.clear_steps()
    assert len(panel.steps) == 1

    yes = QtWidgets.QMessageBox.StandardButton.Yes
    with patch("PyQt5.QtWidgets.QMessageBox.question", return_value=yes):
        panel.clear_steps()
    assert panel.steps == []


def test_invalid_pipeline_is_not_run(main_window, panel):
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.steps[0]["args"]["out_line"] = ""

    with patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warning, \
            patch.object(main_window, "_launch_tool") as mock_launch:
        main_window.run_pipeline()
    assert "no 'out_line' set" in mock_warning.call_args[0][2]
    mock_launch.assert_not_called()


def test_pipeline_with_missing_input_is_not_run(main_window, panel, tmp_path):
    panel.add_tool(SEEDS)
    missing = (tmp_path / "gone.gpkg").as_posix()
    panel.steps[0]["args"].update(in_line=f"{missing}|seed_lines", out_line=f"{(tmp_path / 'out.gpkg').as_posix()}|checked")

    with patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warning, \
            patch.object(main_window, "_launch_tool") as mock_launch:
        main_window.run_pipeline()
    assert f"Step 1: Seed Line not found: {missing}" in mock_warning.call_args[0][2]
    mock_launch.assert_not_called()


def _finish(main_window, exit_code):
    process = MagicMock()
    process.readAllStandardOutput.return_value = b""
    process.readAllStandardError.return_value = b""
    process.exitStatus.return_value = QtCore.QProcess.NormalExit
    process.exitCode.return_value = exit_code
    main_window.process = process
    main_window.process_finished()


def _seeds_and_centerline(panel, tmp_path):
    seeds_file = tmp_path / "seeds.gpkg"
    seeds_file.write_text("")
    panel.add_tool(SEEDS)
    panel.add_tool(CENTERLINE)
    panel.steps[0]["args"].update(in_line=f"{seeds_file.as_posix()}|seed_lines", out_line="D:/lines.gpkg|checked")
    panel.steps[1]["args"]["out_line"] = "D:/lines.gpkg|centerline"


def test_pipeline_runs_steps_in_order(main_window, panel, qtbot, tmp_path):
    _seeds_and_centerline(panel, tmp_path)

    with patch.object(main_window, "_launch_tool") as mock_launch:
        main_window.run_pipeline()
        assert mock_launch.call_count == 1
        assert mock_launch.call_args[0][1] == "check_seed_line"
        assert not panel.btn_run.isEnabled()

        _finish(main_window, 0)
        qtbot.waitUntil(lambda: mock_launch.call_count == 2, timeout=2000)
        assert mock_launch.call_args[0][1] == "centerline"
        assert mock_launch.call_args[0][2]["in_line"] == "D:/lines.gpkg|checked"

        _finish(main_window, 0)

    assert main_window.pipeline_run is None
    assert panel.btn_run.isEnabled()
    assert "Pipeline completed." in main_window.text_edit.toPlainText()


def test_pipeline_stops_when_a_step_fails(main_window, panel, tmp_path):
    _seeds_and_centerline(panel, tmp_path)

    with patch.object(main_window, "_launch_tool") as mock_launch:
        main_window.run_pipeline()
        _finish(main_window, 1)

    assert mock_launch.call_count == 1
    assert main_window.pipeline_run is None
    assert "Pipeline stopped: step 1 failed." in main_window.text_edit.toPlainText()


def test_pipeline_stops_when_linked_input_cannot_be_resolved(main_window, panel, qtbot, tmp_path):
    _seeds_and_centerline(panel, tmp_path)
    resolve = main_window.__class__.__module__ + ".pipeline.resolve_step_args"

    with patch.object(main_window, "_launch_tool") as mock_launch:
        main_window.run_pipeline()
        with patch(resolve, side_effect=FileNotFoundError("Step 1 wrote no file matching *.gpkg")):
            _finish(main_window, 0)
            qtbot.waitUntil(lambda: main_window.pipeline_run is None, timeout=2000)

    assert mock_launch.call_count == 1
    assert "Pipeline stopped before step 2: Step 1 wrote no file matching" in main_window.text_edit.toPlainText()
