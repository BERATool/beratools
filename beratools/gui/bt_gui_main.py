"""
Copyright (C) 2025 Applied Geospatial Research Group.

This script is licensed under the GNU General Public License v3.0.
See <https://gnu.org/licenses/gpl-3.0> for full license details.

Author: Richard Zeng

Description:
    This script is part of the BERA Tools.
    Webpage: https://github.com/BERATool/beratools

    The purpose of this script is to provide main GUI functions.
"""

import copy
import json
import os
import platform
import shlex
import signal
import sys
import webbrowser
from pathlib import Path

import beratools.core.constants as bt_const
from beratools.core import pipeline
from beratools.gui import bt_data
from beratools.gui.pipeline_panel import PipelinePanel
from beratools.utility import env_checks
from beratools.gui.tool_widgets import ToolWidgets

from PyQt5 import QtCore, QtGui, QtWidgets

bt = bt_data.BTData()


def extract_string_from_printout(str_print, str_extract):
    str_array = shlex.split(str_print)  # keep string in double quotes
    str_array_enum = enumerate(str_array)
    index = 0
    for item in str_array_enum:
        if str_extract in item[1]:
            index = item[0]
            break
    str_out = str_array[index]
    return str_out.strip()


class _SearchProxyModel(QtCore.QSortFilterProxyModel):
    def setFilterRegExp(self, pattern):
        if isinstance(pattern, str):
            pattern = QtCore.QRegExp(pattern, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.FixedString)
        super(_SearchProxyModel, self).setFilterRegExp(pattern)

    def _accept_index(self, idx):
        if idx.isValid():
            text = idx.data(QtCore.Qt.DisplayRole)
            if self.filterRegExp().indexIn(text) >= 0:
                return True
            for row in range(idx.model().rowCount(idx)):
                if self._accept_index(idx.model().index(row, 0, idx)):
                    return True
        return False

    def filterAcceptsRow(self, sourceRow, sourceParent):
        idx = self.sourceModel().index(sourceRow, 0, sourceParent)
        return self._accept_index(idx)


class BTTreeView(QtWidgets.QWidget):
    """Tree view for BERA Tools GUI."""

    tool_changed = QtCore.pyqtSignal(str)  # tool selection changed

    def __init__(self, parent=None):
        super(BTTreeView, self).__init__(parent)

        # controls
        self.tool_search = QtWidgets.QLineEdit()
        self.tool_search.setPlaceholderText("Search...")

        self.tags_model = _SearchProxyModel()
        self.tree_model = QtGui.QStandardItemModel()
        self.tags_model.setSourceModel(self.tree_model)
        # self.tags_model.setDynamicSortFilter(True)
        self.tags_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.tree_view = QtWidgets.QTreeView()
        self.tree_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setRootIsDecorated(True)
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setModel(self.tags_model)
        # tools can be dragged into the Pipeline panel
        self.tree_view.setDragEnabled(True)
        self.tree_view.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

        # layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.tool_search)
        main_layout.addWidget(self.tree_view)
        self.setLayout(main_layout)

        # signals
        self.tool_search.textChanged.connect(self.search_text_changed)

        # init
        first_child = self.create_model()

        self.tree_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tree_view.setFirstColumnSpanned(0, self.tree_view.rootIndex(), True)
        self.tree_view.setUniformRowHeights(True)

        self.tree_model.setHorizontalHeaderLabels(["Tools"])
        self.tree_sel_model = self.tree_view.selectionModel()
        self.tree_sel_model.selectionChanged.connect(self.tree_view_selection_changed)
        # clicking the already selected tool doesn't change the selection, but should still show it
        # (e.g. after a pipeline step replaced it in the tool form)
        self.tree_view.clicked.connect(self.tree_item_clicked)

        # always start on the first tool in the list
        if first_child is not None:
            self.select_tool_by_index(self.tree_model.indexFromItem(first_child))
        self.tree_view.collapsed.connect(self.tree_item_collapsed)
        self.tree_view.expanded.connect(self.tree_item_expanded)

    def create_model(self):
        first_child = self.add_tool_list_to_tree(bt.toolbox_list, bt.sorted_tools)

        return first_child

    def search_text_changed(self, text=None):
        self.tags_model.setFilterRegExp(self.tool_search.text())

        if len(self.tool_search.text()) >= 1 and self.tags_model.rowCount() > 0:
            self.tree_view.expandAll()
        else:
            self.tree_view.collapseAll()

    def add_tool_list_to_tree(self, toolbox_list, sorted_tools):
        first_child = None
        for i, toolbox in enumerate(toolbox_list):
            parent = QtGui.QStandardItem(
                QtGui.QIcon(os.path.join(bt_const.ASSETS_PATH, "close.gif")), toolbox
            )
            parent.setDragEnabled(False)
            for j, tool in enumerate(sorted_tools[i]):
                child = QtGui.QStandardItem(QtGui.QIcon(os.path.join(bt_const.ASSETS_PATH, "tool.gif")), tool)
                if i == 0 and j == 0:
                    first_child = child

                parent.appendRow([child])
            self.tree_model.appendRow(parent)

        return first_child

    def tree_view_selection_changed(self, new, old):
        if len(new.indexes()) == 0:
            return

        selected = new.indexes()[0]
        source_index = self.tags_model.mapToSource(selected)
        item = self.tree_model.itemFromIndex(source_index)
        parent = item.parent()
        if not parent:
            return

        tool = item.text()
        self.tool_changed.emit(tool)

    def tree_item_clicked(self, index):
        item = self.tree_model.itemFromIndex(self.tags_model.mapToSource(index))
        if item and item.parent():
            self.tool_changed.emit(item.text())

    def tree_item_expanded(self, index):
        source_index = self.tags_model.mapToSource(index)
        item = self.tree_model.itemFromIndex(source_index)
        if not item:
            return

        if item.hasChildren():
            item.setIcon(QtGui.QIcon(os.path.join(bt_const.ASSETS_PATH, "open.gif")))

    def tree_item_collapsed(self, index):
        source_index = self.tags_model.mapToSource(index)
        item = self.tree_model.itemFromIndex(source_index)
        if not item:
            return

        if item.hasChildren():
            item.setIcon(QtGui.QIcon(os.path.join(bt_const.ASSETS_PATH, "close.gif")))

    def get_tool_index(self, tool_name):
        items = self.tree_model.findItems(tool_name, QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive)
        if not items:
            return QtCore.QModelIndex()

        return self.tree_model.indexFromItem(items[0])

    def select_tool_by_index(self, index):
        if index is None or not index.isValid():
            return

        proxy_index = self.tags_model.mapFromSource(index)
        self.tree_sel_model.select(proxy_index, QtCore.QItemSelectionModel.ClearAndSelect)
        self.tree_view.expand(proxy_index.parent())
        self.tree_sel_model.setCurrentIndex(proxy_index, QtCore.QItemSelectionModel.Current)

    def select_tool_by_name(self, name):
        index = self.get_tool_index(name)
        self.select_tool_by_index(index)


