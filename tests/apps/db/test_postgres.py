import shlex
import sys

from multiprocessing.synchronize import Event

import mock
import six
import unittest2 as unittest

from fabric import api as fab
from fabric.contrib import files

import fabricio

from fabricio.apps.db import postgres
from fabricio import docker
from tests import SucceededResult, FailedResult, docker_run_args_parser, \
    docker_inspect_args_parser, args_parser


class BytesIO(six.BytesIO):
    pass


class TestContainer(postgres.PostgresqlContainer):

    image = docker.Image('image:tag')

    pg_conf = 'postgresql.conf'

    pg_hba = 'pg_hba.conf'

    pg_data = '/data'


class PostgresqlBackupMixinTestCase(unittest.TestCase):

    maxDiff = None

    class BackupContainer(docker.Container, postgres.PostgresqlBackupMixin):
        pass

    class BackupService(docker.Service, postgres.PostgresqlBackupMixin):
        pass

    def setUp(self):
        self.stderr = sys.stderr
        sys.stderr = six.BytesIO()

    def tearDown(self):
        sys.stderr = self.stderr

    @mock.patch.object(docker.Service, 'is_manager', return_value=True)
    def test_backup(self, *args):
        cases = dict(
            container_default=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),
                    SucceededResult(),
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    docker_run_args_parser,
                ],
                init_kwargs=dict(
                    db_backup_dir='/data/backup/postgres',
                    db_backup_filename='backup.dump',
                ),
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'container',
                        'image_or_container': 'name',
                    },
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image_id',
                        'command': ['pg_dump', '--username=postgres', '--if-exists', '--create', '--clean', '--format=c', '--jobs=1', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                service_type=self.BackupContainer,
            ),
            service_default=dict(
                side_effect=(
                    SucceededResult('[{"Spec":{"TaskTemplate":{"ContainerSpec":{"Image":"image@digest"}}}}]'),
                    SucceededResult(),
                ),
                args_parsers=[
                    args_parser,
                    docker_run_args_parser,
                ],
                init_kwargs=dict(
                    db_backup_dir='/data/backup/postgres',
                    db_backup_filename='backup.dump',
                ),
                expected_args=[
                    dict(args=['docker', 'service', 'inspect', 'name']),
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image@digest',
                        'command': ['pg_dump', '--username=postgres', '--if-exists', '--create', '--clean', '--format=c', '--jobs=1', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                service_type=self.BackupService,
            ),
            container_regular=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),
                    SucceededResult(),
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    docker_run_args_parser,
                ],
                init_kwargs=dict(
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
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'container',
                        'image_or_container': 'name',
                    },
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image_id',
                        'command': ['pg_dump', '--username=user', '--host=localhost', '--port=5432', '--if-exists', '--create', '--clean', '--format=t', '--dbname=test_db', '--compress=9', '--jobs=2', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                service_type=self.BackupContainer,
            ),
            service_regular=dict(
                side_effect=(
                    SucceededResult('[{"Spec":{"TaskTemplate":{"ContainerSpec":{"Image":"image@digest"}}}}]'),
                    SucceededResult(),
                ),
                args_parsers=[
                    args_parser,
                    docker_run_args_parser,
                ],
                init_kwargs=dict(
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
                expected_args=[
                    dict(args=['docker', 'service', 'inspect', 'name']),
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image@digest',
                        'command': ['pg_dump', '--username=user', '--host=localhost', '--port=5432', '--if-exists', '--create', '--clean', '--format=t', '--dbname=test_db', '--compress=9', '--jobs=2', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                service_type=self.BackupService,
            ),
        )

        def test_command(command, *args, **kwargs):
            parser = next(args_parsers)
            options = parser.parse_args(shlex.split(command))
            self.assertDictEqual(vars(options), next(expected_args))
            return next(side_effect)
        for case, data in cases.items():
            expected_args = iter(data['expected_args'])
            args_parsers = iter(data['args_parsers'])
            side_effect = iter(data['side_effect'])
            with self.subTest(case=case):
                service = data['service_type'](
                    name='name',
                    image='image:tag',
                    **data['init_kwargs']
                )
                with mock.patch.object(fabricio, 'run', side_effect=test_command) as run:
                    fab.env.command = '{0}__{1}'.format(self, case)
                    service.backup()
                    self.assertEqual(run.call_count, len(data['side_effect']))

    @mock.patch.object(docker.Service, 'is_manager', return_value=True)
    def test_backup_raises_error_if_db_backup_dir_not_set(self, *args):
        class AbortException(Exception):
            pass
        cases = dict(
            container=self.BackupContainer,
            service=self.BackupService,
        )
        for case, service_type in cases.items():
            fab.env.command = '{0}__{1}'.format(self, case)
            with self.subTest(case=case):
                service = service_type(name='name')
                with fab.settings(abort_exception=AbortException):
                    with mock.patch.object(fab, 'abort', side_effect=AbortException):
                        with self.assertRaises(AbortException):
                            service.backup()

    @mock.patch.object(docker.Service, 'is_manager', return_value=True)
    def test_restore(self, *args):
        cases = dict(
            container_default=dict(
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'container',
                        'image_or_container': 'name',
                    },
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image_id',
                        'command': ['pg_restore', '--username=postgres', '--if-exists', '--create', '--clean', '--dbname=template1', '--jobs=4', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                args_parsers=[
                    docker_inspect_args_parser,
                    docker_run_args_parser,
                ],
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),
                    SucceededResult(),
                ),
                init_kwargs=dict(
                    db_backup_dir='/data/backup/postgres',
                ),
                service_type=self.BackupContainer,
            ),
            service_default=dict(
                expected_args=[
                    dict(args=['docker', 'service', 'inspect', 'name']),
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image@digest',
                        'command': ['pg_restore', '--username=postgres', '--if-exists', '--create', '--clean', '--dbname=template1', '--jobs=4', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                args_parsers=[
                    args_parser,
                    docker_run_args_parser,
                ],
                side_effect=(
                    SucceededResult('[{"Spec":{"TaskTemplate":{"ContainerSpec":{"Image":"image@digest"}}}}]'),
                    SucceededResult(),
                ),
                init_kwargs=dict(
                    db_backup_dir='/data/backup/postgres',
                ),
                service_type=self.BackupService,
            ),
            container_regular=dict(
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'container',
                        'image_or_container': 'name',
                    },
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image_id',
                        'command': ['pg_restore', '--username=user', '--host=localhost', '--port=5432', '--if-exists', '--create', '--clean', '--dbname=template1', '--jobs=2', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                args_parsers=[
                    docker_inspect_args_parser,
                    docker_run_args_parser,
                ],
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),
                    SucceededResult(),
                ),
                init_kwargs=dict(
                    db_backup_dir='/data/backup/postgres',
                    db_backup_filename='backup.dump',
                    db_user='user',
                    db_host='localhost',
                    db_port=5432,
                    db_name='test_db',
                    db_backup_format='t',
                    db_restore_workers=2,
                ),
                service_type=self.BackupContainer,
            ),
            service_regular=dict(
                expected_args=[
                    dict(args=['docker', 'service', 'inspect', 'name']),
                    {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'rm': True,
                        'tty': True,
                        'interactive': True,
                        'image': 'image@digest',
                        'command': ['pg_restore', '--username=user', '--host=localhost', '--port=5432', '--if-exists', '--create', '--clean', '--dbname=template1', '--jobs=2', '--file=/data/backup/postgres/backup.dump'],
                    },
                ],
                args_parsers=[
                    args_parser,
                    docker_run_args_parser,
                ],
                side_effect=(
                    SucceededResult('[{"Spec":{"TaskTemplate":{"ContainerSpec":{"Image":"image@digest"}}}}]'),
                    SucceededResult(),
                ),
                init_kwargs=dict(
                    db_backup_dir='/data/backup/postgres',
                    db_backup_filename='backup.dump',
                    db_user='user',
                    db_host='localhost',
                    db_port=5432,
                    db_name='test_db',
                    db_backup_format='t',
                    db_restore_workers=2,
                ),
                service_type=self.BackupService,
            ),
        )

        def test_command(command, *args, **kwargs):
            parser = next(args_parsers)
            options = parser.parse_args(shlex.split(command))
            self.assertDictEqual(vars(options), next(expected_args))
            return next(side_effect)
        for case, data in cases.items():
            expected_args = iter(data['expected_args'])
            args_parsers = iter(data['args_parsers'])
            side_effect = iter(data['side_effect'])
            with self.subTest(case=case):
                service = data['service_type'](
                    name='name',
                    image='image:tag',
                    **data['init_kwargs']
                )
                with mock.patch.object(fabricio, 'run', side_effect=test_command) as run:
                    fab.env.command = '{0}__{1}'.format(self, case)
                    service.restore(backup_name='backup.dump')
                    self.assertEqual(run.call_count, len(data['side_effect']))

    @mock.patch.object(docker.Service, 'is_manager', return_value=True)
    def test_restore_raises_error_if_db_backup_dir_not_set(self, *args):
        class AbortException(Exception):
            pass
        cases = dict(
            container=self.BackupContainer,
            service=self.BackupService,
        )
        for case, service_type in cases.items():
            fab.env.command = '{0}__{1}'.format(self, case)
            with self.subTest(case=case):
                service = service_type(name='name')
                with fab.settings(abort_exception=AbortException):
                    with mock.patch.object(fab, 'abort', side_effect=AbortException):
                        with self.assertRaises(AbortException):
                            service.restore(backup_name='backup.dump')

    @mock.patch.object(docker.Service, 'is_manager', return_value=True)
    def test_restore_raises_error_if_backup_filename_not_provided(self, *args):
        cases = dict(
            container=self.BackupContainer,
            service=self.BackupService,
        )
        for case, service_type in cases.items():
            fab.env.command = '{0}__{1}'.format(self, case)
            with self.subTest(case=case):
                service = service_type(
                    name='name',
                    db_backup_dir='/data/backup/postgres',
                )
                with self.assertRaises(ValueError):
                    service.restore()


