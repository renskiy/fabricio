import contextlib
import warnings

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from distutils import util as distutils

import six


@contextlib.contextmanager
def patch(obj, attr, value, default=None):
    original = getattr(obj, attr, default)
    setattr(obj, attr, value)
    yield
    setattr(obj, attr, original)


class default_property(object):

    def __init__(self, func):
        warnings.warn(
            'default_property is deprecated and will be removed in v0.4',
            DeprecationWarning,
        )
        warnings.warn(
            'default_property is deprecated and will be removed in v0.4',
            category=RuntimeWarning, stacklevel=2,
        )
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        return self.func(obj)


class Options(OrderedDict):

    @staticmethod
    def make_option(option, value=None):
        option = '--' + option.replace('_', '-')
        if value is not None:
            # TODO escape value
            option += ' ' + value
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
            elif isinstance(value, six.integer_types):
                yield self.make_option(option, str(value))
            else:
                for single_value in value:
                    yield self.make_option(option, single_value)

    def __str__(self):
        return ' '.join(self.make_options())


def strtobool(value):
    return bool(distutils.strtobool(str(value)))
