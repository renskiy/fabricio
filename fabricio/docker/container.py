import json
import warnings

from cached_property import cached_property
from frozendict import frozendict

import fabricio

from . import Image


class Option(object):

    def __init__(self, func=None, value=None):
        self.func = func
        if func is not None:
            self.__doc__ = func.__doc__
        self.value = value

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.func is None:
            return self.value
        return self.func(instance)


class Container(object):

    image = None  # type: Image

    cmd = None

    stop_timeout = 10

    user = Option()
    ports = Option()
    env = Option()
    volumes = Option()
    links = Option()
    hosts = Option()
    network = Option()
    restart_policy = Option()
    stop_signal = Option()

    def __init__(self, name, options=None, **kwargs):
        self.name = name
        if options:
            warnings.warn(
                '`options` deprecated and will be removed in v0.4',
                category=RuntimeWarning, stacklevel=2,
            )
        deprecated_options = options or {}
        self.overridden_options = set()
        is_default_option = self.default_options.__contains__
        self.options = options = {}
        for option, value in dict(deprecated_options, **kwargs).items():
            if is_default_option(option):
                setattr(self, option, value)
            else:
                options[option] = value

    def __setattr__(self, attr, value):
        if attr in self.default_options:
            self.overridden_options.add(attr)
        super(Container, self).__setattr__(attr, value)

    def _get_options(self):
        default_options_values = dict(
            (option, getattr(self, option))
            for option in self.default_options
        )
        return frozendict(self._options, **default_options_values)

    def _set_options(self, options):
        self._options = options

    options = property(_get_options, _set_options)

    @cached_property
    def default_options(self):
        return set(
            attr
            for cls in type(self).__mro__
            for attr, value in vars(cls).items()
            if isinstance(value, Option)
        )

    def fork(self, name=None, options=None, **kwargs):
        if options:
            warnings.warn(
                '`options` deprecated and will be removed in v0.4',
                category=RuntimeWarning, stacklevel=2,
            )
        if name is None:
            name = self.name
        deprecated_options = options or {}

        options = dict(self.options)
        for option in (self.default_options - self.overridden_options):
            del options[option]

        options.update(deprecated_options)
        options.update(kwargs)
        return self.__class__(name, **options)

    def __str__(self):
        return str(self.name)

    def __copy__(self):
        return self.fork()

    @property
    def info(self):
        command = 'docker inspect --type container {container}'
        info = fabricio.run(command.format(container=self))
        return json.loads(info)[0]

    def delete(self, force=False, ignore_errors=False):
        command = 'docker rm {force}{container}'
        force = force and '--force ' or ''
        fabricio.run(
            command.format(container=self, force=force),
            ignore_errors=ignore_errors,
        )

    def run(self, tag=None, registry=None):
        self.__class__.image[registry:tag].run(
            cmd=self.cmd,
            temporary=False,
            name=self.name,
            options=self.options,
        )

    def execute(self, cmd, ignore_errors=False, quiet=True, use_cache=False):
        command = 'docker exec --tty --interactive {container} {cmd}'
        return fabricio.run(
            command.format(container=self, cmd=cmd),
            ignore_errors=ignore_errors,
            quiet=quiet,
            use_cache=use_cache,
        )

    def start(self):
        command = 'docker start {container}'
        fabricio.run(command.format(container=self))

    def stop(self, timeout=None):
        if timeout is None:
            timeout = self.stop_timeout
        command = 'docker stop --time {timeout} {container}'
        fabricio.run(command.format(container=self, timeout=timeout))

    def restart(self, timeout=None):
        if timeout is None:
            timeout = self.stop_timeout
        command = 'docker restart --time {timeout} {container}'
        fabricio.run(command.format(container=self, timeout=timeout))

    def rename(self, new_name):
        command = 'docker rename {container} {new_name}'
        fabricio.run(command.format(container=self, new_name=new_name))
        self.name = new_name

    def signal(self, signal):
        command = 'docker kill --signal {signal} {container}'
        fabricio.run(command.format(container=self, signal=signal))

    def update(self, tag=None, registry=None, force=False):
        if not force:
            try:
                current_image_id = self.image.id
            except RuntimeError:  # current container not found
                pass
            else:
                new_image = self.__class__.image[registry:tag]
                if current_image_id == new_image.id:
                    fabricio.log('No change detected, update skipped.')
                    self.start()  # force starting container
                    return False
        new_container = self.fork(name=self.name)
        obsolete_container = self.get_backup_container()
        try:
            obsolete_image = obsolete_container.image
        except RuntimeError:
            pass
        else:
            obsolete_container.delete()
            obsolete_image.delete(ignore_errors=True)
        try:
            backup_container = self.fork()
            backup_container.rename(obsolete_container.name)
        except RuntimeError:
            pass
        else:
            backup_container.stop()
        new_container.run(tag=tag, registry=registry)
        return True

    def revert(self):
        failed_image = self.image
        self.stop()
        self.delete()
        failed_image.delete(ignore_errors=True)
        backup_container = self.get_backup_container()
        backup_container.start()
        backup_container.rename(self.name)

    def get_backup_container(self):
        return self.fork(name='{container}_backup'.format(container=self))

    def migrate(self, tag=None, registry=None):
        pass

    def migrate_back(self):
        pass

    def backup(self):
        pass

    def restore(self, backup_name=None):
        pass
