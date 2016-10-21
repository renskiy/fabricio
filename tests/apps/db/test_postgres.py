import sys
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

    pg_conf = 'postgresql.conf'

    pg_hba = 'pg_hba.conf'

    pg_data = '/data'


class PostgresqlContainerTestCase(unittest.TestCase):

    def setUp(self):
        postgresql.open = mock.MagicMock()
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()
        self.stderr = sys.stderr
        sys.stderr = six.BytesIO()

    def tearDown(self):
        postgresql.open = open
        self.fab_settings.__exit__(None, None, None)
        sys.stderr = self.stderr

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
                expected_commands=[],
                update_kwargs=dict(),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=True,
            ),
            no_change_at_all=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=False,
            ),
            with_tag=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(tag='tag'),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag='tag', registry=None),
                expected_result=False,
            ),
            custom_registry=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(registry='registry'),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry='registry'),
                expected_result=False,
            ),
            forced=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(force=True),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=True, tag=None, registry=None),
                expected_result=True,
            ),
            pg_hba_changed=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                    mock.call('docker kill --signal HUP name'),
                ],
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=False,
            ),
            pg_hba_changed_container_updated=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                ],
                update_kwargs=dict(),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=True,
            ),
            main_conf_changed=dict(
                pg_exists=True,
                old_configs=[
                    'old_postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('docker restart --time 30 name'),
                ],
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=True,
            ),
            main_conf_changed_container_updated=dict(
                pg_exists=True,
                old_configs=[
                    'old_postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                ],
                update_kwargs=dict(),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=True,
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
                    mock.call('docker restart --time 30 name'),
                ],
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=True,
            ),
            configs_changed_container_updated=dict(
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
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=True,
            ),
            from_scratch=dict(
                pg_exists=False,
                old_configs=[
                    'old_postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('docker run --stop-signal INT --name name --detach image:tag ', quiet=True),
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                    mock.call('docker restart --time 30 name'),
                ],
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None),
                expected_result=True,
            ),
            from_scratch_with_custom_tag_and_registry=dict(
                pg_exists=False,
                old_configs=[
                    'old_postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('docker run --stop-signal INT --name name --detach registry/image:foo ', quiet=True),
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup', sudo=True),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup', sudo=True),
                    mock.call('docker restart --time 30 name'),
                ],
                update_kwargs=dict(tag='foo', registry='registry'),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag='foo', registry='registry'),
                expected_result=True,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                postgresql.open.side_effect = (
                    six.BytesIO('postgresql.conf'),
                    six.BytesIO('pg_hba.conf'),
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
                            return_value=data['parent_update_returned'],
                        ) as update:
                            with mock.patch.object(
                                six.BytesIO,
                                'getvalue',
                                side_effect=data['old_configs'],
                            ):
                                result = container.update(**data['update_kwargs'])
                                self.assertEqual(result, data['expected_result'])
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
            default=dict(
                expected_commands=[
                    mock.call(
                        'docker exec --tty --interactive name pg_dump --username postgres --if-exists --create --clean --format c --jobs 1 --file /data/backup/postgres/backup.dump',
                        ignore_errors=False, quiet=False, use_cache=False,
                    ),
                ],
                container_class_attributes=dict(
                    db_backup_dir='/data/backup/postgres',
                    db_backup_filename='backup.dump',
                ),
            ),
            regular=dict(
                expected_commands=[
                    mock.call(
                        'docker exec --tty --interactive name pg_dump --username user --host localhost --port 5432 --if-exists --create --clean --format t --dbname test_db --compress 9 --jobs 2 --file /data/backup/postgres/backup.dump',
                        ignore_errors=False, quiet=False, use_cache=False,
                    ),
                ],
                container_class_attributes=dict(
                    db_backup_dir='/data/backup/postgres',
                    db_backup_filename='backup.dump',
                    db_user='user',
                    db_host='localhost',
                    db_port=5432,
                    db_name='test_db',
                    db_backup_format='t',
                    db_backup_compress_level=9,
                    db_backup_workers=2,
                ),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container_type = type(
                    'TestContainer',
                    (postgresql.PostgresqlBackupMixin, ),
                    data['container_class_attributes'],
                )
                container = container_type(name='name')
                with mock.patch.object(fabricio, 'run') as run:
                    container.backup()
                    run.assert_has_calls(data['expected_commands'])
                    self.assertEqual(
                        len(data['expected_commands']),
                        run.call_count,
                    )

    def test_backup_raises_error_if_db_backup_dir_not_set(self):
        class AbortException(Exception):
            pass
        container = postgresql.PostgresqlBackupMixin(name='name')
        with fab.settings(abort_exception=AbortException):
            with self.assertRaises(AbortException):
                container.backup()

    def test_restore(self):
        cases = dict(
            default=dict(
                expected_commands=[
                    mock.call(
                        'docker exec --tty --interactive name pg_restore --username postgres --if-exists --create --clean --dbname template1 --jobs 4 --file /data/backup/postgres/backup.dump',
                        ignore_errors=False, quiet=False, use_cache=False,
                    ),
                ],
                container_class_attributes=dict(
                    db_backup_dir='/data/backup/postgres',
                ),
            ),
            regular=dict(
                expected_commands=[
                    mock.call(
                        'docker exec --tty --interactive name pg_restore --username user --host localhost --port 5432 --if-exists --create --clean --dbname template1 --jobs 2 --file /data/backup/postgres/backup.dump',
                        ignore_errors=False, quiet=False, use_cache=False,
                    ),
                ],
                container_class_attributes=dict(
                    db_backup_dir='/data/backup/postgres',
                    db_backup_filename='backup.dump',
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
                container_type = type(
                    'TestContainer',
                    (postgresql.PostgresqlBackupMixin, ),
                    data['container_class_attributes'],
                )
                container = container_type(name='name')
                with mock.patch.object(fabricio, 'run') as run:
                    container.restore(backup_filename='backup.dump')
                    run.assert_has_calls(data['expected_commands'])
                    self.assertEqual(
                        len(data['expected_commands']),
                        run.call_count,
                    )

    def test_restore_raises_error_if_db_backup_dir_not_set(self):
        class AbortException(Exception):
            pass
        container = postgresql.PostgresqlBackupMixin(name='name')
        with fab.settings(abort_exception=AbortException):
            with self.assertRaises(AbortException):
                container.restore(backup_filename='backup.dump')

    def test_restore_raises_error_if_backup_filename_not_provided(self):
        class Container(postgresql.PostgresqlBackupMixin):
            db_backup_dir = '/data/backup/postgres'

        container = Container(name='name')
        with self.assertRaises(ValueError):
            container.restore()
