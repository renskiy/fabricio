import collections
import contextlib
import warnings

from distutils import util as distutils

import six

from six.moves import shlex_quote

import fabricio

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


class Options(collections.OrderedDict):

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
    return distutils.strtobool(six.text_type(value))


def once_per_command(*args, **kwargs):  # pragma: no cover
    warnings.warn(
        'once_per_command renamed to fabricio.decorators.once_per_task, '
        'this one will be removed in 0.6',
        DeprecationWarning,
    )
    warnings.warn(
        'once_per_command renamed to fabricio.decorators.once_per_task, '
        'this one will be removed in 0.6',
        RuntimeWarning, stacklevel=2,
    )
    return fabricio.once_per_task(*args, **kwargs)


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class PriorityDict(dict):

    def __init__(self, iterable=None, priority=None, **kwargs):
        super(PriorityDict, self).__init__(iterable, **kwargs)
        self.priority = priority or []

    def items(self):
        seen = set()
        for key in self.priority:
            if key in self:
                yield key, self[key]
                seen.add(key)
        for key in self:
            if key not in seen:
                yield key, self[key]


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

    # additional methods

    union = collections.MutableSet.__ior__
