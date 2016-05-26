import json

import fabricio

from fabricio.utils import writeable_property, Options


class Image(object):

    def __init__(self, name=None, tag=None):
        forced_tag = tag
        self.name, _, tag = name and str(name).partition(':') or [None] * 3
        self.tag = forced_tag or tag or 'latest'

    def __str__(self):
        if 'id' in vars(self):
            return str(self.id)
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

    def __getitem__(self, tag):
        return self.__class__(name=self.name, tag=tag or self.tag)

    def _get_field_name(self, container_cls):
        for attr in dir(container_cls):
            if getattr(container_cls, attr) is self:
                return attr

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

    @writeable_property
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
