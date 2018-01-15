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

    def reset():
        results.pop(get_current_task_id(), None)

    def has_result():
        return get_current_task_id() in results

    def get_current_task_id():
        task = fab.env.command or ''
        infrastructure = fab.env.infrastructure or ''
        session = hashlib.md5()
        session.update(task.encode('utf-16be'))
        session.update(infrastructure.encode('utf-16be'))
        for host in fab.env.all_hosts:
            session.update(host.encode('utf-16be'))
        return session.digest()

    @functools.wraps(func)
    def _func(*args, **kwargs):
        lock = last_task.get_lock()
        if lock.acquire(block):
            try:
                current_task = get_current_task_id()
                if current_task != last_task.raw:
                    last_task.raw = current_task
                    results[current_task] = result = func(*args, **kwargs)
                    return result
                return results.get(current_task, default)
            finally:
                lock.release()

    last_task = multiprocessing.Array(ctypes.c_char, hashlib.md5().digest_size)
    results = multiprocessing.Manager().dict()

    _func.has_result = has_result
    _func.reset = reset

    _func.wrapped = func  # compatibility with Fabric tasks

    return _func
