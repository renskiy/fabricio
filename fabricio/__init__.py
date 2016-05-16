from fabric import api as fab

from .options import Options


def exec_command(command, ignore_errors=False, quiet=True):
    with fab.settings(warn_only=True, quiet=quiet):
        result = fab.sudo(command)
        if result.failed and not ignore_errors:
            raise RuntimeError(result)
    return result


def log(message):
    fab.puts(message)
