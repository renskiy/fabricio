import functools
import types
import weakref

from fabric import api as fab, colors
from fabric.contrib import console
from fabric.main import is_task_object
from fabric.network import needs_host

import fabricio

from fabricio import docker


def infrastructure(confirm=True, color=colors.yellow):
    def _decorator(task):
        @functools.wraps(task)
        def _task(*args, **kwargs):
            if confirm and console.confirm(
                'Are you sure you want to select {infrastructure} '
                'infrastructure to run task(s) on?'.format(
                    infrastructure=color(task.__name__),
                ),
                default=False,
            ):
                return task(*args, **kwargs)
            fab.abort('Aborted')
        return _task
    if callable(confirm):
        func, confirm = confirm, infrastructure.__defaults__[0]
        return _decorator(func)
    return _decorator


class Tasks(object):

    @property
    def __name__(self):
        return self

    __class__ = types.ModuleType

    def __new__(cls, **kwargs):
        self = object.__new__(cls)
        weak_self = weakref.proxy(self)
        for attr in dir(cls):
            attr_value = getattr(cls, attr)
            if is_task_object(attr_value):
                task_decorator = fab.task(
                    default=attr_value.is_default,
                    name=attr_value.name,
                    aliases=attr_value.aliases,
                )
                task = task_decorator(
                    functools.wraps(attr_value.wrapped)(
                        functools.partial(attr_value.wrapped, weak_self),
                    ),
                )
                setattr(self, attr, task)
        return self

    def __init__(self, roles=(), hosts=(), create_default_roles=True):
        if create_default_roles:
            for role in roles:
                fab.env.roledefs.setdefault(role, [])
        for task in self:
            task.roles = roles
            task.hosts = hosts

    def __iter__(self):
        for name, attr_value in vars(self).items():
            if is_task_object(attr_value):
                yield attr_value


class DockerTasks(Tasks):

    def __init__(
        self,
        container,
        roles=(),
        hosts=(),
        create_default_roles=True,
    ):
        super(DockerTasks, self).__init__(
            roles=roles,
            hosts=hosts,
            create_default_roles=create_default_roles,
        )
        self.container = container  # type: docker.Container

    @property
    def image(self):
        return self.container.__class__.image

    @fab.task
    def revert(self):
        """
        revert - revert Docker container to previous version
        """
        self.container.revert()

    @fab.task(default=True)
    def update(self, force='no', tag=None):
        """
        update[:force=no,tag=None] - recreate Docker container
        """
        fabricio.run('docker pull {image}'.format(image=self.image[tag]))
        self.container.update(force=force == 'yes', tag=tag)


class PullDockerTasks(DockerTasks):

    registry = 'localhost:5000'

    def __init__(
        self,
        container,
        local_registry='localhost:5000',
        roles=(),
        hosts=(),
        create_default_roles=True,
    ):
        super(PullDockerTasks, self).__init__(
            container=container,
            roles=roles,
            hosts=hosts,
            create_default_roles=create_default_roles,
        )
        registry_host, _, registry_port = local_registry.partition(':')
        self.local_registry_host = registry_host or 'localhost'
        self.local_registry_port = int(registry_port) or 5000

    @property
    def registry_port(self):
        return int(self.registry.split(':', 1)[1])

    @property
    def local_registry(self):
        return '{registry}:{port}'.format(
            registry=self.local_registry_host,
            port=self.local_registry_port,
        )

    @fab.task
    @needs_host
    def update(self, force='no', tag=None):
        """
        update[:force=no,tag=None] - recreate Docker container
        """
        with fab.remote_tunnel(
            remote_port=self.registry_port,
            local_port=self.local_registry_port,
            local_host=self.local_registry_host,
        ):
            fabricio.run('docker pull {image}'.format(
                image=self.image[self.registry:tag])
            )
            self.container.update(
                force=force == 'yes',
                tag=tag,
                registry=self.registry
            )

    @fab.task
    def push(self, local='yes', tag=None):
        """
        push[:local=yes,tag=None] - push Docker image to local (default) or original registry
        """
        registry = local == 'yes' and self.local_registry or None
        registry_tag = str(self.image[registry:tag])
        if registry:
            fabricio.local(
                'docker tag {image} {tag}'.format(
                    image=self.image[tag],
                    tag=registry_tag,
                ),
                use_cache=True,
            )
        fabricio.local(
            'docker push {tag}'.format(tag=registry_tag),
            quiet=False,
            use_cache=True,
        )

    @fab.task
    def pull(self, tag=None):
        """
        pull[:tag=None] - pull Docker image from original registry
        """
        fabricio.local(
            'docker pull {image}'.format(image=self.image[tag]),
            quiet=False,
            use_cache=True,
        )

    @fab.task(default=True)
    def deploy(self, force='no', tag=None):
        """
        deploy[:force=no,tag=None] - pull -> push -> update
        """
        self.pull(tag=tag)
        self.push(tag=tag)
        self.update(force=force, tag=tag)


class BuildDockerTasks(PullDockerTasks):

    def __init__(
        self,
        container,
        build_path='.',
        local_registry='localhost:5000',
        roles=(),
        hosts=(),
        create_default_roles=True,
    ):
        super(BuildDockerTasks, self).__init__(
            container=container,
            local_registry=local_registry,
            roles=roles,
            hosts=hosts,
            create_default_roles=create_default_roles,
        )
        self.build_path = build_path

    @fab.task
    def build(self, tag=None):
        """
        build[:tag=None] - build Docker image
        """
        fabricio.local(
            'docker build --tag {tag} {build_path}'.format(
                tag=self.image[tag],
                build_path=self.build_path,
            ),
            quiet=False,
            use_cache=True,
        )

    @fab.task(default=True)
    def deploy(self, force='no', tag=None):
        """
        deploy[:force=no,tag=None] - build -> push -> update
        """
        self.build(tag=tag)
        self.push(tag=tag)
        self.update(force=force, tag=tag)
