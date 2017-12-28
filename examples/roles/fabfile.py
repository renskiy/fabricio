import functools

import fabricio

from fabric import api as fab, colors
from fabricio import tasks, docker, utils
from fabricio.misc import AvailableVagrantHosts

fab.env.roledefs.update(
    # you can set default roles definitions here
    web=[],
)


@fabricio.infrastructure(color=colors.red)
def vagrant():
    fab.env.update(
        roledefs={
            'web': AvailableVagrantHosts(),
        },
    )


@fabricio.infrastructure
def localhost(force_local=False):
    if utils.strtobool(force_local):
        # replace fabricio.run by fabricio.local to run all commands locally
        fabricio.run = functools.partial(fabricio.local, capture=True)

        # uncomment row below to skip file uploading (e.g. docker-compose.yml)
        # fab.put = lambda *args, **kwargs: None

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
