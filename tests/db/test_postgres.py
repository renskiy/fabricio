import time

import fabric.api
import mock
import six
import unittest2 as unittest

from fabric.contrib import files

import fabricio

from fabricio.apps.db.postgres import postgresql
from fabricio import docker


class TestContainer(postgresql.PostgresqlContainer):

    image = docker.Image('image:tag')

    postgresql_conf = 'postgresql.conf'

    pg_hba_conf = 'pg_hba.conf'

    pg_data = '/data'


class PostgresqlContainerTestCase(unittest.TestCase):

    def setUp(self):
        postgresql.open = mock.MagicMock()

    def tearDown(self):
        postgresql.open = open

    @mock.patch.object(fabric.api, 'get')
    @mock.patch.object(fabric.api, 'put')
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
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=False, tag=None),
            ),
            no_change_at_all=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                ],
                update_kwargs=dict(),
                update_returns=False,
                expected_update_kwargs=dict(force=False, tag=None),
            ),
            with_tag=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                ],
                update_kwargs=dict(tag='tag'),
                update_returns=False,
                expected_update_kwargs=dict(force=False, tag='tag'),
            ),
            forced=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                ],
                update_kwargs=dict(force=True),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None),
            ),
            not_updated_pg_hba_changed=dict(
                pg_exists=True,
                old_configs=[
                    'postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                    mock.call('docker kill --signal HUP name'),
                ],
                update_kwargs=dict(),
                update_returns=False,
                expected_update_kwargs=dict(force=False, tag=None),
            ),
            main_conf_changed=dict(
                pg_exists=True,
                old_configs=[
                    'old_postgresql.conf',
                    'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None),
            ),
            configs_changed=dict(
                pg_exists=True,
                old_configs=[
                    'old_postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None),
            ),
            from_scratch=dict(
                pg_exists=False,
                old_configs=[
                    'old_postgresql.conf',
                    'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('docker run --name name --stop-signal INT --detach image:tag '),
                    mock.call('mv /data/postgresql.conf /data/postgresql.conf.backup'),
                    mock.call('mv /data/pg_hba.conf /data/pg_hba.conf.backup'),
                ],
                update_kwargs=dict(),
                update_returns=True,
                expected_update_kwargs=dict(force=True, tag=None),
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
                    'exec_command',
                ) as exec_command:
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
                                exec_command.assert_has_calls(data['expected_commands'])
                                self.assertEqual(
                                    len(data['expected_commands']),
                                    exec_command.call_count,
                                )
                                update.assert_called_once_with(**data['expected_update_kwargs'])

    def test_revert(self):
        expected_commands = [
            mock.call(
                'mv /data/postgresql.conf.backup /data/postgresql.conf',
                ignore_errors=True,
            ),
            mock.call(
                'mv /data/pg_hba.conf.backup /data/pg_hba.conf',
                ignore_errors=True,
            ),
        ]
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            with mock.patch.object(docker.Container, 'revert') as revert:
                container = TestContainer(name='name')
                container.revert()
                exec_command.assert_has_calls(expected_commands)
                self.assertEqual(len(expected_commands), exec_command.call_count)
                revert.assert_called_once()

    def test_backup(self):
        expected_commands = [
            mock.call(
                'docker exec --tty name psql -c "SELECT pg_start_backup(\'backup\');"',
                ignore_errors=False,
            ),
            mock.call('rsync --archive --exclude postmaster.pid /data /backup'),
            mock.call(
                'docker exec --tty name psql -c "SELECT pg_stop_backup();"',
                ignore_errors=False,
            )
        ]
        container = TestContainer(name='name')
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.backup('/backup')
            exec_command.assert_has_calls(expected_commands)
            self.assertEqual(len(expected_commands), exec_command.call_count)
