#!/usr/bin/env python3

import sys
import toml
import os
import subprocess
import re
import shutil

def mkdir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass

def create_cached_dep(repo, binary_apath):
    deps_cache = os.path.abspath('.local_deps_cache')
    mkdir(deps_cache)

    repo_cache_apath = os.path.join(deps_cache, repo)
    mkdir(repo_cache_apath)

    filedir_apath = os.path.join(repo_cache_apath, 'file')
    mkdir(filedir_apath)

    binary_name = os.path.basename(binary_apath)

    f = open(os.path.join(repo_cache_apath, 'WORKSPACE'), 'w')
    f.write(f'workspace(name = "{repo}")\n')
    f.close()

    f = open(os.path.join(filedir_apath, 'BUILD'), 'w')
    f.write('filegroup(\n'
            '    name = "file",\n'
            f'    srcs = ["{binary_name}"],\n'
            '    visibility = ["//visibility:public"],\n'
            ')\n')
    f.close()

    shutil.copyfile(binary_apath, os.path.join(filedir_apath, binary_name))

    return repo_cache_apath


local_deps = toml.load('.local_deps')

# Load local repository config and build CLI args
local_repositories = {}
try:
    local_repositories = local_deps['local_repositories']
except KeyError:
    pass

local_repositories_args = []
for repo, path in local_repositories.items():
    apath = os.path.abspath(path)
    local_repositories_args.append('--override_repository')
    local_repositories_args.append(f'{repo}={apath}')


# Load local http_files
http_files = {}
try:
    http_files = local_deps['http_files']
except KeyError:
    pass

http_files_args = []
for repo, path_target in http_files.items():
    path, target = path_target.split('@')
    apath = os.path.abspath(path)

    subprocess.run(['bazel_tool', 'build', target], check=True, cwd=apath)
    dep_aquery = subprocess.check_output(['bazel_tool', 'aquery', '--output', 'textproto', target], cwd=apath).decode(sys.stdout.encoding)

    binary_subpath = re.findall('exec_path: "(.*)"', dep_aquery)[-1]
    binary_apath = os.path.join(apath, binary_subpath)
    print(binary_apath)

    repo_cache_apath = create_cached_dep(repo, binary_apath)

    http_files_args.append('--override_repository')
    http_files_args.append(f'{repo}={repo_cache_apath}')

# TODO should split input args by a "--" arg

command_args = ['bazel', sys.argv[1], *local_repositories_args, *http_files_args, *sys.argv[2:]]
print(' '.join(command_args))
sys.exit(subprocess.run(command_args, check=True).returncode)


# Read config list of local dependencies
# - Read .local_deps
# - Parse local git repositories and local http_files with corresponding repo path and targets:
#   - Convert relative paths to absolute paths

# Check all local file repositories and update their targets, for each:
# - Build the target from local file repository
# - bazel aquery the same target to find the output file (will require parsing textproto)
# - Copy the output file into a secret directory under /file
# - Add a WORKSPACE and a file/BUILD for bazel

# Generate the necessary flags to override all of the bazel repositories to local paths

# Perform the regular bazel build command but with these flags