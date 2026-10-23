"""
Copyright (C) 2025 Applied Geospatial Research Group.

This script is licensed under the GNU General Public License v3.0.
See <https://gnu.org/licenses/gpl-3.0> for full license details.

Description:
    This script is part of the BERA Tools.
    Webpage: https://github.com/BERATool/beratools

    The purpose of this script is to provide the Pipeline panel: tools are dragged in from the
    tool tree, reordered by dragging, linked to an earlier step's output folder, saved, loaded and run.
"""

from PyQt5 import QtCore, QtGui, QtWidgets

from beratools.core import pipeline

# Drag format used by Qt item views, including the tool tree.
ITEM_MIME = "application/x-qabstractitemmodeldatalist"


def tool_name_from_mime(mime):
    """Text of the item dragged from the tool tree, or None."""
    if not mime.hasFormat(ITEM_MIME):
        return None
    model = QtGui.QStandardItemModel()
    model.dropMimeData(mime, QtCore.Qt.CopyAction, 0, 0, QtCore.QModelIndex())
    item = model.item(0, 0)
    return item.text() if item else None


class PipelineList(QtWidgets.QListWidget):
    """Step list that accepts tools dragged from the tool tree and reorders steps by dragging."""

    tool_dropped = QtCore.pyqtSignal(str, int)  # tool name, row
    step_moved = QtCore.pyqtSignal(int, int)  # from row, to row (before removal)

    def __init__(self, parent=None):
        super(PipelineList, self).__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    def _accepts(self, event):
        return event.source() is self or tool_name_from_mime(event.mimeData()) is not None

    def _drop_row(self, event):
        item = self.itemAt(event.pos())
        return self.row(item) if item else self.count()

    def dragEnterEvent(self, event):
        if self._accepts(event):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepts(event):
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        row = self._drop_row(event)
        # Report a copy so Qt doesn't remove the dragged row; the panel rebuilds the list itself.
        event.setDropAction(QtCore.Qt.CopyAction)
        if event.source() is self:
            event.accept()
            if self.currentRow() >= 0:
                self.step_moved.emit(self.currentRow(), row)
            return

        tool_name = tool_name_from_mime(event.mimeData())
        if tool_name:
            event.accept()
            self.tool_dropped.emit(tool_name, row)
        else:
            event.ignore()


