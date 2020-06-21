#!/usr/bin/env python3

# Read config list of local dependencies
# - Read .local_deps.toml
# - Parse local git repositories and local http_files with corresponding repo path and targets:
#   - Convert relative paths to absolute paths

# Check all local file repositories and update their targets, for each:
# - Build the target from local file repository
# - bazel aquery the same target to find the output file
# - Copy the output file into a secret directory under .local_deps_cache/
# - Add a WORKSPACE and a file/BUILD for bazel

# Generate the necessary flags to override all of the bazel repositories to local paths

# Perform the regular bazel build command but with these flags

import sys
import toml
import os
import subprocess
import re
import shutil

local_deps_file = '.local_deps.toml'
local_deps_dir = '.local_deps_cache'

bazel_commands = [
    'analyze-profile',
    'aquery',
    'build',
    'canonicalize-flags',
    'coverage',
    'cquery',
    'dump',
    'fetch',
    'mobile-install',
    'print_action',
    'query',
    'run',
    'sync',
    'test'
]

def mkdir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass

# Only valid in base dir
# TODO make directory dependent
def resolve_bazel_target(target):
    if ':' not in target:
        targetv = target.split('/')
        targetv[-1] = f'{targetv[-1]}:{targetv[-1]}'
        target = ''.join(targetv)
    
    if not target.startswith('//'):
        target = f'//{target}'
    
    return target

def create_cached_dep(repo, binary_apath):
    deps_cache = os.path.abspath(local_deps_dir)
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

def transitive_local(dir, local_repositories = {}):
    dir = os.path.abspath(dir)
    try:
        local_deps = toml.load(os.path.join(dir, local_deps_file))
        local_deps_repos = {}
        try:
            local_deps_repos = local_deps['local_repositories']
        except KeyError:
            return
        
        for repo, path in local_deps_repos.items():
            try:
                local_repositories[repo]
                return
            except KeyError:
                pass
            local_repositories[repo] = os.path.abspath(os.path.join(dir, path))
            transitive_local(path, local_repositories)
    except FileNotFoundError:
        pass

def bazel_tool(argv, dir, capture_output=False):
    command_pos = 0
    for arg in argv:
        if (arg == '--'):
            return None # No build command
        if arg in bazel_commands:
            break
        command_pos += 1
    
    if command_pos == len(argv):
        return None # No build command

    local_repositories = {}
    transitive_local(dir, local_repositories)
    
    local_repositories_args = []
    for repo, path in local_repositories.items():
        apath = os.path.abspath(path)
        local_repositories_args.append('--override_repository')
        local_repositories_args.append(f'{repo}={apath}')


    # Load local http_files
    http_files = {}
    try:
        local_deps = toml.load(os.path.join(dir, local_deps_file))
        http_files = local_deps['http_files']
    except FileNotFoundError:
        pass
    except KeyError:
        pass

    http_files_args = []
    for repo, path_target in http_files.items():
        path, target = path_target.split('@')
        apath = os.path.abspath(path)

        target = resolve_bazel_target(target)

        # subprocess.run(['bazel_tool', 'build', target], check=True, cwd=apath)
        repo_target = f'@{repo}{target}'
        bazel_tool(['build', target], apath)
        dep_aquery = bazel_tool(['aquery', '--output', 'textproto', target], apath, capture_output=True).stdout.decode(sys.stdout.encoding)

        binary_subpath = re.findall('exec_path: "(.*)"', dep_aquery)[-1]
        binary_apath = os.path.join(apath, binary_subpath)

        repo_cache_apath = create_cached_dep(repo, binary_apath)

        http_files_args.append('--override_repository')
        http_files_args.append(f'{repo}={repo_cache_apath}')

    command_args = ['bazel', *argv[0:command_pos+1], *local_repositories_args, *http_files_args]
    if command_pos < len(argv) - 1:
        command_args.extend(argv[command_pos+1:])
    print(dir, ' '.join(command_args))
    return subprocess.run(command_args, check=True, capture_output=capture_output, cwd=dir)

if __name__ == "__main__":
    try:
        sys.exit(bazel_tool(sys.argv[1:], os.getcwd()).returncode)
    except subprocess.CalledProcessError:
        sys.exit(1)
