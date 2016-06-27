import functools
import os
import types
import weakref

import six

from fabric import api as fab, colors
from fabric.contrib import console
from fabric.main import is_task_object
from fabric.network import needs_host
from fabric.tasks import WrappedCallableTask

import fabricio

from fabricio import docker, utils


class IgnoreHostsTask(WrappedCallableTask):

    hosts = roles = property(lambda self: (), lambda self, value: None)


class Registry(str):

    def __init__(self, *args, **kwargs):
        super(Registry, self).__init__(*args, **kwargs)
        self.host, _, port = self.partition(':')
        self.port = port and int(port)


def infrastructure(
    confirm=True,
    color=colors.yellow,
    autoconfirm_env_var='FABRICIO_INFRASTRUCTURE_AUTOCONFIRM',
):
    def _decorator(task):
        @functools.wraps(task)
        def _task(*args, **kwargs):
            if confirm:
                confirmed = utils.yes(os.environ.get(autoconfirm_env_var, 0))
                if not confirmed and not console.confirm(
                    'Are you sure you want to select {infrastructure} '
                    'infrastructure to run task(s) on?'.format(
                        infrastructure=color(task.__name__),
                    ),
                    default=False,
                ):
                    fab.abort('Aborted')
            fab.env.infrastructure = task.__name__
            return task(*args, **kwargs)
        return fab.task(_task)
    fab.env.setdefault('infrastructure', None)
    if callable(confirm):
        func, confirm = confirm, six.get_function_defaults(infrastructure)[0]
        return _decorator(func)
    return _decorator


class Tasks(object):

    @property
    def __name__(self):
        return self

    __class__ = types.ModuleType

    def __new__(cls, **kwargs):
        self = object.__new__(cls)
        _self = weakref.proxy(self)
        for attr in dir(cls):
            attr_value = getattr(cls, attr)
            if is_task_object(attr_value):
                task_decorator = fab.task(
                    default=attr_value.is_default,
                    name=attr_value.name,
                    aliases=attr_value.aliases,
                    task_class=attr_value.__class__,
                )
                task = task_decorator(functools.wraps(attr_value.wrapped)(
                    # TODO fix Fabric's --display option
                    functools.partial(attr_value.wrapped, _self),
                ))
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
        registry=None,
        migrate_commands=False,
        backup_commands=False,
        **kwargs
    ):
        super(DockerTasks, self).__init__(**kwargs)
        self.registry = registry and Registry(registry)
        self.container = container  # type: docker.Container
        self.backup.use_task_objects = backup_commands
        self.restore.use_task_objects = backup_commands
        self.migrate.use_task_objects = migrate_commands
        self.migrate_back.use_task_objects = migrate_commands

    @property
    def image(self):
        return self.container.__class__.image

    @fab.task
    def revert(self):
        """
        revert - revert Docker container to previous version
        """
        self.container.revert()

    @fab.task
    @fab.serial
    def migrate(self, tag=None):
        """
        migrate[:tag=None] - apply migrations
        """
        self.container.migrate(tag=tag, registry=self.registry)

    @fab.task
    @fab.serial
    def migrate_back(self):
        """
        migrate_back - remove applied migrations returning to previous state
        """
        self.container.migrate_back()

    @fab.task(task_class=IgnoreHostsTask)
    def rollback(self, migrate_back=True):
        """
        rollback[:migrate_back=yes] - migrate_back -> revert
        """
        if utils.yes(migrate_back):
            fab.execute(self.migrate_back)
        fab.execute(self.revert)

    @fab.task
    @fab.serial
    def backup(self):
        """
        backup - backup data
        """
        self.container.backup()

    @fab.task
    @fab.serial
    def restore(self):
        """
        restore - restore data
        """
        self.container.restore()

    @fab.task
    def pull(self, tag=None):
        """
        pull[:tag=None] - pull Docker image from registry
        """
        fabricio.run('docker pull {image}'.format(
            image=self.image[self.registry:tag],
        ))

    @fab.task
    def update(self, force=False, tag=None):
        """
        update[:force=no,tag=None] - recreate Docker container
        """
        self.container.update(
            force=utils.yes(force),
            tag=tag,
            registry=self.registry,
        )

    @fab.task(default=True, task_class=IgnoreHostsTask)
    def deploy(self, force=False, tag=None, migrate=True, backup=True):
        """
        deploy[:force=no,tag=None,migrate=yes,backup=yes] - backup -> pull -> migrate -> update
        """
        if utils.yes(backup):
            fab.execute(self.backup)
        fab.execute(self.pull, tag=tag)
        if utils.yes(migrate):
            fab.execute(self.migrate, tag=tag)
        fab.execute(self.update, force=force, tag=tag)


class PullDockerTasks(DockerTasks):

    def __init__(self, registry='localhost:5000', local_registry='localhost:5000', **kwargs):
        super(PullDockerTasks, self).__init__(registry=registry, **kwargs)
        self.local_registry = Registry(local_registry)

    @fab.task(task_class=IgnoreHostsTask)
    def push(self, tag=None):
        """
        push[:tag=None] - push Docker image to registry
        """
        local_tag = str(self.image[self.local_registry:tag])
        fabricio.local(
            'docker tag {image} {tag}'.format(
                image=self.image[tag],
                tag=local_tag,
            ),
            use_cache=True,
        )
        fabricio.local(
            'docker push {tag}'.format(tag=local_tag),
            quiet=False,
            use_cache=True,
        )
        fabricio.local(
            'docker rmi {tag}'.format(tag=local_tag),
            use_cache=True,
        )

    @fab.task
    @needs_host
    def pull(self, tag=None):
        """
        pull[:tag=None] - pull Docker image from registry
        """
        with fab.remote_tunnel(
            remote_port=self.registry.port,
            local_port=self.local_registry.port,
            local_host=self.local_registry.host,
        ):
            fabricio.run('docker pull {image}'.format(
                image=self.image[self.registry:tag]),
            )

    @fab.task(task_class=IgnoreHostsTask)
    def prepare(self, tag=None):
        """
        prepare[:tag=None] - prepare Docker image
        """
        fabricio.local(
            'docker pull {image}'.format(image=self.image[tag]),
            quiet=False,
            use_cache=True,
        )

    @fab.task(default=True, task_class=IgnoreHostsTask)
    def deploy(self, force=False, tag=None, *args, **kwargs):
        """
        deploy[:force=no,tag=None,migrate=yes,backup=yes] - prepare -> push -> backup -> pull -> migrate -> update
        """
        fab.execute(self.prepare, tag=tag)
        fab.execute(self.push, tag=tag)
        DockerTasks.deploy(self, force=force, tag=tag, *args, **kwargs)


class BuildDockerTasks(PullDockerTasks):

    def __init__(self, build_path='.', **kwargs):
        super(BuildDockerTasks, self).__init__(**kwargs)
        self.build_path = build_path

    @fab.task(task_class=IgnoreHostsTask)
    def prepare(self, tag=None):
        """
        prepare[:tag=None] - prepare Docker image
        """
        fabricio.local(
            'docker build --tag {tag} {build_path}'.format(
                tag=self.image[tag],
                build_path=self.build_path,
            ),
            quiet=False,
            use_cache=True,
        )
