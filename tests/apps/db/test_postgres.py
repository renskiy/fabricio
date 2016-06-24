import time

from StringIO import StringIO

import mock
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
                    StringIO('postgresql.conf'),
                    StringIO('pg_hba.conf'),
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
                                StringIO,
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

    @unittest.skip('PostgresqlContainer.backup() needs to be reworked')
    def test_backup(self):
        cases = dict(
            default=dict(
                expected_commands=[
                    mock.call(
                        'docker exec --tty name psql --username postgres --command "SELECT pg_start_backup(\'backup\');"',
                        ignore_errors=False,
                    ),
                    mock.call('tar --create --exclude postmaster.pid /data | gzip > backup.tar.gz', sudo=True),
                    mock.call(
                        'docker exec --tty name psql --username postgres --command "SELECT pg_stop_backup();"',
                        ignore_errors=False,
                    )
                ],
                backup_kwargs=dict(),
            ),
            username_overridden=dict(
                expected_commands=[
                    mock.call(
                        'docker exec --tty name psql --username user --command "SELECT pg_start_backup(\'backup\');"',
                        ignore_errors=False,
                    ),
                    mock.call('tar --create --exclude postmaster.pid /data | gzip > backup.tar.gz', sudo=True),
                    mock.call(
                        'docker exec --tty name psql --username user --command "SELECT pg_stop_backup();"',
                        ignore_errors=False,
                    )
                ],
                backup_kwargs=dict(username='user'),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container = TestContainer(name='name')
                with mock.patch.object(fabricio, 'run') as run:
                    container.backup('backup.tar.gz', **data['backup_kwargs'])
                    run.assert_has_calls(data['expected_commands'])
                    self.assertEqual(len(data['expected_commands']), run.call_count)

    @unittest.skip('PostgresqlContainer.restore() needs to be reworked')
    def test_restore(self):
        expected_commands = [
            mock.call('docker stop --time 30 name'),
            mock.call('gzip --decompress < backup.tar.gz | tar --extract --directory /data', sudo=True),
            mock.call('docker start name')
        ]
        container = TestContainer(name='name')
        with mock.patch.object(fabricio, 'run') as run:
            container.restore('backup.tar.gz')
            run.assert_has_calls(expected_commands)
            self.assertEqual(len(expected_commands), run.call_count)
