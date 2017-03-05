from fabric import api as fab
from fabricio import tasks, docker
from fabricio.misc import AvailableVagrantHosts

fab.env.roledefs.update(
    # you can set default roles definitions here
    web=['localhost'],
)


@tasks.infrastructure
def vagrant():
    fab.env.update(
        roledefs={
            'web': AvailableVagrantHosts(),
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
