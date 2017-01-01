import fabricio

from fabric import api as fab
from fabricio import tasks, docker
from fabricio.misc import AvailableVagrantHosts

hosts = AvailableVagrantHosts(guest_network_interface='eth1')


@fab.task(name='swarm-init')
@fab.serial
@fab.hosts('fake_host')
def swarm_init():
    def _swarm_init():
        if swarm_init.worker_join_command is None:
            fabricio.run(
                'docker swarm init --advertise-addr {0}'.format(fab.env.host),
                ignore_errors=True,
            )
            join_token = fabricio.run(
                'docker swarm join-token --quiet worker',
                ignore_errors=True,
            )
            swarm_init.worker_join_command = (
                'docker swarm join --token {join_token} {host}:2377'
            ).format(join_token=join_token, host=fab.env.host)
        else:
            fabricio.run(
                swarm_init.worker_join_command,
                ignore_errors=True,
            )
    with fab.settings(hosts=hosts):
        fab.execute(_swarm_init)

swarm_init.worker_join_command = None

nginx = tasks.DockerTasks(
    service=docker.Service(
        name='nginx',
        image='nginx:stable-alpine',
        options=dict(
            ports='80:80',
            replicas=2,
        ),
    ),
    hosts=hosts,
)
