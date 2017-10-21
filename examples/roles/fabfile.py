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


@tasks.infrastructure
def localhost():
    # monkeypatching `run` method to be able to run docker commands
    # on localhost instead of remote server
    fabricio.run = functools.partial(fabricio.local, capture=True)

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
