import time

import mock
import six
import unittest2 as unittest

from fabric import api as fab
from fabric.contrib import files

import fabricio

from fabricio.apps.db.postgres import postgresql
from fabricio import docker


class TestContainer(postgresql.PostgresqlContainer):

    image = docker.Image('image:tag')

    postgresql_conf = 'postgresql.conf'

    pg_hba_conf = 'pg_hba.conf'

    data = '/data'


class PostgresqlContainerTestCase(unittest.TestCase):

    def setUp(self):
        postgresql.open = mock.MagicMock()
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        postgresql.open = open
        self.fab_settings.__exit__(None, None, None)

    @mock.patch.object(fab, 'get')
    @mock.patch.object(fab, 'put')
    @mock.patch.object(time, 'sleep')
    def test_update(self, *args):
        cases = dict(
            updated_without_config_change=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
            ),
            no_change_at_all=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(),
                update_returns=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
            ),
            with_tag=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(tag='tag'),
                update_returns=False,
                expected_update_kwargs=dict(force=False, tag='tag', registry=None),
            ),
            custom_registry=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(registry='registry'),
                update_returns=False,
                expected_update_kwargs=dict(force=False, tag=None, registry='registry'),
            ),
            forced=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(force=True),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None, registry=None),
            ),
            not_updated_pg_hba_changed=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                    mock.call('docker kill --signal HUP name'),
                ],
                update_kwargs=dict(),
                update_returns=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
            ),
            main_conf_changed=dict(
                pg_exists=True,
                old_configs=[
                    'old_postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None, registry=None),
            ),
            configs_changed=dict(
                pg_exists=True,
                old_configs=[
                    'old_postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None, registry=None),
            ),
            from_scratch=dict(
                pg_exists=False,
                old_configs=[
                    'old_postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('docker run --name name --stop-signal INT --detach image:tag ', quiet=True),
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None, registry=None),
            ),
            from_scratch_with_custom_tag_and_registry=dict(
                pg_exists=False,
                old_configs=[
                    'old_postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('docker run --name name --stop-signal INT --detach registry/image:foo ', quiet=True),
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(tag='foo', registry='registry'),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag='foo', registry='registry'),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                postgresql.open.side_effect = (
                    six.StringIO('postgresql.conf'),
                    six.StringIO('pg_hba.conf'),
                )
                container = TestContainer(name='name')
                with mock.patch.object(
                    fabricio,
                    'run',
                ) as run:
                    with mock.patch.object(
                        files,
                        'exists',
                        return_value=data['pg_exists'],
                    ):
                        with mock.patch.object(
                            docker.Container,
                            'update',
                            return_value=data['update_returns'],
                        ) as update:
                            with mock.patch.object(
                                six.StringIO,
                                'getvalue',
                                side_effect=data['old_configs'],
                            ):
                                container.update(**data['update_kwargs'])
                                run.assert_has_calls(data['expected_commands'])
                                self.assertEqual(
                                    len(data['expected_commands']),
                                    run.call_count,
                                )
                                update.assert_called_once_with(**data['expected_update_kwargs'])

    def test_revert(self):
        expected_commands = [
            mock.call(
                'mv /data/postgresql.conf.backup /data/postgresql.conf',
                ignore_errors=True,
                sudo=True,
            ),
            mock.call(
                'mv /data/pg_hba.conf.backup /data/pg_hba.conf',
                ignore_errors=True,
                sudo=True,
            ),
        ]
        with mock.patch.object(fabricio, 'run') as run:
            with mock.patch.object(docker.Container, 'revert') as revert:
                container = TestContainer(name='name')
                container.revert()
                run.assert_has_calls(expected_commands)
                self.assertEqual(len(expected_commands), run.call_count)
                revert.assert_called_once()

    def test_backup(self):
        cases = dict(
            not_implemented=dict(
                expected_commands=[],
                container_class_attributes=dict(db_backup_enabled=True),
            ),
            default=dict(
                expected_commands=[
                    mock.call('docker exec --tty --interactive name pg_dump --username postgres --if-exists --create --clean --format c --jobs 1 --file /data/backup/postgres/backup.dump', ignore_errors=False, quiet=False),
                ],
                container_class_attributes=dict(
                    db_backup_folder='/data/backup/postgres',
                    db_backup_name='backup.dump',
                    db_backup_enabled=True,
                ),
            ),
            disabled=dict(
                expected_commands=[],
                container_class_attributes=dict(
                    db_backup_folder='/data/backup/postgres',
                    db_backup_name='backup.dump',
                ),
            ),
            regular=dict(
                expected_commands=[
                    mock.call('docker exec --tty --interactive name pg_dump --username user --host localhost --port 5432 --if-exists --create --clean --format t --dbname test_db --compress 9 --jobs 2 --file /data/backup/postgres/backup.dump', ignore_errors=False, quiet=False),
                ],
                container_class_attributes=dict(
                    db_backup_folder='/data/backup/postgres',
                    db_backup_name='backup.dump',
                    db_user='user',
                    db_host='localhost',
                    db_port=5432,
                    db_name='test_db',
                    db_backup_format='t',
                    db_backup_compress_level=9,
                    db_backup_workers=2,
                    db_backup_enabled=True,
                ),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                Container = type(
                    'TestContainer',
                    (postgresql.PostgresqlBackupMixin, ),
                    data['container_class_attributes'],
                )
                container = Container(name='name')
                with mock.patch.object(fabricio, 'run') as run:
                    container.backup()
                    run.assert_has_calls(data['expected_commands'])
                    self.assertEqual(
                        len(data['expected_commands']),
                        run.call_count,
                    )

    def test_restore(self):
        cases = dict(
            default=dict(
                expected_commands=[
                    mock.call('docker exec --tty --interactive name pg_restore --username postgres --if-exists --create --clean --dbname template1 --jobs 4 --file /data/backup/postgres/backup.dump', ignore_errors=False, quiet=False),
                ],
                container_class_attributes=dict(
                    db_backup_folder='/data/backup/postgres',
                ),
            ),
            regular=dict(
                expected_commands=[
                    mock.call('docker exec --tty --interactive name pg_restore --username user --host localhost --port 5432 --if-exists --create --clean --dbname template1 --jobs 2 --file /data/backup/postgres/backup.dump', ignore_errors=False, quiet=False),
                ],
                container_class_attributes=dict(
                    db_backup_folder='/data/backup/postgres',
                    db_backup_name='backup.dump',
                    db_user='user',
                    db_host='localhost',
                    db_port=5432,
                    db_name='test_db',
                    db_backup_format='t',
                    db_restore_workers=2,
                ),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                Container = type(
                    'TestContainer',
                    (postgresql.PostgresqlBackupMixin, ),
                    data['container_class_attributes'],
                )
                container = Container(name='name')
                with mock.patch.object(fabricio, 'run') as run:
                    container.restore(backup_name='backup.dump')
                    run.assert_has_calls(data['expected_commands'])
                    self.assertEqual(
                        len(data['expected_commands']),
                        run.call_count,
                    )

    def test_restore_raises_error_if_db_backup_folder_not_set(self):
        container = postgresql.PostgresqlBackupMixin(name='name')
        with self.assertRaises(NotImplementedError):
            container.restore(backup_name='backup.dump')

    def test_restore_raises_error_if_backup_name_not_provided(self):
        class Container(postgresql.PostgresqlBackupMixin):
            db_backup_folder = '/data/backup/postgres'

        container = Container(name='name')
        with self.assertRaises(ValueError):
            container.restore()
