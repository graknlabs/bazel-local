# `bazel-local`

A wrapper to run `bazel` with locally overriden dependencies.

## Intallation

`curl -sSf https://raw.githubusercontent.com/graknlabs/bazel-local/master/install.sh | sh`

## Usage

Use the `bazel-local` command in place of `bazel`.

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

You should add `.local_deps*` to your `.gitignore`.

## Enable/Disable

Disable by resetting the unwrapped link.

`rm /usr/local/bin/bazel && mv /usr/local/bin/bazel-unwrapped /usr/local/bin/bazel`

Enable by resetting the wrapper link.