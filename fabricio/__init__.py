import functools
import warnings

from fabric import colors, api as fab
from fabric.contrib import console


def sudo(command, ignore_errors=False, quiet=True):
    warnings.warn(
        "fabricio.sudo() is deprecated and will be removed starting from "
        "version 0.2. Use fabricio.run(sudo=True) instead",
        DeprecationWarning,
    )
    hide = quiet and ('output', 'warnings') or ()
    with fab.settings(fab.hide(*hide), warn_only=True):
        result = fab.sudo(command.strip())
        if result.failed and not ignore_errors:
            raise RuntimeError(result)
    return result


def _command(
    fabric_method,
    command,
    ignore_errors=False,
    quiet=True,
    hide=('running', ),
    show=(),
    **kwargs
):
    command = command.strip()
    if quiet:
        hide += ('stdout', )
    log('{method}: {command}'.format(method=fabric_method.__name__, command=command))
    with fab.settings(fab.hide(*hide), fab.show(*show), warn_only=True):
        result = fabric_method(command, **kwargs)
        if result.failed and not ignore_errors:
            raise RuntimeError(result)
    return result


def run(command, sudo=False, **kwargs):
    fabric_method = sudo and fab.sudo or fab.run
    return _command(
        fabric_method=fabric_method,
        command=command,
        **kwargs
    )


def local(command, **kwargs):
    return _command(
        fabric_method=fab.local,
        command=command,
        **kwargs
    )


def log(message, color=colors.yellow):
    fab.puts(color(message))


def infrastructure(confirm=True, color=colors.yellow):
    def _decorator(task):
        @functools.wraps(task)
        def _task(*args, **kwargs):
            if confirm and console.confirm(
                'Are you sure you want to select {infrastructure} '
                'infrastructure to run task(s) on?'.format(
                    infrastructure=color(task.__name__),
                ),
                default=False,
            ):
                return task(*args, **kwargs)
            fab.abort('Aborted')
        return _task
    if callable(confirm):
        func, confirm = confirm, infrastructure.__defaults__[0]
        return _decorator(func)
    return _decorator
