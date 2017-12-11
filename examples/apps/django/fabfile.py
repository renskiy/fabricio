from fabricio import tasks
from fabricio.apps.python.django import DjangoContainer
from fabricio.misc import AvailableVagrantHosts

django = tasks.ImageBuildDockerTasks(
    service=DjangoContainer(
        name='django',
        image='django',
        options={
            'publish': '8000:8000',
            'stop-signal': 'INT',
            'volume': '/data/django:/data',
            'env': 'DJANGO_SETTINGS_MODULE=settings',
        },
    ),
    hosts=AvailableVagrantHosts(),
    registry='localhost:5000',
    ssh_tunnel='5000:5000',
)
