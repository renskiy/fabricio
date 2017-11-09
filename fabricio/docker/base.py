import itertools

from cached_property import cached_property
from frozendict import frozendict
from six.moves import filter

from fabricio import utils

from .image import Image


class Option(utils.default_property):

    def __init__(
        self,
        func=None,
        default=None,
        name=None,
        safe=False,
        safe_name=None,
    ):
        super(Option, self).__init__(func=func, default=default)
        self.name = name
        self.safe = safe
        self.safe_name = safe_name


class Attribute(utils.default_property):
    pass


class BaseService(object):

    name = Attribute()

    image = Image()

    def __init__(self, image=None, options=None, safe_options=None, **attrs):
        if image is not None:
            self.image = image
        self.overridden_options = set()
        self.overridden_attributes = set()
        is_option = self._options.__contains__
        is_attribute = self._attributes.__contains__
        self._other_options = other_options = options or {}
        self._other_safe_options = safe_options or {}
        for option in list(filter(is_option, other_options)):
            setattr(self, option, other_options.pop(option))
        for attr, value in attrs.items():
            if not is_attribute(attr):
                raise TypeError('Unknown attribute: {attr}'.format(attr=attr))
            setattr(self, attr, value)

    def __setattr__(self, attr, value):
        if attr in self._options:
            self.overridden_options.add(attr)
        elif attr in self._attributes:
            self.overridden_attributes.add(attr)
        super(BaseService, self).__setattr__(attr, value)

    @property
    def image_id(self):
        raise NotImplementedError

    @cached_property
    def _attributes(self):
        return set(
            attr
            for cls in type(self).__mro__[::-1]
            for attr, value in vars(cls).items()
            if isinstance(value, Attribute)
        )

    @classmethod
    def _get_available_options(cls, safe=False):
        return dict(
            (attr, option)
            for mro in cls.__mro__[::-1]
            for attr, option in vars(mro).items()
            if isinstance(option, Option)
            and (safe and option.safe or option.safe_name or not safe)
        )

    @cached_property
    def _options(self):
        return self._get_available_options()

    @cached_property
    def _safe_options(self):
        return self._get_available_options(safe=True)

    def _get_options(self, safe=False):
        options = itertools.chain(
            (
                (
                    safe and option.safe_name or option.name or attr,
                    getattr(self, attr),
                )
                for attr, option in
                (self._safe_options if safe else self._options).items()
            ),
            (self._other_safe_options if safe else self._other_options).items(),
        )
        evaluated_options = (
            (option, value(self) if callable(value) else value)
            for option, value in options
        )
        return frozendict(
            (option, value)
            for option, value in evaluated_options
            if value is not None
        )

    @property
    def options(self):
        return self._get_options()

    @property
    def safe_options(self):
        return self._get_options(safe=True)

    def fork(self, image=None, options=None, **attrs):
        image = image or self.image
        fork_options = dict(
            (
                (option, getattr(self, option))
                for option in self.overridden_options
            ),
            **self._other_options
        )
        if options:
            fork_options.update(options)
        if self.overridden_attributes:
            attrs = dict(
                (
                    (attr, getattr(self, attr))
                    for attr in self.overridden_attributes
                ),
                **attrs
            )
        return self.__class__(image=image, options=fork_options, **attrs)

    def __str__(self):
        if not self.name:
            raise ValueError('service name is not set or empty')
        return self.name

    def __copy__(self):
        return self.fork()

    def get_backup_version(self):
        raise NotImplementedError

    def update(self, tag=None, registry=None, account=None, force=False):
        raise NotImplementedError

    def revert(self):
        raise NotImplementedError

    def pull_image(self, tag=None, registry=None, account=None):
        return self.image[registry:tag:account].pull()

    def migrate(self, tag=None, registry=None, account=None):
        pass

    def migrate_back(self):
        pass

    def backup(self):
        pass

    def restore(self, backup_name=None):
        pass

    @property
    def info(self):
        raise NotImplementedError
