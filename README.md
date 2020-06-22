# `bazel-tool`

A wrapper to run `bazel` with locally overriden dependencies.

## Intallation

`curl -sSf https://raw.githubusercontent.com/graknlabs/bazel-local/master/install.sh | echo`

## Usage

Installed in place of the regular `bazel` command when running bazel, use `bazel-unwrapped` for the unwrapped version.

To enable local dependency overriding, create a `.local_deps.toml` in the root of your bazel workspace. An example is shown:

```toml
# Override git_repository/http_archive with local bazel workspaces at the given directory.
# This works recursively, respecting their local `.local_deps.toml` configuration.
[local_repositories]
graknlabs_grakn_common = "../common"

# Override a http_file with the output of the given [<workspace_path>, <target>]
[http_files]
graknlabs_console = ["../console", "//:console-deps"]
```