import fabricio

from fabric import api as fab
from fabricio import tasks, kubernetes
from fabricio.misc import AvailableVagrantHosts
from six.moves import filter

hosts = AvailableVagrantHosts(guest_network_interface='eth1')


@fab.task(name='kubernetes-init')
@fab.serial
def kubernetes_init():
    """
    create Kubernetes cluster
    """
    def _kubernetes_init():
        if not getattr(kubernetes_init, 'join_command', None):
            initialization = list(filter(None, fabricio.run(
                'kubeadm init '
                '--apiserver-advertise-address {0} '
                '--pod-network-cidr 10.244.0.0/16'
                ''.format(fab.env.host),
                sudo=True,
                quiet=False,
            ).splitlines()))
            kubernetes_init.join_command = initialization[-1].strip()

            # master setup
            fabricio.run('mkdir -p $HOME/.kube')
            fabricio.run('cp /etc/kubernetes/admin.conf /home/vagrant/.kube/config', sudo=True)
            fabricio.run('chown vagrant /home/vagrant/.kube/config', sudo=True)

            # install Kubernetes network plugin
            fabricio.run(
                'kubectl apply --filename /vagrant/kube-rbac.yml '
                '&& kubectl apply --filename /vagrant/kube-canal.yml',
                quiet=False,
            )
        else:
            fabricio.run(kubernetes_init.join_command, quiet=False, sudo=True)
    with fab.settings(hosts=hosts):
        fab.execute(_kubernetes_init)


k8s = tasks.DockerTasks(
    service=kubernetes.Configuration(
        name='k8s',
        options={'filename': 'k8s.yml'},
    ),
    hosts=hosts,
    destroy_command=True,
)
