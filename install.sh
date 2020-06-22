set -ex

INSTALL_DIR=~/.local_deps

mkdir -p "${INSTALL_DIR}"

pip3 install --upgrade toml

curl -sSf https://raw.githubusercontent.com/graknlabs/bazel-local/master/bazel_local.py > "${INSTALL_DIR}/bazel_local.py"

chmod +x "${INSTALL_DIR}/bazel_local.py"

ln -s "${INSTALL_DIR}/bazel_local.py" /usr/local/bin/bazel-local