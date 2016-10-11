import json
import warnings

from docker import utils as docker_utils, auth as docker_auth

import fabricio

from fabricio.utils import default_property, Options


class Image(object):

    container_options_mapping = (
        ('user', 'user'),
        ('publish', 'ports'),
        ('env', 'env'),
        ('volume', 'volumes'),
        ('link', 'links'),
        ('add-host', 'hosts'),
        ('net', 'network'),
        ('restart', 'restart_policy'),
        ('stop-signal', 'stop_signal'),
    )

    def __init__(self, name, tag=None, registry=None):
        parsed_registry, parsed_name, parsed_tag = self._parse_image_name(name)
        self.name = parsed_name
        self.tag = tag or parsed_tag or 'latest'
        self.registry = registry or parsed_registry

    def __str__(self):
        if 'id' in vars(self):
            return str(self.id)
        if self.registry:
            return '{registry}/{name}:{tag}'.format(
                registry=self.registry,
                name=self.name,
                tag=self.tag,
            )
        return '{name}:{tag}'.format(name=self.name, tag=self.tag)

    def __get__(self, container, container_cls):
        if container is None:
            return self
        field_name = self._get_field_name(container_cls)
        image = container.__dict__[field_name] = self.__class__(
            name=self.name,
            tag=self.tag,
        )
        image.id = container.info['Image']
        return image

    def __getitem__(self, item):
        if isinstance(item, slice):
            registry, tag = item.start, item.stop
        else:
            registry, tag = None, item
        return self.__class__(
            name=self.name,
            tag=tag or self.tag,
            registry=registry or self.registry,
        )

    def _get_field_name(self, container_cls):
        for attr in dir(container_cls):
            if getattr(container_cls, attr) is self:
                return attr

    @staticmethod
    def _parse_image_name(image):
        repository, tag = docker_utils.parse_repository_tag(image)
        registry, name = docker_auth.resolve_repository_name(repository)
        if registry == docker_auth.INDEX_NAME:
            registry = ''
        return registry, name, tag

    @classmethod
    def make_container_options(cls, temporary=None, name=None, options=()):
        options = dict(options)
        container_options = Options()
        for remap, option in cls.container_options_mapping:
            container_options[remap] = options.pop(option, None)
        container_options.update(
            (
                ('name', name),
                ('rm', temporary),
                ('tty', temporary),
                ('detach', temporary is not None and not temporary),
            ),
            **options
        )
        return container_options

    @property
    def info(self):
        command = 'docker inspect --type image {image}'
        info = fabricio.run(command.format(image=self))
        return json.loads(str(info))[0]

    @default_property
    def id(self):
        return self.info.get('Id')

    def delete(self, force=False, ignore_errors=False):
        command = 'docker rmi {force}{image}'
        force = force and '--force ' or ''
        fabricio.run(
            command.format(image=self.id, force=force),
            ignore_errors=ignore_errors,
        )

    def run(
        self,
        cmd=None,
        temporary=True,
        quiet=True,
        name=None,
        options=(),
        **kwargs
    ):
        if kwargs:
            warnings.warn(
                'Container options must be provided in `options` arg, '
                'kwargs behavior will be removed in v0.4',
                category=RuntimeWarning, stacklevel=2,
            )
            options = dict(options, **kwargs)
        command = 'docker run {options} {image} {cmd}'
        return fabricio.run(
            command.format(
                image=self,
                cmd=cmd or '',
                options=self.make_container_options(
                    temporary=temporary,
                    name=name,
                    options=options,
                ),
            ),
            quiet=quiet,
        )
