# Overview


## Project Layout

There are a number of files for build, test, and continuous integration in the root of the project, but in general, the
project is broken up like so.

```
├── beratools
│   ├── cli
│   ├── core
│   ├── gui
│   ├── tools
│   └── utility
├── docs
│   └── files
├── examples
├── notebooks
├── tests
```

Directory            | Description
-------------------- | -----------
`beratools/cli`      | The `bt` / `beratools` command (`entry.py`), with one subcommand per tool.
`beratools/core`     | Core algorithms and logic, and user-built pipelines (`pipeline.py`).
`beratools/gui`      | GUI components and assets; `assets/beratools.json` defines every tool and its parameters.
`beratools/tools`    | Tool implementations.
`beratools/utility`  | Argument composition (`tool_args.py`), environment checks and spatial helpers.
`examples`           | Example workflows.
`docs/files/developer`   | Developer documentation.
`notebooks`          | Example notebooks and configs.
`tests`              | Unit and integration tests.