class ClickSlider(QtWidgets.QSlider):
    """Custom slider for BERA Tools GUI."""

    def mousePressEvent(self, event):
        super(ClickSlider, self).mousePressEvent(event)
        if event.button() == QtCore.Qt.LeftButton:
            val = self.pixel_pos_to_range_value(event.pos())
            self.setValue(val)

    def pixel_pos_to_range_value(self, pos):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(
            QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderGroove, self
        )
        sr = self.style().subControlRect(
            QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderHandle, self
        )

        if self.orientation() == QtCore.Qt.Horizontal:
            slider_length = sr.width()
            slider_min = gr.x()
            slider_max = gr.right() - slider_length + 1
        else:
            slider_length = sr.height()
            slider_min = gr.y()
            slider_max = gr.bottom() - slider_length + 1
        pr = pos - sr.center() + sr.topLeft()
        p = pr.x() if self.orientation() == QtCore.Qt.Horizontal else pr.y()
        return QtWidgets.QStyle.sliderValueFromPosition(
            self.minimum(),
            self.maximum(),
            p - slider_min,
            slider_max - slider_min,
            opt.upsideDown,
        )


class BTSlider(QtWidgets.QWidget):
    """Slider for BERA Tools GUI."""

    def __init__(self, current, maximum, parent=None):
        super(BTSlider, self).__init__(parent)

        self.value = current
        self.slider = ClickSlider(QtCore.Qt.Horizontal)
        self.slider.setFixedWidth(120)
        self.slider.setTickInterval(2)
        self.slider.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.slider.setRange(1, maximum)

        # Block signals while setting initial value to avoid triggering save
        self.slider.blockSignals(True)
        self.slider.setValue(current)
        self.slider.blockSignals(False)

        self.label = QtWidgets.QLabel(self.generate_label_text(current))

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.slider)
        self.setLayout(layout)

        self.slider.valueChanged.connect(self.slider_moved)

    def slider_moved(self, value):
        actual_value = int(self.slider.value())
        bt.set_selected_cpu_cores(actual_value)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), f"{actual_value}")
        self.label.setText(self.generate_label_text(actual_value))

    def generate_label_text(self, value=None):
        if not value:
            value = self.slider.value()

        return f"Use CPU Cores: {value:3d}"


