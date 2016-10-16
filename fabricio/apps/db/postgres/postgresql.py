import os
import time
import warnings

from datetime import datetime

import six

from fabric import api as fab
from fabric.contrib import files

import fabricio

from fabricio import docker
from fabricio.utils import Options


class PostgresqlBackupMixin(docker.Container):
    """
    Your Docker image must have pg_dump and pg_restore installed in order
    to run backup and restore respectively
    (usually this requires `postgresql-client-common` package for Ubuntu/Debian)
    """

    db_name = None

    db_user = 'postgres'

    db_host = None

    db_port = None

    db_backup_dir = None

    @property
    def db_backup_folder(self):
        warnings.warn(
            'db_backup_folder is deprecated and will be removed in ver. 0.4, '
            'use db_backup_dir instead', DeprecationWarning,
        )
        return None

    @property
    def db_backup_dir(self):
        warnings.warn(
            'db_backup_folder is deprecated and will be removed in ver. 0.4, '
            'use db_backup_dir instead', RuntimeWarning,
        )
        return self.db_backup_folder

    db_backup_format = 'c'

    db_backup_compress_level = None  # 0-9 (0 - no compression, 9 - max)

    db_backup_workers = 1

    @property
    def db_backup_name(self):
        warnings.warn(
            'db_backup_name is deprecated and will be removed in ver. 0.4, '
            'use db_backup_filename instead', DeprecationWarning,
        )
        return '{datetime:%Y-%m-%dT%H:%M:%S.%f}.dump'

    db_restore_workers = 4

    @property
    def db_backup_filename(self):
        warnings.warn(
            'db_backup_name is deprecated and will be removed in ver. 0.4, '
            'use db_backup_filename instead', RuntimeWarning,
        )
        return self.db_backup_name

    @property
    def db_connection_options(self):
        return Options([
            ('username', self.db_user),
            ('host', self.db_host),
            ('port', self.db_port),
        ])

    @property
    def db_backup_options(self):
        return Options([
            ('if-exists', True),
            ('create', True),
            ('clean', True),
        ])

    def make_backup_command(self):
        options = Options(self.db_connection_options)
        options.update(self.db_backup_options)
        options.update([
            ('format', self.db_backup_format),
            ('dbname', self.db_name),
            ('compress', self.db_backup_compress_level),
            ('jobs', self.db_backup_workers),
            ('file', os.path.join(
                self.db_backup_dir,
                self.db_backup_filename.format(datetime=datetime.utcnow())
            )),
        ])
        return 'pg_dump {options}'.format(options=options)

    def backup(self):
        if self.db_backup_dir is None:
            fab.abort('db_backup_dir not set, can\'t continue with backup')
        self.execute(self.make_backup_command(), quiet=False)

    @property
    def db_restore_options(self):
        return self.db_backup_options

    def make_restore_command(self, backup_filename):
        options = Options(self.db_connection_options)
        options.update(self.db_restore_options)
        options.update([
            ('dbname', 'template1'),  # use any existing DB
            ('jobs', str(self.db_restore_workers)),
            ('file', os.path.join(self.db_backup_dir, backup_filename)),
        ])
        return 'pg_restore {options}'.format(options=options)

    def restore(self, backup_filename=None):
        """
        Before run this method you have somehow to disable incoming connections,
        e.g. by stopping all database client containers:

            client_container.stop()
            pg_container.restore()
            client_container.start()
        """
        if self.db_backup_dir is None:
            fab.abort('db_backup_dir not set, can\'t continue with restore')

        if backup_filename is None:
            raise ValueError('backup_filename not provided')

        command = self.make_restore_command(backup_filename)
        self.execute(command, quiet=False)


class PostgresqlContainer(docker.Container):

    @property
    def postgresql_conf(self):
        warnings.warn(
            'postgresql_conf is deprecated and will be removed in ver. 0.4, '
            'use pg_conf instead', DeprecationWarning,
        )
        return NotImplemented

    @property
    def pg_conf(self):
        warnings.warn(
            'postgresql_conf is deprecated and will be removed in ver. 0.4, '
            'use pg_conf instead', RuntimeWarning,
        )
        return self.postgresql_conf

    @property
    def pg_hba_conf(self):
        warnings.warn(
            'pg_hba_conf is deprecated and will be removed in ver. 0.4, '
            'use pg_hba instead', DeprecationWarning,
        )
        return NotImplemented

    @property
    def pg_hba(self):
        warnings.warn(
            'pg_hba_conf is deprecated and will be removed in ver. 0.4, '
            'use pg_hba instead', RuntimeWarning,
        )
        return self.pg_hba_conf

    @property
    def data(self):
        warnings.warn(
            'data is deprecated and will be removed in ver. 0.4, '
            'use pg_data instead', DeprecationWarning,
        )
        return NotImplemented

    @property
    def pg_data(self):
        warnings.warn(
            'data is deprecated and will be removed in ver. 0.4, '
            'use pg_data instead', RuntimeWarning,
        )
        return self.data

    stop_signal = 'INT'

    stop_timeout = 30

    @staticmethod
    def update_config(content, path):
        old_file = six.BytesIO()
        fab.get(remote_path=path, local_path=old_file, use_sudo=True)
        old_content = old_file.getvalue()
        fabricio.run(
            'mv {path_from} {path_to}'.format(
                path_from=path,
                path_to=path + '.backup',
            ),
            sudo=True,
        )
        fab.put(six.BytesIO(content), path, use_sudo=True, mode='0644')
        return content != old_content

    def update(self, force=False, tag=None, registry=None):
        if not files.exists(
            os.path.join(self.pg_data, 'PG_VERSION'),
            use_sudo=True,
        ):
            fabricio.log('PostgreSQL database not found, creating new...')
            self.run(tag=tag, registry=registry)
            time.sleep(10)  # wait until all data prepared during first start

        main_config_changed = self.update_config(
            content=open(self.pg_conf).read(),
            path=os.path.join(self.pg_data, 'postgresql.conf'),
        )
        hba_config_changed = self.update_config(
            content=open(self.pg_hba).read(),
            path=os.path.join(self.pg_data, 'pg_hba.conf'),
        )
        force = force or main_config_changed
        updated = super(PostgresqlContainer, self).update(
            force=force,
            tag=tag,
            registry=registry,
        )
        if not updated and hba_config_changed:
            self.signal('HUP')  # reload configs
        return updated

    def revert(self):
        main_conf = os.path.join(self.pg_data, 'postgresql.conf')
        hba_conf = os.path.join(self.pg_data, 'pg_hba.conf')
        fabricio.run(
            'mv {path_from} {path_to}'.format(
                path_from=main_conf + '.backup',
                path_to=main_conf,
            ),
            ignore_errors=True,
            sudo=True,
        )
        fabricio.run(
            'mv {path_from} {path_to}'.format(
                path_from=hba_conf + '.backup',
                path_to=hba_conf,
            ),
            ignore_errors=True,
            sudo=True,
        )
        super(PostgresqlContainer, self).revert()
