import functools

import fabricio

from fabric import api as fab
from fabricio import tasks, docker
from fabricio.misc import AvailableVagrantHosts

fab.env.roledefs.update(
    # you can set default roles definitions here
    web=[],
)


@tasks.infrastructure
def vagrant():
    fab.env.update(
        roledefs={
            'web': AvailableVagrantHosts(),
        },
    )


@fab.task(name='monkey-patch')
def monkey_patch():
    """
    apply monkey patch
    """
    # replace fabricio.run by fabricio.local to run all commands on localhost
    fabricio.run = functools.partial(fabricio.local, capture=True)

    # uncomment row below to disable file uploading (e.g. docker-compose.yml)
    # fab.put = lambda *args, **kwargs: None


@tasks.infrastructure
def localhost():
    fab.env.update(
        roledefs={
            'web': ['localhost'],
        },
    )


nginx = tasks.DockerTasks(
    service=docker.Container(
        name='nginx',
        image='nginx:stable-alpine',
        options=dict(
            publish='80:80',
        ),
    ),
    roles=['web'],
)