class BTListView(QtWidgets.QWidget):
    """List view for BERA Tools GUI."""

    tool_changed = QtCore.pyqtSignal(str)

    def __init__(self, data_list=None, parent=None):
        super(BTListView, self).__init__(parent)

        delete_icon = QtWidgets.QStyle.SP_DialogCloseButton
        delete_icon = self.style().standardIcon(delete_icon)
        clear_icon = QtWidgets.QStyle.SP_DialogResetButton
        clear_icon = self.style().standardIcon(clear_icon)
        btn_delete = QtWidgets.QPushButton()
        btn_clear = QtWidgets.QPushButton()
        btn_delete.setIcon(delete_icon)
        btn_clear.setIcon(clear_icon)
        btn_delete.setToolTip("Delete selected tool history")
        btn_clear.setToolTip("clear all tool history")
        btn_delete.setFixedWidth(40)
        btn_clear.setFixedWidth(40)

        layout_h = QtWidgets.QHBoxLayout()
        layout_h.addWidget(btn_delete)
        layout_h.addWidget(btn_clear)
        layout_h.addStretch(1)

        self.list_view = QtWidgets.QListView()
        self.list_view.setFlow(QtWidgets.QListView.TopToBottom)
        self.list_view.setBatchSize(5)

        self.list_model = QtCore.QStringListModel()  # model
        if data_list:
            self.list_model.setStringList(data_list)

        self.list_view.setModel(self.list_model)  # set model
        self.sel_model = self.list_view.selectionModel()

        self.list_view.setLayoutMode(QtWidgets.QListView.SinglePass)
        btn_delete.clicked.connect(self.delete_selected_item)
        btn_clear.clicked.connect(self.clear_all_items)
        self.sel_model.selectionChanged.connect(self.selection_changed)
        self.list_view.clicked.connect(self.item_clicked)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(layout_h)
        layout.addWidget(self.list_view)
        self.setLayout(layout)

    def selection_changed(self, new, old):
        indexes = new.indexes()
        if len(indexes) == 0:
            return

        selection = new.indexes()[0]
        tool = self.list_model.itemData(selection)[0]
        self.tool_changed.emit(tool)

    def item_clicked(self, index):
        # clicking the already selected tool doesn't change the selection, but should still show it
        tool = index.data()
        if tool:
            self.tool_changed.emit(tool)

    def set_data_list(self, data_list):
        self.list_model.setStringList(data_list)

    def delete_selected_item(self):
        selection = self.sel_model.currentIndex()
        row = selection.row()
        if row < 0:
            return

        self.list_model.removeRow(row)
        bt.remove_tool_history_item(row)

    def clear_all_items(self):
        self.list_model.setStringList([])
        bt.remove_tool_history_all()