class PostgresqlContainerTestCase(unittest.TestCase):

    def setUp(self):
        postgres.open = mock.MagicMock()
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()
        self.stderr = sys.stderr
        sys.stderr = six.BytesIO()

    def tearDown(self):
        postgres.open = open
        self.fab_settings.__exit__(None, None, None)
        sys.stderr = self.stderr

    @mock.patch('six.BytesIO', BytesIO)
    @mock.patch.object(fab, 'get')
    @mock.patch.object(fab, 'put')
    @mock.patch.object(postgres.PostgresqlContainer, 'create_db')
    @mock.patch.object(files, 'exists', return_value=True)
    def test_update(self, exists, create_db, *args):
        cases = dict(
            updated_without_config_change=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('rm -f /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('rm -f /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                ],
                update_kwargs=dict(),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            no_change=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=False,
            ),
            no_change_with_tag=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(tag='tag'),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag='tag', registry=None, account=None),
                expected_result=False,
            ),
            no_change_with_registry=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(registry='registry'),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry='registry', account=None),
                expected_result=False,
            ),
            no_change_with_account=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(account='account'),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account='account'),
                expected_result=False,
            ),
            no_change_with_tag_and_registry_and_account=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[],
                update_kwargs=dict(tag='tag', registry='registry', account='account'),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag='tag', registry='registry', account='account'),
                expected_result=False,
            ),
            forced=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('rm -f /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('rm -f /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                ],
                update_kwargs=dict(force=True),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=True, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            pg_hba_changed=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/pg_hba.conf /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('docker kill --signal HUP name'),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm --volumes name_backup'),
                    mock.call('docker rmi image_id', ignore_errors=True),
                    mock.call('rm -f /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult('[{"Image": "image_id"}]'),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                ),
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            pg_hba_changed_backup_container_not_found=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/pg_hba.conf /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('docker kill --signal HUP name'),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('rm -f /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                    docker.ContainerNotFoundError,
                    SucceededResult(),
                ),
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            pg_hba_changed_container_updated=dict(
                db_exists=True,
                old_configs=[
                    b'postgresql.conf',
                    b'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/pg_hba.conf /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('rm -f /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                ],
                update_kwargs=dict(),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            main_conf_changed=dict(
                db_exists=True,
                old_configs=[
                    b'old_postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/postgresql.conf /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('docker restart --time 30 name'),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm --volumes name_backup'),
                    mock.call('docker rmi image_id', ignore_errors=True),
                    mock.call('rm -f /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult('[{"Image": "image_id"}]'),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                ),
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            main_conf_changed_backup_container_not_found=dict(
                db_exists=True,
                old_configs=[
                    b'old_postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/postgresql.conf /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('docker restart --time 30 name'),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('rm -f /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                    docker.ContainerNotFoundError,
                    SucceededResult(),
                ),
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            main_conf_changed_container_updated=dict(
                db_exists=True,
                old_configs=[
                    b'old_postgresql.conf',
                    b'pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/postgresql.conf /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('rm -f /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                ],
                update_kwargs=dict(),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            configs_changed=dict(
                db_exists=True,
                old_configs=[
                    b'old_postgresql.conf',
                    b'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/postgresql.conf /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('docker restart --time 30 name'),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm --volumes name_backup'),
                    mock.call('docker rmi image_id', ignore_errors=True),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult('[{"Image": "image_id"}]'),
                    SucceededResult(),
                    SucceededResult(),
                ),
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            configs_changed_backup_container_not_found=dict(
                db_exists=True,
                old_configs=[
                    b'old_postgresql.conf',
                    b'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/postgresql.conf /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('docker restart --time 30 name'),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    docker.ContainerNotFoundError,
                ),
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            configs_changed_container_updated=dict(
                db_exists=True,
                old_configs=[
                    b'old_postgresql.conf',
                    b'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/postgresql.conf /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                ],
                update_kwargs=dict(),
                parent_update_returned=True,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
            ),
            from_scratch=dict(
                db_exists=False,
                old_configs=[
                    b'old_postgresql.conf',
                    b'old_pg_hba.conf',
                ],
                expected_commands=[
                    mock.call('mv -f /data/postgresql.conf /data/postgresql.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf /data/pg_hba.conf.backup', ignore_errors=True, sudo=True),
                    mock.call('docker restart --time 30 name'),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    docker.ContainerNotFoundError,
                ),
                update_kwargs=dict(),
                parent_update_returned=False,
                expected_update_kwargs=dict(force=False, tag=None, registry=None, account=None),
                expected_result=True,
                expected_db_creation=True,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                postgres.open.side_effect = (
                    six.BytesIO(b'postgresql.conf'),
                    six.BytesIO(b'pg_hba.conf'),
                )
                container = TestContainer(
                    name='name',
                    options=dict(volume='/data:/data'),
                    sudo=True,
                )
                with mock.patch(
                    'fabricio.run',
                    side_effect=data.get('side_effect'),
                ) as run:
                    with mock.patch('fabricio.operations.run', run):
                        with mock.patch.object(
                            container,
                            'db_exists',
                            return_value=data['db_exists'],
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
                                    self.assertListEqual(run.mock_calls, data['expected_commands'])
                                    self.assertEqual(result, data['expected_result'])
                                    update.assert_called_once_with(**data['expected_update_kwargs'])
                                    if data.get('expected_db_creation', False):
                                        create_db.assert_called_once()

    def test_revert(self):
        cases = dict(
            pg_hba_reverted=dict(
                parent_revert_returned=docker.ContainerError,
                expected_commands = [
                    mock.call('mv -f /data/postgresql.conf.backup /data/postgresql.conf', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf.backup /data/pg_hba.conf', ignore_errors=True, sudo=True),
                    mock.call('docker kill --signal HUP name'),
                ],
                side_effect=(
                    FailedResult(),  # main config
                    SucceededResult(),  # pg_hba
                    SucceededResult(),  # SIGHUP
                ),
            ),
            main_conf_reverted=dict(
                parent_revert_returned=docker.ContainerError,
                expected_commands = [
                    mock.call('mv -f /data/postgresql.conf.backup /data/postgresql.conf', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf.backup /data/pg_hba.conf', ignore_errors=True, sudo=True),
                    mock.call('docker restart --time 30 name'),
                ],
                side_effect=(
                    SucceededResult(),  # main config
                    FailedResult(),  # pg_hba
                    SucceededResult(),  # restart
                ),
            ),
            configs_reverted=dict(
                parent_revert_returned=docker.ContainerError,
                expected_commands = [
                    mock.call('mv -f /data/postgresql.conf.backup /data/postgresql.conf', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf.backup /data/pg_hba.conf', ignore_errors=True, sudo=True),
                    mock.call('docker restart --time 30 name'),
                ],
                side_effect=(
                    SucceededResult(),  # main config
                    SucceededResult(),  # pg_hba
                    SucceededResult(),  # restart
                ),
            ),
            pg_hba_reverted_container_reverted=dict(
                parent_revert_returned=None,
                expected_commands = [
                    mock.call('mv -f /data/postgresql.conf.backup /data/postgresql.conf', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf.backup /data/pg_hba.conf', ignore_errors=True, sudo=True),
                ],
                side_effect=(
                    FailedResult(),  # main config
                    SucceededResult(),  # pg_hba
                ),
            ),
            main_conf_reverted_container_reverted=dict(
                parent_revert_returned=None,
                expected_commands = [
                    mock.call('mv -f /data/postgresql.conf.backup /data/postgresql.conf', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf.backup /data/pg_hba.conf', ignore_errors=True, sudo=True),
                ],
                side_effect=(
                    SucceededResult(),  # main config
                    FailedResult(),  # pg_hba
                ),
            ),
            configs_reverted_container_reverted=dict(
                parent_revert_returned=None,
                expected_commands = [
                    mock.call('mv -f /data/postgresql.conf.backup /data/postgresql.conf', ignore_errors=True, sudo=True),
                    mock.call('mv -f /data/pg_hba.conf.backup /data/pg_hba.conf', ignore_errors=True, sudo=True),
                ],
                side_effect=(
                    SucceededResult(),  # main config
                    SucceededResult(),  # pg_hba
                ),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                expected_commands = data['expected_commands']
                with mock.patch(
                    'fabricio.run',
                    side_effect=data['side_effect'],
                ) as run:
                    with mock.patch('fabricio.operations.run', run):
                        with mock.patch.object(
                            docker.Container,
                            'revert',
                            side_effect=data['parent_revert_returned'],
                        ):
                            container = TestContainer(
                                name='name',
                                options=dict(volume='/data:/data'),
                                sudo=True,
                            )
                            container.revert()
                            self.assertListEqual(
                                run.mock_calls,
                                expected_commands,
                            )

    def test_revert_nothing_changed(self):
        expected_commands = [
            mock.call('mv -f /data/postgresql.conf.backup /data/postgresql.conf', ignore_errors=True, sudo=True),
            mock.call('mv -f /data/pg_hba.conf.backup /data/pg_hba.conf', ignore_errors=True, sudo=True),
        ]
        side_effect=(
            FailedResult(),  # main config
            FailedResult(),  # pg_hba
        )
        with mock.patch(
            'fabricio.run',
            side_effect=side_effect,
        ) as run:
            with mock.patch('fabricio.operations.run', run):
                with mock.patch.object(
                    docker.Container,
                    'revert',
                    side_effect=RuntimeError,
                ):
                    container = TestContainer(
                        name='name',
                        options=dict(volume='/data:/data'),
                        sudo=True,
                    )
                    with self.assertRaises(RuntimeError):
                        container.revert()
                    self.assertListEqual(
                        run.mock_calls,
                        expected_commands,
                    )


class StreamingReplicatedPostgresqlContainerTestCase(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()
        self.event_wait_mock = mock.patch.object(Event, 'wait')
        self.event_wait_mock.start()
        self.stderr = sys.stderr
        sys.stderr = six.BytesIO()

    def tearDown(self):
        postgres.open = open
        self.fab_settings.__exit__(None, None, None)
        self.event_wait_mock.stop()
        sys.stderr = self.stderr

    @mock.patch.object(postgres.StreamingReplicatedPostgresqlContainer, 'db_exists')
    @mock.patch.object(files, 'exists')
    @mock.patch.object(fabricio, 'run')
    def test_update_recovery_config(self, run, recovery_exists, db_exists):
        cases = dict(
            master=dict(
                db_exists=True,
                recovery_exists=False,
                host='master',
                expected_master_host='master',
                expected_result=False,
                expected_commands=[],
            ),
            slave=dict(
                db_exists=True,
                recovery_exists=True,
                host='slave',
                expected_master_host='master',
                expected_result=True,
                set_master='master',
                expected_recovery_conf=b"primary_conninfo = 'host=master port=5432 user=postgres'\n",
                expected_commands=[],
            ),
            slave_with_existing_recovery_conf=dict(
                db_exists=True,
                recovery_exists=True,
                host='slave',
                expected_master_host='master',
                expected_result=True,
                set_master='master',
                old_recovery_conf=(
                    "custom_setting = 'custom_setting'\n"
                    "primary_conninfo = 'host=old_master port=5432 user=postgres'\n"
                    "custom_setting2 = 'custom_setting2'\n"
                ),
                expected_recovery_conf=(
                    b"custom_setting = 'custom_setting'\n"
                    b"custom_setting2 = 'custom_setting2'\n"
                    b"primary_conninfo = 'host=master port=5432 user=postgres'\n"
                ),
                expected_commands=[],
            ),
            new_slave=dict(
                db_exists=False,
                recovery_exists=False,
                host='slave',
                expected_master_host='master',
                expected_result=True,
                set_master='master',
                expected_recovery_conf=b"primary_conninfo = 'host=master port=5432 user=postgres'\n",
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'volume': ['/data:/data'],
                    'stop-signal': 'INT',
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'image': 'image:latest',
                    'command': ['/bin/bash', '-c', 'pg_basebackup --progress --write-recovery-conf -X stream --pgdata=$PGDATA --host=master --username=postgres --port=5432'],
                },
            ),
            master_promotion_from_scratch=dict(
                db_exists=False,
                recovery_exists=False,
                host='new_master',
                expected_master_host='new_master',
                expected_result=False,
                expected_commands=[],
            ),
            master_promotion=dict(
                db_exists=True,
                recovery_exists=True,
                host='new_master',
                expected_master_host='new_master',
                expected_result=True,
                expected_commands=[
                    mock.call('mv -f /data/recovery.conf /data/recovery.conf.backup', ignore_errors=False, sudo=True),
                ],
                init_kwargs=dict(pg_recovery_master_promotion_enabled=True),
            ),
        )

        def test_command(command, *args, **kwargs):
            options = docker_run_args_parser.parse_args(shlex.split(command))
            self.assertDictEqual(vars(options), data['expected_args'])
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch('fabricio.operations.run', run):
                    run.reset_mock()
                    run.side_effect = data.get('expected_args') and test_command
                    postgres.open = mock.MagicMock(
                        return_value=six.StringIO(data.get('old_recovery_conf', '')),
                    )
                    db_exists.return_value = data['db_exists']
                    recovery_exists.return_value = data['recovery_exists']
                    fab.env.host = data['host']
                    container = postgres.StreamingReplicatedPostgresqlContainer(
                        name='name', image='image', pg_data='/data',
                        options=dict(volume='/data:/data'),
                        sudo=True,
                        **data.get('init_kwargs', {})
                    )
                    if 'set_master' in data:
                        container.multiprocessing_data.master = data['set_master']
                        container.master_obtained.set()
                    with mock.patch.object(container, 'update_config', return_value=True) as update_config:
                        result = container.update_recovery_config()
                        self.assertEqual(result, data['expected_result'])
                        self.assertEqual(container.multiprocessing_data.master, data['expected_master_host'])
                        expected_commands = data.get('expected_commands')
                        if expected_commands:
                            self.assertListEqual(run.mock_calls, expected_commands)
                        if 'expected_recovery_conf' in data:
                            update_config.assert_called_once_with(
                                content=data['expected_recovery_conf'],
                                path='/data/recovery.conf',
                            )

    @mock.patch.object(postgres.StreamingReplicatedPostgresqlContainer, 'db_exists', return_value=False)
    @mock.patch.object(postgres.StreamingReplicatedPostgresqlContainer, 'update_config')
    @mock.patch.object(postgres.StreamingReplicatedPostgresqlContainer, 'get_recovery_config')
    @mock.patch.object(fabricio, 'run')
    def test_update_recovery_config_does_not_promote_new_master_without_db_if_slave_with_db_exists(self, run, *args):
        def test_command(command, *args, **kwargs):
            options = docker_run_args_parser.parse_args(shlex.split(command))
            self.assertDictEqual(
                vars(options),
                {
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'volume': ['/data:/data'],
                    'stop-signal': 'INT',
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'image': 'image:latest',
                    'command': ['/bin/bash', '-c', 'pg_basebackup --progress --write-recovery-conf -X stream --pgdata=$PGDATA --host=promoted_master --username=postgres --port=5432'],
                },
            )
        run.side_effect = test_command
        container = postgres.StreamingReplicatedPostgresqlContainer(
            name='name', image='image', pg_data='/data',
            options=dict(volume='/data:/data'),
        )
        container.multiprocessing_data.db_exists = True
        container.multiprocessing_data.master = 'promoted_master'
        container.update_recovery_config()

    @mock.patch.object(postgres.PostgresqlContainer, 'db_exists', return_value=True)
    @mock.patch.object(files, 'exists', return_value=True)
    def test_update_fails_when_master_not_found_and_promotion_disabled(self, *args):
        class AbortException(Exception):
            pass
        container = postgres.StreamingReplicatedPostgresqlContainer(
            name='name', pg_data='/data',
            options=dict(volume='/data:/data'),
        )
        with fab.settings(abort_exception=AbortException):
            with mock.patch.object(fab, 'abort', side_effect=AbortException):
                with self.assertRaises(AbortException):
                    container.update_recovery_config()

    def test_update_raises_error_when_not_parallel_mode(self):
        class AbortException(Exception):
            pass
        container = postgres.StreamingReplicatedPostgresqlContainer(
            name='name',
            options=dict(volume='/data:/data'),
        )
        fab.env.parallel = False
        with fab.settings(abort_exception=AbortException):
            with mock.patch.object(fab, 'abort', side_effect=AbortException):
                with self.assertRaises(AbortException):
                    container.update()

    def test_revert_disabled_by_default(self):
        class AbortException(Exception):
            pass
        container = postgres.StreamingReplicatedPostgresqlContainer(
            name='name',
            options=dict(volume='/data:/data'),
        )
        with fab.settings(abort_exception=AbortException):
            with mock.patch.object(fab, 'abort', side_effect=AbortException):
                with self.assertRaises(AbortException):
                    container.revert()

    @mock.patch.object(postgres.PostgresqlContainer, 'revert')
    def test_revert_can_be_enabled(self, parent_revert):
        container = postgres.StreamingReplicatedPostgresqlContainer(
            name='name', pg_recovery_revert_enabled=True,
            options=dict(volume='/data:/data'),
        )
        container.revert()
        parent_revert.assert_called_once()

    def test_update(self):
        cases = dict(
            recovery_config_updated_container_not=dict(
                container_updated=False,
                should_restart=True,
                expected_result=True,
                recovery_config_updated=True,
            ),
            recovery_config_updated_container_too=dict(
                container_updated=True,
                should_restart=False,
                expected_result=True,
                recovery_config_updated=True,
            ),
            recovery_config_not_updated_container_updated=dict(
                container_updated=True,
                should_restart=False,
                expected_result=True,
                recovery_config_updated=False,
            ),
            recovery_config_and_container_not_updated=dict(
                container_updated=False,
                should_restart=False,
                expected_result=False,
                recovery_config_updated=False,
            ),
        )
        fab.env.parallel = True
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(docker.Container, 'reload') as restart:
                    with mock.patch.object(
                        postgres.PostgresqlContainer,
                        'update',
                        return_value=data['container_updated'],
                    ):
                        with mock.patch.object(
                            postgres.StreamingReplicatedPostgresqlContainer,
                            'update_recovery_config',
                            return_value=data['recovery_config_updated'],
                        ):
                            container = postgres.StreamingReplicatedPostgresqlContainer(
                                name='name', pg_recovery_revert_enabled=True,
                                options=dict(volume='/data:/data'),
                            )
                            result = container.update()
                            if data['should_restart']:
                                restart.assert_called_once()
                            self.assertEqual(result, data['expected_result'])
                            self.assertFalse(container.master_obtained.is_set())

    def test_set_master_info_calls_abort_on_exception(self):
        class AbortException(Exception):
            pass
        container = postgres.StreamingReplicatedPostgresqlContainer(
            name='name', options=dict(volume='volume'),
        )
        container.multiprocessing_data.exception = Exception('exception')
        with fab.settings(abort_exception=AbortException):
            with mock.patch.object(fab, 'abort', side_effect=AbortException):
                with self.assertRaises(AbortException):
                    container.set_master_info()

    @mock.patch.object(postgres.PostgresqlContainer, 'update', return_value=False)
    @mock.patch.object(postgres.PostgresqlContainer, 'reload')
    @mock.patch.object(Event, 'clear')
    @mock.patch.object(postgres.StreamingReplicatedPostgresqlContainer, 'update_recovery_config', return_value=True)
    def test_update_set_exception_info_if_any_happens(self, *args):
        exception = Exception('error')
        cases = dict(
            container_update_failed=dict(
                mock=mock.patch.object(postgres.PostgresqlContainer, 'update', side_effect=exception),
            ),
            configs_update_failed=dict(
                mock=mock.patch.object(postgres.StreamingReplicatedPostgresqlContainer, 'update_recovery_config', side_effect=exception),
            ),
            container_restart_failed=dict(
                mock=mock.patch.object(postgres.PostgresqlContainer, 'reload', side_effect=exception),
            ),
        )
        container = postgres.StreamingReplicatedPostgresqlContainer(
            name='name', options=dict(volume='volume'),
        )
        with fab.settings(parallel=True):
            for case, data in cases.items():
                with self.subTest(case=case):
                    with data['mock']:
                        with self.assertRaises(Exception):
                            container.update()
                        self.assertIsInstance(
                            container.multiprocessing_data.exception,
                            Exception,
                        )
                        self.assertFalse(container.master_obtained.is_set())
                        container.multiprocessing_data.exception = None
