from fabric import api as fab


def sudo(command, ignore_errors=False, quiet=True):
    hide = quiet and ('output', 'warnings') or ()
    with fab.settings(fab.hide(*hide), warn_only=True):
        result = fab.sudo(command.strip())
        if result.failed and not ignore_errors:
            raise RuntimeError(result)
    return result


def log(message):
    fab.puts(message)