class MainWindow(QtWidgets.QMainWindow):
    """Main window for BERA Tools GUI."""

    def __init__(self):
        super().__init__()

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.title = "BERA Tools"
        self.setWindowTitle(self.title)
        self.help_menu = None
        self.action_bera_tools_guide = None
        self.action_about_bera_tools = None
        self._create_help_menu()
        # always start on the first tool in the list (same as the tree view)
        self.tool_name = bt.tools_list[0] if bt.tools_list else None
        self.tool_api = bt.get_bera_tool_api(self.tool_name)

        # Only set to max if not already loaded from saved settings
        if bt.selected_cpu_cores <= 0:
            self.update_procs(bt.get_max_cpu_cores())

        # QProcess run tools
        self.process = None
        self.cancel_op = False
        self._stdout_buffer = ""

        # pipeline: the step shown in the tool form, and the steps of a running pipeline
        self.pipeline_step = None
        self.pipeline_run = None
        self.pipeline_index = 0
        # switching between a tool and pipeline steps keeps each tool's unsaved values, the tool to go
        # back to from a step, and the step to show again when going back to the Pipeline tab
        self.tool_drafts = {}
        self.standalone_tool = self.tool_name
        self.last_pipeline_step = None

        # BERA tool list
        self.bera_tools = bt.bera_tools
        self.tools_list = bt.tools_list
        self.sorted_tools = bt.sorted_tools
        self.toolbox_list = bt.toolbox_list
        self.upper_toolboxes = bt.upper_toolboxes
        self.lower_toolboxes = bt.lower_toolboxes

        self.current_file_path = Path(__file__).resolve().parent
        bt.set_bera_dir(self.current_file_path)

        # Tree view
        self.tree_view = BTTreeView()
        self.tree_view.tool_changed.connect(self.set_tool)

        # group box for tree view
        tree_box = QtWidgets.QGroupBox()
        tree_box.setTitle("Tools available")
        tree_layout = QtWidgets.QVBoxLayout()
        tree_layout.addWidget(self.tree_view)
        tree_box.setLayout(tree_layout)

        # QListWidget
        self.tool_history = BTListView()
        self.tool_history.set_data_list(bt.tool_history)
        self.tool_history.tool_changed.connect(self.set_tool)

        # Pipeline panel
        self.pipeline_panel = PipelinePanel(bt)
        self.pipeline_panel.step_selected.connect(self.show_pipeline_step)
        self.pipeline_panel.run_requested.connect(self.run_pipeline)
        self.pipeline_panel.add_requested.connect(lambda: self.pipeline_panel.add_tool(self.tool_name))

        # tabs for tool history and pipeline; dragging a tool over a tab switches to it
        self.left_tabs = QtWidgets.QTabWidget()
        self.left_tabs.addTab(self.tool_history, "Tool history")
        self.left_tabs.addTab(self.pipeline_panel, "Pipeline")
        self.left_tabs.tabBar().setAcceptDrops(True)
        self.left_tabs.tabBar().setChangeCurrentOnDrag(True)
        self.left_tabs.currentChanged.connect(self.left_tab_changed)

        # left and right sides are in splitters, which keep their sizes when the content changes
        # (e.g. selecting a pipeline step) and let the user resize them
        page_layout = QtWidgets.QHBoxLayout()
        self.left_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.setContentsMargins(0, 0, 0, 0)

        self.left_splitter.addWidget(tree_box)
        self.left_splitter.addWidget(self.left_tabs)

        # top buttons
        label = QtWidgets.QLabel(f"{self.tool_name}")
        label.setFont(QtGui.QFont("Consolas", 14))
        self.btn_advanced = QtWidgets.QPushButton("Show Advanced Options")
        self.btn_advanced.setFixedWidth(180)
        self.btn_tool_help = QtWidgets.QPushButton("Tool Help")
        self.btn_tool_help.setFixedWidth(100)

        self.btn_layout_top = QtWidgets.QHBoxLayout()
        self.btn_layout_top.setAlignment(QtCore.Qt.AlignRight)
        self.btn_layout_top.addWidget(label)
        self.btn_layout_top.addStretch(1)
        self.btn_layout_top.addWidget(self.btn_advanced)
        self.btn_layout_top.addWidget(self.btn_tool_help)

        # ToolWidgets
        tool_args = bt.get_bera_tool_args(self.tool_name)
        self.tool_widget = ToolWidgets(self.tool_name, tool_args, bt.show_advanced, bt_data_obj=bt)
        # at startup, history inputs that no longer exist start empty instead of flagged
        self.tool_widget.clear_missing_inputs()
        self.tool_scroll_area = QtWidgets.QScrollArea()
        self.tool_scroll_area.setWidgetResizable(True)
        self.tool_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.tool_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.tool_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.tool_scroll_area.setWidget(self.tool_widget)

        # bottom buttons
        slider = BTSlider(bt.selected_cpu_cores, bt.max_cpu_cores)
        btn_default_args = QtWidgets.QPushButton("Load Default Arguments")
        self.btn_run = QtWidgets.QPushButton("Run")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_exit = QtWidgets.QPushButton("Exit")
        btn_default_args.setFixedWidth(150)
        slider.setFixedWidth(250)
        self.btn_run.setFixedWidth(120)
        btn_cancel.setFixedWidth(120)
        btn_exit.setFixedWidth(120)

        btn_layout_bottom = QtWidgets.QHBoxLayout()
        btn_layout_bottom.setAlignment(QtCore.Qt.AlignRight)
        btn_layout_bottom.addStretch(1)
        btn_layout_bottom.addWidget(btn_default_args)
        btn_layout_bottom.addWidget(slider)
        btn_layout_bottom.addWidget(self.btn_run)
        btn_layout_bottom.addWidget(btn_cancel)
        btn_layout_bottom.addWidget(btn_exit)

        self.top_right_layout = QtWidgets.QVBoxLayout()
        self.top_right_layout.addLayout(self.btn_layout_top)
        self.top_right_layout.addWidget(self.tool_scroll_area)
        self.top_right_layout.addLayout(btn_layout_bottom)
        tool_widget_grp = QtWidgets.QGroupBox("Tool")
        tool_widget_grp.setLayout(self.top_right_layout)

        # Text widget
        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setFont(QtGui.QFont("Consolas", 9))
        self.text_edit.setReadOnly(True)
        self.text_edit.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self._show_log_context_menu)
        self.print_about()

        # progress bar
        self.progress_label = QtWidgets.QLabel()
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_var = 0

        # progress layout
        progress_layout = QtWidgets.QHBoxLayout()
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)

        self.right_layout.addWidget(tool_widget_grp)
        self.right_layout.addWidget(self.text_edit)
        self.right_layout.addLayout(progress_layout)

        # main layouts
        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(self.right_layout)
        self.page_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.page_splitter.setChildrenCollapsible(False)
        self.page_splitter.addWidget(self.left_splitter)
        self.page_splitter.addWidget(right_widget)
        self.page_splitter.setStretchFactor(0, 3)
        self.page_splitter.setStretchFactor(1, 7)
        self.page_splitter.setSizes([300, 700])  # scaled to the window when shown
        page_layout.addWidget(self.page_splitter)

        # signals and slots
        self.btn_advanced.clicked.connect(self.show_advanced)
        self.btn_tool_help.clicked.connect(self.show_help)
        btn_default_args.clicked.connect(self.load_default_args)
        self.btn_run.clicked.connect(self.start_process)
        btn_cancel.clicked.connect(self.stop_process)
        btn_exit.clicked.connect(self.close)

        widget = QtWidgets.QWidget(self)
        widget.setLayout(page_layout)
        self.setCentralWidget(widget)

    def _create_help_menu(self):
        menu_bar = self.menuBar()
        self.help_menu = menu_bar.addMenu("Help")

        self.action_bera_tools_guide = QtWidgets.QAction("BERA Tools Guide", self)
        self.action_about_bera_tools = QtWidgets.QAction("About BERA Tools", self)

        self.action_bera_tools_guide.triggered.connect(self.open_global_guide)
        self.action_about_bera_tools.triggered.connect(self.show_about_dialog)

        self.help_menu.addAction(self.action_bera_tools_guide)
        self.help_menu.addAction(self.action_about_bera_tools)

    def closeEvent(self, event):
        self.cancel_op = True
        if self.process is None:
            window_msg = "Are you sure you want to quit?"
        else:
            window_msg = "Work in progress. Are you sure you want to quit?"

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmation:",
            window_msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            if self.process is not None:
                self.process.kill()
            event.accept()
        else:
            event.ignore()

    def set_tool(self, tool=None):
        # a click also changes the tree selection, and selecting the tool in the tree below calls this again
        if tool == self.tool_name and self.pipeline_step is None:
            return

        self._save_tool_draft()
        if tool:
            self.tool_name = tool
        self.standalone_tool = self.tool_name

        # choosing a tool from the tree or history stops editing a pipeline step
        if self.pipeline_step is not None:
            self.last_pipeline_step = self.pipeline_step
            self.pipeline_step = None
            self.pipeline_panel.list_widget.blockSignals(True)
            self.pipeline_panel.list_widget.setCurrentRow(-1)
            self.pipeline_panel.list_widget.blockSignals(False)

        # let tree view select the tool
        self.tree_view.select_tool_by_name(self.tool_name)
        self._show_tool_form(self.tool_name, self.tool_name)
        if self.tool_name in self.tool_drafts:
            self.tool_widget.update_widgets(self.tool_drafts[self.tool_name])

    def _save_tool_draft(self):
        """Remember the values in a tool's form (not a step's), to restore them when the tool is shown again."""
        if self.pipeline_step is None:
            self.tool_drafts[self.tool_name] = self.tool_widget.get_widgets_values()

    def left_tab_changed(self, index):
        """Show the form that goes with the tab: the last pipeline step, or the tool chosen in the tree."""
        if self.left_tabs.widget(index) is self.pipeline_panel:
            step = self.last_pipeline_step
            if self.pipeline_step is None and step is not None:
                row = pipeline.step_index(self.pipeline_panel.steps, step["id"])
                if row is not None:
                    self.pipeline_panel.list_widget.setCurrentRow(row)
        elif self.pipeline_step is not None:
            self.set_tool(self.standalone_tool)

    def _show_tool_form(self, tool_name, label_text):
        self.tool_api = bt.get_bera_tool_api(tool_name)
        tool_args = bt.get_bera_tool_args(tool_name)

        # update tool label
        self.btn_layout_top.itemAt(0).widget().setText(label_text)

        # update tool widget
        self.tool_widget = ToolWidgets(tool_name, tool_args, bt.show_advanced, bt_data_obj=bt)
        old_widget = self.tool_scroll_area.takeWidget()
        if old_widget is not None:
            old_widget.deleteLater()
        self.tool_scroll_area.setWidget(self.tool_widget)
        self.top_right_layout.update()

    def show_pipeline_step(self, step):
        """Show a pipeline step's arguments in the tool form; edits are stored in the step."""
        if step is None:
            # the step is no longer selected (e.g. it was removed): go back to the tool
            if self.pipeline_step is not None:
                self.set_tool(self.standalone_tool)
            return

        self._save_tool_draft()
        self.pipeline_step = step
        self.last_pipeline_step = step

        steps = self.pipeline_panel.steps
        index = pipeline.step_index(steps, step["id"])
        self.tool_name = bt.get_bera_tool_name(step["tool_api"])
        self._show_tool_form(self.tool_name, f"Step {index + 1}: {self.tool_name}")
        self.tool_widget.update_widgets(step["args"])

        # linked inputs show what they will read (it may not exist until the pipeline runs) and can't be edited
        for variable, source_id in step["links"].items():
            input_widget = self.tool_widget.widgets_by_variable.get(variable)
            source = pipeline.step_index(steps, source_id)
            if input_widget is None or source is None:
                continue
            input_widget.in_file.setText("")
            input_widget.in_file.setPlaceholderText(pipeline.describe_link(steps, step, variable))
            input_widget.setEnabled(False)
            input_widget.setToolTip(f"Comes from the output of step {source + 1}")

        # a new step starts from the tool's saved or default values
        self._store_pipeline_step_args()
        self.tool_widget.connect_value_changed(self._store_pipeline_step_args)

    def _store_pipeline_step_args(self, *_):
        if self.pipeline_step is not None:
            self.pipeline_step["args"] = self.tool_widget.get_widgets_values()

    def save_tool_parameter(self):
        # Retrieve tool parameters from GUI
        args = self.tool_widget.get_widgets_arguments()
        bt.add_tool_history(self.tool_api, args)
        bt.save_tool_info()

        # update tool history list
        bt.get_tool_history()
        self.tool_history.set_data_list(bt.tool_history)

    def get_current_tool_parameters(self):
        self.tool_api = bt.get_bera_tool_api(self.tool_name)
        return bt.get_bera_tool_params(self.tool_name)

    def show_help(self):
        # open the user manual section for the current tool
        tech_link = self.get_current_tool_parameters()["tech_link"]
        if isinstance(tech_link, list):
            if tech_link:
                tech_link = tech_link[0]
            else:
                tech_link = ""
        webbrowser.open_new_tab(str(tech_link))

    def open_global_guide(self):
        webbrowser.open_new_tab(bt_data.get_global_docs_url())

    def show_about_dialog(self):
        version_info = bt_data.get_app_version_info()
        git_revision = version_info.get("git_revision") or "n/a"

        about_text = (
            "BERA Tools\n\n"
            "Developed by:\n\n Applied Geospatial Research Group (AppliedGRG)\n\n"
            "A suite of geospatial analysis tools for research and operations.\n\n"
            f"Version: {version_info.get('version', 'unknown')}\n"
            f"Git Revision: {git_revision}\n"
            "\n"
            f"Python: {sys.version.split()[0]}\n"
            f"PyQt: {QtCore.PYQT_VERSION_STR}\n"
            f"Qt: {QtCore.QT_VERSION_STR}\n"
            f"OS: {platform.platform()}\n\n"
            "License: GPL-3.0-or-later\n"
            f"Project: {bt_data.get_global_docs_url()}\n"
            "Credits: AppliedGRG / BERA"
        )
        QtWidgets.QMessageBox.about(self, "About BERA Tools", about_text)

    def print_about(self):
        self.text_edit.clear()
        self.print_to_output(bt.about())
        self.show_startup_warnings()

    def show_startup_warnings(self):
        warning_message = env_checks.get_gdal_proj_env_warning()
        if warning_message:
            self.print_line_to_output("")
            self.print_line_to_output("[Warning]")
            self.print_line_to_output(warning_message)

    def print_license(self):
        self.text_edit.clear()
        self.print_to_output(bt.license())

    def update_procs(self, value):
        selected_cpu_cores = int(value)
        bt.set_selected_cpu_cores(selected_cpu_cores)

    def print_to_output(self, text):
        self.text_edit.moveCursor(QtGui.QTextCursor.End)
        self.text_edit.insertPlainText(text)
        self.text_edit.moveCursor(QtGui.QTextCursor.End)

    def clear_log_messages(self):
        self.text_edit.clear()

    def _show_log_context_menu(self, pos):
        menu = self.text_edit.createStandardContextMenu()
        menu.addSeparator()
        clear_action = menu.addAction("Clear Messages")
        action = menu.exec_(self.text_edit.mapToGlobal(pos))
        if action == clear_action:
            self.clear_log_messages()

    def print_line_to_output(self, text, tag=None):
        self.text_edit.moveCursor(QtGui.QTextCursor.End)
        self.text_edit.insertPlainText(text + "\n")
        self.text_edit.moveCursor(QtGui.QTextCursor.End)

    def show_advanced(self):
        if bt.show_advanced:
            bt.show_advanced = False
            self.btn_advanced.setText("Show Advanced Options")
        else:
            bt.show_advanced = True
            self.btn_advanced.setText("Hide Advanced Options")

        self.tool_widget.show_advanced = bt.show_advanced

        for widget in self.tool_widget.widget_list:
            if widget.optional:
                widget.setVisible(bt.show_advanced)

        self.tool_widget._update_dependency_states()

        self.tool_widget.adjustSize()
        self.tool_widget.updateGeometry()
        self.tool_scroll_area.widget().adjustSize()
        self.tool_scroll_area.viewport().update()
        self.top_right_layout.activate()
        self.top_right_layout.update()

    def custom_callback(self, value):
        """Define custom callback that deals with tool output."""
        value = str(value)
        value.strip()
        if value != "":
            # remove esc string which origin is unknown
            rm_str = "\x1b[0m"
            if rm_str in value:
                value = value.replace(rm_str, "")

        if "%" in value:
            try:
                str_progress = extract_string_from_printout(value, "%")

                # remove progress string
                value = value.replace(str_progress, "").strip()
                progress = float(str_progress.replace("%", "").strip())
                self.progress_bar.setValue(int(progress))
            except ValueError as e:
                print("custom_callback: Problem parsing data into number: ", e)
            except Exception as e:
                print(e)
        if "PROGRESS_LABEL" in value:
            str_label = extract_string_from_printout(value, "PROGRESS_LABEL")
            value = value.replace(str_label, "").strip()  # remove progress string
            value = value.replace('"', "")
            str_label = str_label.replace("PROGRESS_LABEL", "").strip()
            self.progress_label.setText(str_label)

        if value:
            self.print_line_to_output(value)

    def message(self, s):
        self.text_edit.appendPlainText(s)

    def load_default_args(self):
        self.tool_widget.load_default_args()

    def start_process(self):
        args = self.tool_widget.get_widgets_arguments()
        if not args:
            print("Please check the parameters.")
            return

        bt.recent_tool = self.tool_name
        self.save_tool_parameter()
        self._launch_tool(self.tool_name, self.tool_api, args)

        while self.process is not None:
            sys.stdout.flush()
            if self.cancel_op:
                self.cancel_op = False
                self.process.terminate()
            else:
                break

    def _launch_tool(self, tool_name, tool_api, args):
        self.print_line_to_output("")
        self.print_line_to_output(f"Starting tool {tool_name} ... \n")
        self.print_line_to_output("-----------------------------")
        self.print_line_to_output("Tool arguments:")
        self.print_line_to_output(json.dumps(args, indent=4))
        self.print_line_to_output("")

        # Run the tool and check the return value for an error
        args = pipeline.stringify_args(args)
        tool_type, tool_args = bt.prepare_tool_run(tool_api, args, self.custom_callback)

        if self.process is None:  # No process running.
            self.print_line_to_output(f"Tool {tool_name} started")
            self.print_line_to_output("-----------------------")
            self._stdout_buffer = ""
            self.process = QtCore.QProcess()  # Keep a reference to the QProcess
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.stateChanged.connect(self.handle_state)

            # Clean up once complete.
            self.process.finished.connect(self.process_finished)
            self.process.start(tool_type, tool_args)

    def run_pipeline(self):
        steps = self.pipeline_panel.steps
        errors = pipeline.validate_pipeline(steps) + pipeline.missing_inputs(steps)
        if errors:
            QtWidgets.QMessageBox.warning(self, "Pipeline", "\n".join(errors))
            return
        if self.process is not None:
            QtWidgets.QMessageBox.warning(self, "Pipeline", "A tool is already running.")
            return

        # run a copy, so editing the pipeline while it runs doesn't change the remaining steps
        self.pipeline_run = copy.deepcopy(steps)
        self.pipeline_index = 0
        self.cancel_op = False
        self.pipeline_panel.set_running(True)
        self.btn_run.setEnabled(False)
        self.print_line_to_output("")
        self.print_line_to_output(f"Starting pipeline with {len(steps)} steps")
        self._start_pipeline_step()

    def _start_pipeline_step(self):
        steps = self.pipeline_run
        step = steps[self.pipeline_index]
        tool_name = bt.get_bera_tool_name(step["tool_api"])
        try:
            args = pipeline.resolve_step_args(steps, self.pipeline_index)
        except FileNotFoundError as err:
            self._finish_pipeline(f"Pipeline stopped before step {self.pipeline_index + 1}: {err}")
            return
        self._launch_tool(f"{tool_name} (step {self.pipeline_index + 1}/{len(steps)})", step["tool_api"], args)

    def _continue_pipeline(self, step_ok):
        if self.cancel_op:
            self.cancel_op = False
            self._finish_pipeline("Pipeline canceled.")
        elif not step_ok:
            self._finish_pipeline(f"Pipeline stopped: step {self.pipeline_index + 1} failed.")
        elif self.pipeline_index + 1 >= len(self.pipeline_run):
            self._finish_pipeline("Pipeline completed.")
        else:
            self.pipeline_index += 1
            # start the next step once the finished QProcess has been cleaned up
            QtCore.QTimer.singleShot(0, self._start_pipeline_step)

    def _finish_pipeline(self, msg):
        self.pipeline_run = None
        self.pipeline_panel.set_running(False)
        self.btn_run.setEnabled(True)
        self.message(msg)

    def stop_process(self):
        self.cancel_op = True
        if self.process:
            self.print_line_to_output(f"Tool {self.tool_name} terminating ...")
            self.process.kill()

    def handle_stderr(self):
        if not self.process:
            return
        data = self.process.readAllStandardError()
        stderr = bytes(data).decode("utf8")

        self.message(stderr)

    def handle_stdout(self):
        self._drain_stdout(flush_partial=False)
        sys.stdout.flush()

    def _drain_stdout(self, flush_partial=False):
        if not self.process:
            return

        data = self.process.readAllStandardOutput()
        try:
            chunk = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            chunk = bytes(data).decode("cp1252", errors="replace")
        if chunk:
            self._stdout_buffer += chunk

        while True:
            newline_idx = self._stdout_buffer.find("\n")
            if newline_idx < 0:
                break
            line = self._stdout_buffer[: newline_idx + 1]
            self._stdout_buffer = self._stdout_buffer[newline_idx + 1 :]
            self.custom_callback(line)

        if flush_partial and self._stdout_buffer:
            self.custom_callback(self._stdout_buffer)
            self._stdout_buffer = ""

    def handle_state(self, state):
        states = {
            QtCore.QProcess.NotRunning: "Not running",
            QtCore.QProcess.Starting: "Starting",
            QtCore.QProcess.Running: "Running",
        }
        state_name = states[state]
        if state_name == "Not running":
            self.btn_run.setEnabled(self.pipeline_run is None)
            if self.cancel_op:
                self.message("Tool operation canceled")
        elif state_name == "Starting":
            self.btn_run.setEnabled(False)

    def process_finished(self):
        step_ok = True
        if self.process:
            self._drain_stdout(flush_partial=True)

            stderr_data = self.process.readAllStandardError()
            if stderr_data:
                self.message(bytes(stderr_data).decode("utf8"))
            if self.pipeline_run is not None:
                step_ok = self.process.exitStatus() == QtCore.QProcess.NormalExit and self.process.exitCode() == 0

        self.message("Process finished.")
        self.process = None
        self._stdout_buffer = ""
        self.progress_bar.setValue(0)
        self.progress_label.setText("")

        if self.pipeline_run is not None:
            self._continue_pipeline(step_ok)


