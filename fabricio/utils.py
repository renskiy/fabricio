import collections
import contextlib
import ctypes
import functools
import hashlib
import multiprocessing

from distutils import util as distutils

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import six

from fabric import api as fab
from six.moves import shlex_quote

DEFAULT = object()


@contextlib.contextmanager
def patch(obj, attr, value, default=DEFAULT, force_delete=False):
    original = not force_delete and getattr(obj, attr, default)
    setattr(obj, attr, value)
    try:
        yield
    finally:
        if force_delete or original is DEFAULT:
            obj.__delattr__(attr)
        else:
            setattr(obj, attr, original)


class default_property(object):

    def __init__(self, func=None, default=None):
        self.func = func
        self.default = default

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.func is None:
            return self.default
        return self.func(instance)

    def __call__(self, func):
        self.func = func
        return self


class Options(OrderedDict):

    def make_option(self, option, value=None):
        option = '--' + option
        if value is not None:
            option += '=' + shlex_quote(six.text_type(value))
        return option

    def make_options(self):
        for option, value in self.items():
            if value is None:
                continue
            if isinstance(value, bool):
                if value is True:
                    yield self.make_option(option)
            elif isinstance(value, six.string_types):
                yield self.make_option(option, value)
            elif isinstance(value, collections.Iterable):
                for single_value in value:
                    yield self.make_option(option, single_value)
            else:
                yield self.make_option(option, value)

    def __str__(self):
        return ' '.join(self.make_options())


def strtobool(value):
    return distutils.strtobool(str(value))


def once_per_command(func):  # TODO default=None
    @functools.wraps(func)
    def _func(*args, **kwargs):
        lock = last_hash.get_lock()
        if lock.acquire(False):
            try:
                command = fab.env.command or ''
                infrastructure = fab.env.infrastructure or ''
                current_session = hashlib.md5()
                current_session.update(command.encode('utf-16be'))
                current_session.update(infrastructure.encode('utf-16be'))
                for host in fab.env.all_hosts:
                    current_session.update(host.encode('utf-16be'))
                current_hash = current_session.digest()
                if current_hash != last_hash.raw:
                    last_hash.raw = current_hash
                    return func(*args, **kwargs)
            finally:
                lock.release()
    last_hash = multiprocessing.Array(ctypes.c_char, hashlib.md5().digest_size)
    return _func


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class OrderedSet(collections.MutableSet):  # pragma: no cover
    """
    http://code.activestate.com/recipes/576694-orderedset/
    """

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)
