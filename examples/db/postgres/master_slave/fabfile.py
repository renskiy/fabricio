"""
https://github.com/renskiy/fabricio/blob/master/examples/db/postgres/master_slave
"""

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
            # `docker run` options
            volume='/data:/data',
            env='PGDATA=/data',
            publish='5432:5432',
        ),
    ),
    hosts=AvailableVagrantHosts(guest_network_interface='eth1'),

    rollback_command=True,  # show `rollback` command in the list
    # migrate_commands=True,  # show `migrate` and `migrate-back` commands in the list
    # backup_commands=True,  # show `backup` and `restore` commands in the list
    # pull_command=True,  # show `pull` command in the list
    # update_command=True,  # show `update` command in the list
    # revert_command=True,  # show `revert` command in the list
    # destroy_command=True,  # show `destroy` command in the list
)
