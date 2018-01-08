from fabricio import tasks
from fabricio.apps.db.postgres import StreamingReplicatedPostgresqlContainer
from fabricio.misc import AvailableVagrantHosts

db = tasks.DockerTasks(
    service=StreamingReplicatedPostgresqlContainer(
        name='postgres',
        image='postgres:10-alpine',
        pg_data='/data',
        pg_recovery_master_promotion_enabled=True,
        sudo=True,
        options=dict(
            volume='/data:/data',
            env='PGDATA=/data',
            publish='5432:5432',
        ),
    ),
    hosts=AvailableVagrantHosts(guest_network_interface='eth1'),
    destroy_command=True,
)
