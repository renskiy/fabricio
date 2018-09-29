"""
https://github.com/renskiy/fabricio/blob/master/examples/hello_world
"""

from fabricio import tasks, docker
from fabricio.misc import AvailableVagrantHosts

app = tasks.DockerTasks(
    service=docker.Container(
        name='app',
        image='nginx:stable-alpine',
        options={
            # `docker run` options
            'env': 'FOO=42',
        },
    ),
    hosts=AvailableVagrantHosts(),

    rollback_command=True,  # show `rollback` command in the list
    # migrate_commands=True,  # show `migrate` and `migrate-back` commands in the list
    # backup_commands=True,  # show `backup` and `restore` commands in the list
    # pull_command=True,  # show `pull` command in the list
    # update_command=True,  # show `update` command in the list
    # revert_command=True,  # show `revert` command in the list
    # destroy_command=True,  # show `destroy` command in the list
)
