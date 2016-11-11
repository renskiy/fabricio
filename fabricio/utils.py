import contextlib
import re

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

    def __init__(self, func=None, default=None):
        self.func = func
        if func is not None:
            self.__doc__ = func.__doc__
        self.default = default

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.func is None:
            return self.default
        return self.func(instance)


class Options(OrderedDict):

    quoting_required_regex = re.compile('[\s"\']+')

    def quote_option_value(self, value):
        if value and not self.quoting_required_regex.search(value):
            return value
        return '"{value}"'.format(value=value.replace('"', '\\"'))

    def make_option(self, option, value=None):
        option = '--' + option
        if value is not None:
            # TODO escape value
            option += ' ' + self.quote_option_value(value)
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
