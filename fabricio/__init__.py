from __future__ import print_function

import hashlib
import sys

from fabric import colors, api as fab

from fabricio import utils

VERSION = (0, 4, 1)

__version__ = '.'.join(map(str, VERSION))

fab.env.setdefault('infrastructure', None)


def _command(
    fabric_method,
    command,
    ignore_errors=False,
    quiet=True,
    hide=('running', 'aborts'),
    show=(),
    abort_exception=RuntimeError,
    **kwargs
):
    if quiet:
        hide += ('output', 'warnings')
    log('{method}: {command}'.format(
        method=fabric_method.__name__,
        command=command,
    ))
    with fab.settings(
        fab.hide(*hide),
        fab.show(*show),
        abort_exception=abort_exception,
        warn_only=ignore_errors,
    ):
        return fabric_method(command, **kwargs)


def run(
    command,
    sudo=False,
    stdout=sys.stdout,
    stderr=sys.stderr,
    use_cache=False,
    cache_salt='',
    **kwargs
):
    if use_cache:
        md5 = hashlib.md5()
        md5.update(command.encode())
        md5.update((fab.env.host or '').encode())
        md5.update(cache_salt.encode())
        cache_key = md5.digest()
        if cache_key in run.cache:
            return run.cache[cache_key]
    fabric_method = sudo and fab.sudo or fab.run
    result = _command(
        fabric_method=fabric_method,
        command=command,
        stdout=stdout,
        stderr=stderr,
        **kwargs
    )
    if use_cache:
        run.cache[cache_key] = result
    return result
run.cache = {}


def local(
    command,
    stdout=sys.stdout,
    stderr=sys.stderr,
    quiet=True,
    capture=False,
    use_cache=False,
    cache_salt='',
    **kwargs
):
    if use_cache:
        md5 = hashlib.md5()
        md5.update(command.encode())
        md5.update(cache_salt.encode())
        cache_key = md5.digest()
        if cache_key in local.cache:
            return local.cache[cache_key]
    result = _command(
        fabric_method=fab.local,
        command=command,
        capture=capture,
        quiet=quiet,
        **kwargs
    )
    if use_cache:
        local.cache[cache_key] = result
    if capture and not quiet:
        if result:
            print(result, file=stdout)
        if result.stderr:
            print(result.stderr, file=stderr)
    return result
local.cache = {}


def log(message, color=colors.yellow, output=sys.stdout):
    with utils.patch(sys, 'stdout', output):
        fab.puts(color(message))


def move_file(path_from, path_to, sudo=False, force=True, ignore_errors=False):
    return run(
        'mv {force}{path_from} {path_to}'.format(
            path_from=path_from,
            path_to=path_to,
            force=force and '-f ' or '',
        ),
        sudo=sudo,
        ignore_errors=ignore_errors,
    )


def remove_file(path, sudo=False, force=True, ignore_errors=False):
    return run(
        'rm {force}{path}'.format(
            force=force and '-f ' or '',
            path=path,
        ),
        sudo=sudo,
        ignore_errors=ignore_errors,
    )
