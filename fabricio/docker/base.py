import itertools
import multiprocessing
import sys

import six

from cached_property import cached_property
from fabric import api as fab, colors
from frozendict import frozendict

import fabricio

from fabricio import utils

from .image import Image


class ServiceError(fabricio.Error):
    pass


class ManagerNotFoundError(ServiceError):
    pass


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

    image = Image()

    @Attribute
    def name(self):
        raise ValueError('must provide service name')

    def __init__(self, image=None, options=None, safe_options=None, **attrs):
        if image is not None:
            self.image = image
        self.overridden_options = set()
        self.overridden_attributes = set()
        is_attribute = self._attributes.__contains__
        self._other_options = other_options = options or {}
        self._other_safe_options = safe_options or {}
        for option in list(other_options):
            attr = self._get_option_attribute(option)
            if attr:
                setattr(self, attr, other_options.pop(option))
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

    def _get_option_attribute(self, option_name):
        if option_name in self._options:
            return option_name
        if option_name in self._options_custom_names:
            return self._options_custom_names[option_name]
        return None

    @cached_property
    def _options_custom_names(self):
        return dict(
            (option.name, attr)
            for attr, option in self._options.items()
            if option.name
        )

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
        return six.text_type(self.name)

    def __copy__(self):
        return self.fork()

    def get_backup_version(self):
        raise NotImplementedError

    def update(self, tag=None, registry=None, account=None, force=False):
        raise NotImplementedError

    def revert(self):
        raise NotImplementedError

    def pull_image(self, tag=None, registry=None, account=None):
        image = self.image[registry:tag:account]
        if image:
            return image.pull()

    def migrate(self, tag=None, registry=None, account=None):
        pass

    def migrate_back(self):
        pass

    def backup(self):
        pass

    def restore(self, backup_name=None):
        pass

    def destroy(self):
        raise NotImplementedError

    @property
    def info(self):
        raise NotImplementedError


class ManagedService(BaseService):

    def __init__(self, *args, **kwargs):
        super(ManagedService, self).__init__(*args, **kwargs)
        self.managers = multiprocessing.Manager().dict()

    def _is_manager(self):
        command = 'docker info 2>&1 | grep "Is Manager:"'
        return fabricio.run(command).endswith('true')

    def is_manager(self, raise_manager_error=True):
        is_manager = self.managers.get(fab.env.host)
        try:
            if is_manager is None:
                is_manager = self.managers[fab.env.host] = self._is_manager()
        except fabricio.host_errors as error:
            is_manager = self.managers[fab.env.host] = False
            fabricio.log(
                'WARNING: {error}'.format(error=error),
                output=sys.stderr,
                color=colors.red,
            )
        finally:
            if (
                raise_manager_error
                and len(self.managers) >= len(fab.env.all_hosts)
                and not any(self.managers.values())
            ):
                msg = 'service manager not found or it failed to pull image'
                raise ManagerNotFoundError(msg)
        return is_manager

    def pull_image(self, *args, **kwargs):
        try:
            return super(ManagedService, self).pull_image(*args, **kwargs)
        except fabricio.host_errors as error:
            self.managers[fab.env.host] = False
            fabricio.log(
                'WARNING: {error}'.format(error=error),
                output=sys.stderr,
                color=colors.red,
            )

    def migrate(self, *args, **kwargs):
        if self.is_manager():
            super(ManagedService, self).migrate(*args, **kwargs)

    def migrate_back(self):
        if self.is_manager():
            super(ManagedService, self).migrate_back()

    def backup(self):
        if self.is_manager():
            super(ManagedService, self).backup()

    def restore(self, backup_name=None):
        if self.is_manager():
            super(ManagedService, self).restore(backup_name=backup_name)
