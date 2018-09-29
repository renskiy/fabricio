"""
https://github.com/renskiy/fabricio/blob/master/examples/build_image
"""

from fabricio import tasks, docker
from fabricio.misc import AvailableVagrantHosts

app = tasks.ImageBuildDockerTasks(
    service=docker.Container(
        name='app',
        image='service:v1.0',
        options={
            # `docker run` options
            'env': 'FOO=42',
        },
    ),
    registry='localhost:5000',
    ssh_tunnel='5000:5000',
    hosts=AvailableVagrantHosts(),

    # rollback_command=True,  # show `rollback` command in the list
    # migrate_commands=True,  # show `migrate` and `migrate-back` commands in the list
    # backup_commands=True,  # show `backup` and `restore` commands in the list
    # pull_command=True,  # show `pull` command in the list
    # update_command=True,  # show `update` command in the list
    # revert_command=True,  # show `revert` command in the list
    # destroy_command=True,  # show `destroy` command in the list

    prepare_command=True,  # show `prepare` command in the list
    push_command=True,  # show `push` command in the list
    upgrade_command=True,  # show `upgrade` command in the list
)