def runner():
    app = QtWidgets.QApplication(sys.argv)

    # Use absolute path for icons (works with embedded Python on Windows)
    assets_path = Path(__file__).parent / "assets"
    app.setWindowIcon(QtGui.QIcon(str(assets_path / "BERALogo.ico")))
    window = MainWindow()
    window.setMinimumSize(1024, 768)
    window.show()

    # Cross-platform tray icon (Windows: .ico, macOS: .png)
    if platform.system() == "Darwin":
        tray_icon_path = assets_path / "BERALogo.png"
    else:
        tray_icon_path = assets_path / "BERALogo.ico"
    tray_icon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(str(tray_icon_path)), app)
    tray_icon.setToolTip("BERA Tools")
    tray_icon.show()

    def signal_ready():
        ready_flag = os.getenv("BERA_SPLASH_READY")
        if ready_flag:
            try:
                from pathlib import Path

                Path(ready_flag).touch()
            except Exception:
                pass

    QtCore.QTimer.singleShot(100, signal_ready)

    # Allow Ctrl+C in the terminal to quit the application.
    # Qt overrides Python's SIGINT handler; use a custom handler that
    # calls app.quit() and a timer to let Python process signals.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QtCore.QTimer(app)
    timer.start(500)
    timer.timeout.connect(lambda: None)
    app.aboutToQuit.connect(timer.stop)

    app.exec_()
