from fabric import colors, api as fab


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
