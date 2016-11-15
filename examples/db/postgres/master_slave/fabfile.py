from fabricio import tasks
from fabricio.apps.db.postgres import StreamingReplicatedPostgresqlContainer
from fabricio.misc import AvailableVagrantHosts

db = tasks.DockerTasks(
    container=StreamingReplicatedPostgresqlContainer(
        name='postgres',
        image='postgres:9.6',
        pg_conf='postgresql.conf',
        pg_hba='pg_hba.conf',
        pg_data='/data',
        pg_recovery='recovery.conf',
        pg_recovery_revert_enabled=True,
        pg_recovery_master_promotion_enabled=True,
        pg_recovery_wait_for_master_seconds=10,
        options=dict(
            volumes='/data:/data',
            env='PGDATA=/data',
            ports='5432:5432',
        ),
    ),
    hosts=AvailableVagrantHosts(guest_network_interface='eth1'),
    registry='localhost:5000',
    ssh_tunnel_port=5000,
)
