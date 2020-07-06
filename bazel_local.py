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
import signal
import time
import subprocess
import re
import shutil

local_deps_file = '.local_deps.toml'
local_deps_dir = '.local_deps_cache'

unwrapped_bazel_command = '/usr/local/bin/bazel'

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

def create_cached_file_dep(cwd, repo, binary_apath, args):
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

def create_cached_archive_dep(cwd, repo, binary_apath, args):
    deps_cache = os.path.abspath(local_deps_dir)
    mkdir(deps_cache)

    repo_cache_apath = os.path.join(deps_cache, repo)
    mkdir(repo_cache_apath)

    binary_name = os.path.basename(binary_apath)

    subprocess.run(['tar', '-xzf', binary_apath, '-C', repo_cache_apath], check=True)

    f = open(os.path.join(repo_cache_apath, 'WORKSPACE'), 'w')
    f.write(f'workspace(name = "{repo}")\n')
    f.close()

    shutil.copyfile(os.path.join(cwd, args[0]), os.path.join(repo_cache_apath, 'BUILD'))

    return repo_cache_apath

def transitive_local(cwd, local_repositories = {}):
    cwd = os.path.abspath(cwd)
    try:
        local_deps = toml.load(os.path.join(cwd, local_deps_file))
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
            local_repositories[repo] = os.path.abspath(os.path.join(cwd, path))
            transitive_local(path, local_repositories)
    except FileNotFoundError:
        pass

def create_local_deps(cwd, repo, args, create_function):
    path = args[0]
    target = args[1]
    apath = os.path.abspath(path)

    target = resolve_bazel_target(target)

    repo_target = f'@{repo}{target}'
    bazel_tool(['build', target], apath, check=True)
    dep_aquery = bazel_tool(['aquery', '--output', 'textproto', target], apath, capture_output=True, check=True).stdout.decode(sys.stdout.encoding)

    binary_subpath = re.findall('exec_path: "(.*)"', dep_aquery)[-1]
    binary_apath = os.path.join(apath, binary_subpath)

    repo_cache_apath = create_function(cwd, repo, binary_apath, args[2:])

    return [f'{repo}={repo_cache_apath}']

def bazel_tool(argv, cwd, capture_output=False, check=False):
    command_pos = 0
    for arg in argv:
        if (arg == '--'):
            return subprocess.run([unwrapped_bazel_command, *argv], check=check, capture_output=capture_output, cwd=cwd)
        if arg in bazel_commands:
            break
        command_pos += 1
    
    if command_pos == len(argv):
        return subprocess.run([unwrapped_bazel_command, *argv], check=check, capture_output=capture_output, cwd=cwd)

    local_repositories = {}
    transitive_local(cwd, local_repositories)
    
    local_repositories_args = []
    for repo, path in local_repositories.items():
        apath = os.path.abspath(path)
        local_repositories_args.append('--override_repository')
        local_repositories_args.append(f'{repo}={apath}')


    # Load local http_files
    http_files = {}
    try:
        local_deps = toml.load(os.path.join(cwd, local_deps_file))
        http_files = local_deps['http_files']
    except FileNotFoundError:
        pass
    except KeyError:
        pass

    http_files_args = []
    for repo, args in http_files.items():
        for l in create_local_deps(cwd, repo, args, create_cached_file_dep):
            http_files_args.append('--override_repository')
            http_files_args.append(l)
    
    http_archives = {}
    try:
        local_deps = toml.load(os.path.join(cwd, local_deps_file))
        http_archives = local_deps['http_archives']
    except FileNotFoundError:
        pass
    except KeyError:
        pass

    http_archive_args = []
    for repo, args in http_archives.items():
        for l in create_local_deps(cwd, repo, args, create_cached_archive_dep):
            http_files_args.append('--override_repository')
            http_files_args.append(l)

    command_args = [unwrapped_bazel_command, *argv[0:command_pos+1], *local_repositories_args, *http_files_args]
    if command_pos < len(argv) - 1:
        command_args.extend(argv[command_pos+1:])

    full_command = ' '.join(command_args)
    print(cwd, full_command)
    return subprocess.run(command_args, cwd=cwd, check=check, capture_output=capture_output)


if __name__ == "__main__":
    try:
        sys.exit(bazel_tool(sys.argv[1:], os.getcwd()).returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        pass        
