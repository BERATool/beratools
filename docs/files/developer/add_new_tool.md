# How to Add a New Tool

This page focuses on the **practical contributor workflow** for adding a new tool.

For runtime internals (CLI/GUI call modes, argument composition, multiprocessing), see:
- [Tool Runtime Model](../technical/architecture/tool_runtime_model.md)

## 1) Create the tool script

Add a new script in `beratools/tools` (you can start from `tool_template.py`).

Typical API pattern:

```python
def my_tool(..., processes=0, call_mode=CallMode.CLI, log_level="INFO"):
    ...
```

Add `__main__` entrypoint:

```python
if __name__ == "__main__":
    from beratools.utility.tool_args import compose_tool_kwargs
    kwargs = compose_tool_kwargs("my_tool")
    my_tool(**kwargs)
```

## 2) Register in GUI metadata

Update `beratools/gui/assets/beratools.json` and add your tool definition in the proper category.

At minimum, define:

- `name`, `info`, `tool_type`, `tool_api`, `icon`, `tech_link`
- parameter list (`variable`, `label`, `description`, `type`, `subtype`, `default`, `output`, `optional`)

`tool_api` must match the module name and the string passed to `compose_tool_kwargs`, or the tool
stops with `Tool API '<name>' not found in beratools.json`.

### Taking part in pipelines

Every registered `python` tool can be a step in a GUI pipeline. To let its inputs be linked to an
earlier step's output, tag the parameters with a *kind*:

- an input parameter gets `"accepts": "<kind>"`;
- an output parameter gets `"produces": {"<kind>": [patterns]}`. An empty list means the output value
  itself (an output file such as `lines.gpkg|centerline`); otherwise the
  pipeline uses the first glob pattern that matches files in the output folder, newest file first.

```json
{"variable": "in_line", "accepts": "line", ...}
{"variable": "out_line", "produces": {"line": []}, ...}
{"variable": "out_folder", "produces": {"dtm": ["Merged_*_DTM.tif", "*_DTM.tif"]}, ...}
```

The kinds in use are `line` and `footprint`; add a new one when a tool writes something new. `tests/test_pipeline.py` checks that every
accepted kind has a producer. For the pipeline to stop when your tool fails, exit with a non-zero
code (`sys.exit(1)` or an uncaught exception), not a plain `exit()`.

### Adding the CLI subcommand

In `beratools/cli/entry.py`, add a short alias to `TOOL_ALIASES` (for example
`"my_tool": "my_tool"`) and teach `_resolve_tool_function` to import and return the tool function.

## 3) Keep tools thin; move heavy logic to core

- Put high-level tool wiring in `beratools/tools/*`
- Put algorithm-heavy logic in `beratools/core/*`

This keeps code easier to test and maintain.

## 4) Test from CLI first

Run help and a sample execution before validating in GUI:

```bash
python beratools/tools/my_tool.py --help
```

Then test via GUI once CLI behavior is stable.

## 5) Add docs and tests

- Add/update user docs if end-user behavior changed
- Add/update technical docs for algorithm/runtime internals
- Add tests in `tests/` for new behavior and edge cases

## 6) Submit PR

- Follow branching and contribution guidance in [Development](development.md)
- Request review and ensure CI passes