class PipelinePanel(QtWidgets.QWidget):
    """Pipeline builder for the BERA Tools GUI."""

    step_selected = QtCore.pyqtSignal(object)  # step dict, or None when no step is selected
    run_requested = QtCore.pyqtSignal()
    add_requested = QtCore.pyqtSignal()

    def __init__(self, bt_data_obj, parent=None):
        super(PipelinePanel, self).__init__(parent)
        self.bt = bt_data_obj
        self.steps = []

        hint = QtWidgets.QLabel("Drag tools here from Tools available, then drag steps to reorder.")
        hint.setWordWrap(True)

        self.list_widget = PipelineList()

        # one "from step" combo per input of the selected step that can be linked
        self.links_box = QtWidgets.QGroupBox("Inputs from earlier steps")
        self.links_layout = QtWidgets.QFormLayout()
        self.links_box.setLayout(self.links_layout)
        self.link_combos = {}

        style = self.style()
        self.btn_add = self._icon_button(style.SP_FileDialogNewFolder, "Add the selected tool")
        self.btn_up = self._icon_button(style.SP_ArrowUp, "Move step up")
        self.btn_down = self._icon_button(style.SP_ArrowDown, "Move step down")
        self.btn_remove = self._icon_button(style.SP_DialogCloseButton, "Remove selected step")
        self.btn_clear = self._icon_button(style.SP_DialogResetButton, "Remove all steps")
        self.btn_load = self._icon_button(style.SP_DialogOpenButton, "Load pipeline")
        self.btn_save = self._icon_button(style.SP_DialogSaveButton, "Save pipeline")
        self.btn_run = QtWidgets.QPushButton("Run Pipeline")

        btn_layout = QtWidgets.QHBoxLayout()
        for btn in (self.btn_add, self.btn_up, self.btn_down, self.btn_remove, self.btn_clear):
            btn_layout.addWidget(btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_save)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(hint)
        layout.addLayout(btn_layout)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.links_box)
        layout.addWidget(self.btn_run)

        # scroll the content when it doesn't fit, rather than resizing the panel
        content = QtWidgets.QWidget()
        content.setLayout(layout)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setWidget(content)
        outer_layout = QtWidgets.QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)

        self.list_widget.tool_dropped.connect(self.add_tool)
        self.list_widget.step_moved.connect(self.move_step)
        self.list_widget.currentRowChanged.connect(self.row_changed)
        self.btn_add.clicked.connect(self.add_requested)
        self.btn_up.clicked.connect(lambda: self.move_step(self.list_widget.currentRow(), self.list_widget.currentRow() - 1))
        self.btn_down.clicked.connect(lambda: self.move_step(self.list_widget.currentRow(), self.list_widget.currentRow() + 2))
        self.btn_remove.clicked.connect(self.remove_step)
        self.btn_clear.clicked.connect(self.clear_steps)
        self.btn_load.clicked.connect(self.load)
        self.btn_save.clicked.connect(self.save)
        self.btn_run.clicked.connect(self.run_requested)

        self.refresh()

    @staticmethod
    def _icon_button(icon, tooltip):
        btn = QtWidgets.QPushButton()
        btn.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        btn.setToolTip(tooltip)
        btn.setFixedWidth(40)
        return btn

    def param_label(self, tool_api, variable):
        tool_name = self.bt.get_bera_tool_name(tool_api)
        for param in self.bt.get_bera_tool_args(tool_name):
            if param.get("variable") == variable:
                return param["name"]
        return variable

    def step_label(self, step):
        return self.bt.get_bera_tool_name(step["tool_api"])

    def current_step(self):
        row = self.list_widget.currentRow()
        return self.steps[row] if 0 <= row < len(self.steps) else None

    def refresh(self, select_row=None):
        """Rebuild the list from self.steps and select a row (the current one by default)."""
        if select_row is None:
            select_row = self.list_widget.currentRow()
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for n, step in enumerate(self.steps, 1):
            text = f"{n}. {self.step_label(step)}"
            sources = sorted(
                i + 1 for i in (pipeline.step_index(self.steps, s) for s in set(step["links"].values()))
                if i is not None
            )
            if sources:
                text += f"   ← step{'s' if len(sources) > 1 else ''} {', '.join(map(str, sources))}"
            self.list_widget.addItem(text)
        select_row = min(select_row, len(self.steps) - 1)
        self.list_widget.setCurrentRow(select_row)
        self.list_widget.blockSignals(False)
        self.row_changed(select_row)

    def row_changed(self, row):
        step = self.steps[row] if 0 <= row < len(self.steps) else None
        has_step = step is not None
        self.btn_up.setEnabled(has_step and row > 0)
        self.btn_down.setEnabled(has_step and row < len(self.steps) - 1)
        self.btn_remove.setEnabled(has_step)
        self.btn_clear.setEnabled(bool(self.steps))
        self.btn_save.setEnabled(bool(self.steps))
        self.btn_run.setEnabled(bool(self.steps))
        self._update_link_combos(step, row)
        self.step_selected.emit(step)

    def _update_link_combos(self, step, row):
        while self.links_layout.rowCount():
            self.links_layout.removeRow(0)
        self.link_combos = {}

        inputs = pipeline.linkable_inputs(step["tool_api"]) if step else {}
        self.links_box.setVisible(bool(inputs))
        for variable, kind in inputs.items():
            combo = QtWidgets.QComboBox()
            # don't widen the panel to fit long step names
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(10)
            combo.addItem("Its own value", None)
            for earlier in pipeline.link_sources(self.steps[:row], kind):
                n = pipeline.step_index(self.steps, earlier["id"]) + 1
                combo.addItem(f"Step {n}: {self.step_label(earlier)}", earlier["id"])
            combo.setCurrentIndex(max(combo.findData(step["links"].get(variable)), 0))
            combo.setToolTip(f"Read this input ({kind}) from an earlier step's output")
            combo.activated.connect(lambda index, v=variable: self.link_changed(v, index))
            self.links_layout.addRow(self.param_label(step["tool_api"], variable), combo)
            self.link_combos[variable] = combo

    def link_changed(self, variable, index):
        step = self.current_step()
        if step is None:
            return
        source_id = self.link_combos[variable].itemData(index)
        if source_id is None:
            step["links"].pop(variable, None)
        else:
            step["links"][variable] = source_id
        # rebuild after this combo's signal returns, since refreshing deletes the combo
        QtCore.QTimer.singleShot(0, self.refresh)

    def add_tool(self, tool_name, row=None):
        tool_api = self.bt.get_bera_tool_api(tool_name)
        if tool_api is None:  # a category was dropped
            return
        if row is None or row > len(self.steps):
            row = len(self.steps)
        self.steps.insert(row, pipeline.new_step(tool_api))
        pipeline.relink(self.steps)
        self.refresh(row)

    def move_step(self, from_row, to_row):
        if not 0 <= from_row < len(self.steps) or to_row < 0:
            return
        step = self.steps.pop(from_row)
        if to_row > from_row:
            to_row -= 1
        to_row = min(to_row, len(self.steps))
        self.steps.insert(to_row, step)
        pipeline.relink(self.steps)
        self.refresh(to_row)

    def remove_step(self):
        row = self.list_widget.currentRow()
        if not 0 <= row < len(self.steps):
            return
        self.steps.pop(row)
        pipeline.relink(self.steps)
        self.refresh(row)

    def clear_steps(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear pipeline",
            f"Remove all {len(self.steps)} steps from the pipeline?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.steps = []
            self.refresh(-1)

    def set_steps(self, steps):
        self.steps = steps
        self.refresh(0 if steps else -1)

    def save(self):
        start_dir = self.bt.get_last_browse_dir() or ""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save pipeline", start_dir, "Pipeline (*.json)")
        if path:
            pipeline.save_pipeline(path, self.steps)

    def load(self):
        start_dir = self.bt.get_last_browse_dir() or ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load pipeline", start_dir, "Pipeline (*.json)")
        if not path:
            return
        try:
            steps = pipeline.load_pipeline(path)
        except (OSError, ValueError, KeyError) as err:
            QtWidgets.QMessageBox.warning(self, "Load pipeline", f"Could not load {path}:\n{err}")
            return

        unknown = [s["tool_api"] for s in steps if self.bt.get_bera_tool_name(s["tool_api"]) is None]
        if unknown:
            QtWidgets.QMessageBox.warning(self, "Load pipeline", f"Unknown tools in {path}: {', '.join(unknown)}")
            return
        self.set_steps(steps)

    def set_running(self, running):
        for widget in (self.list_widget, self.links_box, self.btn_add, self.btn_load, self.btn_run):
            widget.setEnabled(not running)
        if running:
            for btn in (self.btn_up, self.btn_down, self.btn_remove, self.btn_clear, self.btn_save):
                btn.setEnabled(False)
        else:
            self.refresh()
