"""
https://github.com/renskiy/fabricio/blob/master/examples/service/kubernetes
"""

import fabricio

from fabric import api as fab
from fabricio import tasks, kubernetes
from fabricio.misc import AvailableVagrantHosts
from six.moves import filter

hosts = AvailableVagrantHosts(guest_network_interface='eth1')

service = tasks.DockerTasks(
    service=kubernetes.Configuration(
        name='my-service',
        options={
            # `kubectl apply` options
            'filename': 'configuration.yml',
        },
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


@fab.task(name='k8s-init')
@fab.serial
def k8s_init():
    """
    create Kubernetes cluster
    """
    def init():
        if not init.join_command:
            initialization = list(filter(None, fabricio.run(
                'kubeadm init '
                '--apiserver-advertise-address {0} '
                '--pod-network-cidr 10.244.0.0/16'
                ''.format(fab.env.host),
                sudo=True,
                quiet=False,
            ).splitlines()))
            init.join_command = initialization[-1].strip()

            # master setup
            fabricio.run('mkdir -p $HOME/.kube')
            fabricio.run('cp /etc/kubernetes/admin.conf /home/vagrant/.kube/config', sudo=True)
            fabricio.run('chown vagrant /home/vagrant/.kube/config', sudo=True)

            # install Kubernetes network plugin
            fabricio.run(
                'kubectl apply --filename /vagrant/kube-rbac.yml '
                '&& kubectl apply --filename /vagrant/kube-canal.yml --validate=false',
                quiet=False,
            )
        else:
            fabricio.run(init.join_command, quiet=False, sudo=True)

    init.join_command = None
    with fab.settings(hosts=hosts):
        fab.execute(init)


@fab.task(name='k8s-reset')
def k8s_reset():
    """
    reset Kubernetes cluster
    """
    def reset():
        fabricio.run('kubeadm reset --force', sudo=True, quiet=False)

    with fab.settings(hosts=hosts):
        fab.execute(reset)
