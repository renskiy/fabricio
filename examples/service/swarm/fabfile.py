"""
https://github.com/renskiy/fabricio/blob/master/examples/service/swarm
"""

import fabricio

from fabric import api as fab
from fabricio import tasks, docker
from fabricio.misc import AvailableVagrantHosts

hosts = AvailableVagrantHosts(guest_network_interface='eth1')

service = tasks.DockerTasks(
    service=docker.Service(
        name='my-service',
        image='nginx:stable-alpine',
        options=dict(
            # `docker service create` options
            replicas=2,
            env='FOO=42',
        ),
    ),
    hosts=hosts,

    rollback_command=True,  # show `rollback` command in the list
    # migrate_commands=True,  # show `migrate` and `migrate-back` commands in the list
    # backup_commands=True,  # show `backup` and `restore` commands in the list
    # pull_command=True,  # show `pull` command in the list
    # update_command=True,  # show `update` command in the list
    # revert_command=True,  # show `revert` command in the list
    # destroy_command=True,  # show `destroy` command in the list
)


@fab.task(name='swarm-init')
@fab.serial
def swarm_init():
    """
    enable Docker swarm mode
    """
    def init():
        if not init.join_command:
            fabricio.run(
                'docker swarm init --advertise-addr {0}'.format(fab.env.host),
                ignore_errors=True,
                quiet=False,
            )
            join_token = fabricio.run(
                'docker swarm join-token --quiet manager',
                ignore_errors=True,
            )
            init.join_command = (
                'docker swarm join --token {join_token} {host}:2377'
            ).format(join_token=join_token, host=fab.env.host)
        else:
            fabricio.run(init.join_command, ignore_errors=True, quiet=False)

    init.join_command = None
    with fab.settings(hosts=hosts):
        fab.execute(init)


@fab.task(name='swarm-reset')
def swarm_reset():
    """
    enable Docker swarm mode
    """
    def reset():
        fabricio.run('docker swarm leave --force', ignore_errors=True, quiet=False)

    with fab.settings(hosts=hosts):
        fab.execute(reset)
