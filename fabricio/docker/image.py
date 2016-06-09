import json

import fabricio

from fabricio.utils import default_property, Options


class Image(object):

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
        registry, _, name_with_tag = image.rpartition('/')
        name, _, tag = name_with_tag.partition(':')
        return registry, name, tag

    @staticmethod
    def make_container_options(
        temporary=None,
        name=None,
        user=None,
        ports=None,
        env=None,
        volumes=None,
        links=None,
        hosts=None,
        network=None,
        restart_policy=None,
        stop_signal=None,
        options=None,
    ):
        options = Options(options or ())
        options.update((
            ('name', name),
            ('user', user),
            ('publish', ports),
            ('env', env),
            ('volume', volumes),
            ('link', links),
            ('add-host', hosts),
            ('net', network),
            ('restart', restart_policy),
            ('stop-signal', stop_signal),
            ('rm', temporary),
            ('tty', temporary),
            ('detach', temporary is not None and not temporary),
        ))
        return options

    @property
    def info(self):
        command = 'docker inspect --type image {image}'
        info = fabricio.sudo(command.format(image=self))
        return json.loads(str(info))[0]

    @default_property
    def id(self):
        return self.info.get('Id')

    def delete(self, force=False, ignore_errors=False):
        command = 'docker rmi {force}{image}'
        force = force and '--force ' or ''
        fabricio.sudo(
            command.format(image=self.id, force=force),
            ignore_errors=ignore_errors,
        )

    def run(
        self,
        cmd=None,
        temporary=True,
        name=None,
        user=None,
        ports=None,
        env=None,
        volumes=None,
        links=None,
        hosts=None,
        network=None,
        restart_policy=None,
        stop_signal=None,
        options=None,
    ):
        command = 'docker run {options} {image} {cmd}'
        return fabricio.sudo(command.format(
            image=self,
            cmd=cmd or '',
            options=self.make_container_options(
                temporary=temporary,
                name=name,
                user=user,
                ports=ports,
                env=env,
                volumes=volumes,
                links=links,
                hosts=hosts,
                network=network,
                restart_policy=restart_policy,
                stop_signal=stop_signal,
                options=options,
            ),
        ))
