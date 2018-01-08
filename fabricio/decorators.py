import ctypes
import functools
import hashlib
import multiprocessing

from fabric import api as fab

import fabricio


def skip_unknown_host(func):
    @functools.wraps(func)
    def _task(*args, **kwargs):
        if fab.env.get('host_string', False):
            return func(*args, **kwargs)
        fabricio.log(
            "'{func}' execution was skipped due to no host provided "
            "(command: {command})".format(
                func=func.__name__,
                command=fab.env.command,
            )
        )
    _task.wrapped = func  # compatibility with Fabric tasks
    return _task


def once_per_task(func=None, block=False, default=None):
    if func is None:
        return functools.partial(once_per_task, block=block, default=default)

    @functools.wraps(func)
    def _func(*args, **kwargs):
        lock = last_hash.get_lock()
        if lock.acquire(block):
            try:
                task = fab.env.command or ''
                infrastructure = fab.env.infrastructure or ''
                current_session = hashlib.md5()
                current_session.update(task.encode('utf-16be'))
                current_session.update(infrastructure.encode('utf-16be'))
                for host in fab.env.all_hosts:
                    current_session.update(host.encode('utf-16be'))
                current_hash = current_session.digest()
                if current_hash != last_hash.raw:
                    last_hash.raw = current_hash
                    return func(*args, **kwargs)
                return default
            finally:
                lock.release()

    last_hash = multiprocessing.Array(ctypes.c_char, hashlib.md5().digest_size)
    _func.wrapped = func  # compatibility with Fabric tasks
    return _func
