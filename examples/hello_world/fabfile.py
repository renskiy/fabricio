from fabricio import tasks, docker
from fabricio.misc import AvailableVagrantHosts

nginx = tasks.DockerTasks(
    service=docker.Container(
        name='nginx',
        image='nginx:stable-alpine',
        options=dict(
            publish='80:80',
        ),
    ),
    hosts=AvailableVagrantHosts(),
    destroy_command=True,
)
