import collections
import contextlib
import ctypes
import functools
import hashlib
import multiprocessing
import re

from distutils import util as distutils

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import six

from fabric import api as fab

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


class Options(OrderedDict):  # TODO OrderedDict => dict

    quoting_required_regex = re.compile('[\s"\']+')

    def quote_option_value(self, value):
        if value and not self.quoting_required_regex.search(value):
            return value
        return '"{value}"'.format(value=value.replace('"', '\\"'))

    def make_option(self, option, value=None):
        option = '--' + option
        if value is not None:
            option += ' ' + self.quote_option_value(six.text_type(value))
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
    return bool(distutils.strtobool(str(value)))


class Item(six.text_type):

    def __hash__(self):
        return hash(self.get_comparison_value())

    def __eq__(self, other):
        return self.get_comparison_value() == other

    def get_comparison_value(self):
        raise NotImplementedError


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
