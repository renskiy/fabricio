import json

from cached_property import cached_property
from frozendict import frozendict

import fabricio

from . import Image


class Property(object):

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


class Option(Property):
    pass


class Attribute(Property):
    pass


class Container(object):

    image = Image()

    cmd = Attribute()
    stop_timeout = Attribute(default=10)

    user = Option()
    ports = Option()
    env = Option()
    volumes = Option()
    links = Option()
    hosts = Option()
    network = Option()
    restart_policy = Option()
    stop_signal = Option()

    def __init__(self, name, image=None, options=None, **attrs):
        self.name = name
        if image is not None:
            self.image = image

        options = options or {}
        self.overridden_options = set()
        is_default_option = self.default_options.__contains__
        self.options = container_options = {}
        for option, value in options.items():
            if is_default_option(option):
                setattr(self, option, value)
            else:
                container_options[option] = value

        self.overridden_attributes = set()
        is_attribute = self.attributes.__contains__
        if attrs:
            for attr, value in attrs.items():
                if not is_attribute(attr):
                    raise ValueError('Unknown attribute: {}'.format(attr))
                setattr(self, attr, value)

    def __setattr__(self, attr, value):
        if attr in self.default_options:
            self.overridden_options.add(attr)
        elif attr in self.attributes:
            self.overridden_attributes.add(attr)
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

    @cached_property
    def attributes(self):
        return set(
            attr
            for cls in type(self).__mro__
            for attr, value in vars(cls).items()
            if isinstance(value, Attribute)
        )

    def fork(self, name=None, image=None, options=None, **attrs):
        if name is None:
            name = self.name
        image = image or self.image

        fork_options = dict(
            (
                (option, getattr(self, option))
                for option in self.overridden_options
            ),
            **self._options
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

        return self.__class__(name, image=image, options=fork_options, **attrs)

    def __str__(self):
        return self.name

    def __copy__(self):
        return self.fork()

    @property
    def info(self):
        command = 'docker inspect --type container {container}'
        info = fabricio.run(command.format(container=self))
        return json.loads(info)[0]

    def delete(self, force=False, ignore_errors=False, delete_image=False):
        delete_image_callback = None
        if delete_image:
            try:
                delete_image_callback = self.image.delete(
                    ignore_errors=True,
                    deferred=True,
                )
            except RuntimeError:
                if ignore_errors:
                    return
                raise
        command = 'docker rm {force}{container}'
        force = force and '--force ' or ''
        fabricio.run(
            command.format(container=self, force=force),
            ignore_errors=ignore_errors,
        )
        if delete_image_callback:
            delete_image_callback()

    def run(self, tag=None, registry=None):
        self.image[registry:tag].run(
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
                new_image = self.image[registry:tag]
                if current_image_id == new_image.id:
                    fabricio.log('No change detected, update skipped.')
                    self.start()  # force starting container
                    return False
        new_container = self.fork(name=self.name)
        obsolete_container = self.get_backup_container()
        obsolete_container.delete(delete_image=True, ignore_errors=True)
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
        backup_container = self.get_backup_container()
        self.stop()
        self.delete(delete_image=True)
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
