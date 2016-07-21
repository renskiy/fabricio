import os
import sys

import mock
import six
import unittest2 as unittest

from fabric import api as fab
from fabric.contrib import console
from fabric.main import load_tasks_from_module, is_task_module, is_task_object

import fabricio

from fabricio import docker
from fabricio.tasks import Tasks, DockerTasks, PullDockerTasks, BuildDockerTasks, infrastructure, Registry


class TestContainer(docker.Container):

    image = docker.Image('test')


class TestCase(unittest.TestCase):

    def setUp(self):
        self.stderr = sys.stderr
        sys.stderr = six.StringIO()

    def tearDown(self):
        sys.stderr = self.stderr

    def test_infrastructure(self):
        class AbortException(Exception):
            pass

        def task():
            return 'result'

        with fab.settings(abort_on_prompts=True, abort_exception=AbortException):
            self.assertTrue(is_task_object(infrastructure(task)))
            self.assertTrue(is_task_object(infrastructure()(task)))
            self.assertIsNone(fab.env.infrastructure)

            with self.assertRaises(AbortException):
                fab.execute(infrastructure(task))

            environ_backup = os.environ.copy()
            try:
                os.environ.pop('FABRICIO_INFRASTRUCTURE_AUTOCONFIRM', None)
                with self.assertRaises(AbortException):
                    fab.execute(infrastructure(task))

                for env in ('yes', 'true', '1', 'YES', 'True'):
                    os.environ['FABRICIO_INFRASTRUCTURE_AUTOCONFIRM'] = env
                    self.assertDictEqual({'<local-only>': 'result'}, fab.execute(infrastructure(task)))

                self.assertEqual('task', fab.env.infrastructure)

                for env in ('no', 'false', '0', 'NO', 'False'):
                    os.environ['FABRICIO_INFRASTRUCTURE_AUTOCONFIRM'] = env
                    with self.assertRaises(AbortException):
                        fab.execute(infrastructure(task))

                infrastructure(task)
                self.assertIsNotNone(fab.env.infrastructure)

                os.environ['CUSTOM_ENV'] = '1'
                self.assertDictEqual(
                    {'<local-only>': 'result'},
                    fab.execute(infrastructure(autoconfirm_env_var='CUSTOM_ENV')(task)),
                )
            finally:
                os.environ = environ_backup

            with mock.patch.object(console, 'confirm', side_effect=(True, False)):
                self.assertDictEqual({'<local-only>': 'result'}, fab.execute(infrastructure(task)))
                with self.assertRaises(AbortException):
                    fab.execute(infrastructure(task))

            self.assertDictEqual({'<local-only>': 'result'}, fab.execute(infrastructure(confirm=False)(task)))


class TasksTestCase(unittest.TestCase):

    def test_tasks(self):
        class TestTasks(Tasks):

            @fab.task(default=True, aliases=['foo', 'bar'])
            def default(self):
                pass

            @fab.task(name='name', alias='alias')
            def task(self):
                pass

        roles = ['role_1', 'role_2']
        hosts = ['host_1', 'host_2']
        tasks = TestTasks(roles=roles, hosts=hosts)
        self.assertTrue(is_task_module(tasks))
        self.assertTrue(tasks.default.is_default)
        self.assertListEqual(['foo', 'bar'], tasks.default.aliases)
        self.assertEqual('name', tasks.task.name)
        self.assertListEqual(['alias'], tasks.task.aliases)
        for task in tasks:
            self.assertListEqual(roles, task.roles)
            self.assertListEqual(hosts, task.hosts)
        docstring, new_style, classic, default = load_tasks_from_module(tasks)
        self.assertIsNone(docstring)
        self.assertIn('default', new_style)
        self.assertIn('alias', new_style)
        self.assertIn('foo', new_style)
        self.assertIn('bar', new_style)
        self.assertIn('name', new_style)
        self.assertDictEqual({}, classic)
        self.assertIs(tasks.default, default)


class DockerTasksTestCase(unittest.TestCase):

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)

    def test_commands_list(self):
        cases = dict(
            default=dict(
                init_kwargs=dict(container='container'),
                expected_commands_list=['revert', 'pull', 'rollback', 'update', 'deploy'],
                unexpected_commands_list=['migrate', 'migrate_back', 'backup', 'restore'],
            ),
            migrate_tasks=dict(
                init_kwargs=dict(container='container', migrate_commands=True),
                expected_commands_list=['revert', 'pull', 'rollback', 'update', 'deploy', 'migrate', 'migrate_back'],
                unexpected_commands_list=['backup', 'restore'],
            ),
            backup_tasks=dict(
                init_kwargs=dict(container='container', backup_commands=True),
                expected_commands_list=['revert', 'pull', 'rollback', 'update', 'deploy', 'backup', 'restore'],
                unexpected_commands_list=['migrate', 'migrate_back'],
            ),
            all_tasks=dict(
                init_kwargs=dict(container='container', backup_commands=True, migrate_commands=True),
                expected_commands_list=['revert', 'pull', 'rollback', 'update', 'deploy', 'backup', 'restore', 'migrate', 'migrate_back'],
                unexpected_commands_list=[],
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                tasks = DockerTasks(**data['init_kwargs'])
                docstring, new_style, classic, default = load_tasks_from_module(tasks)
                for expected_command in data['expected_commands_list']:
                    self.assertIn(expected_command, new_style)
                for unexpected_command in data['unexpected_commands_list']:
                    self.assertNotIn(unexpected_command, new_style)

    @mock.patch.multiple(TestContainer, revert=mock.DEFAULT, migrate_back=mock.DEFAULT)
    def test_rollback(self, revert, migrate_back):
        tasks = DockerTasks(container=TestContainer('name'))
        rollback = mock.Mock()
        rollback.attach_mock(migrate_back, 'migrate_back')
        rollback.attach_mock(revert, 'revert')

        # default case
        fab.execute(tasks.rollback)
        self.assertListEqual(
            [mock.call.migrate_back(), mock.call.revert()],
            rollback.mock_calls,
        )
        rollback.reset_mock()

        # with migrate_back disabled
        fab.execute(tasks.rollback, migrate_back='no')
        migrate_back.assert_not_called()
        revert.assert_called_once()
        rollback.reset_mock()

    @mock.patch.multiple(TestContainer, backup=mock.DEFAULT, migrate=mock.DEFAULT, update=mock.DEFAULT)
    @mock.patch.object(fabricio, 'run')
    def test_deploy(self, run, backup, migrate, update):
        cases = dict(
            default=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker pull test:latest'),
                    mock.call.migrate(tag=None, registry=None),
                    mock.call.update(force=False, tag=None, registry=None),
                ],
            ),
            custom_registry=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker pull host:1234/test:latest'),
                    mock.call.migrate(tag=None, registry='host:1234'),
                    mock.call.update(force=False, tag=None, registry='host:1234'),
                ],
                init_kwargs=dict(registry='host:1234'),
            ),
            skip_migration=dict(
                deploy_kwargs=dict(migrate='no'),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker pull test:latest'),
                    mock.call.update(force=False, tag=None, registry=None),
                ],
            ),
            skip_migration_bool=dict(
                deploy_kwargs=dict(migrate=False),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker pull test:latest'),
                    mock.call.update(force=False, tag=None, registry=None),
                ],
            ),
            skip_backup=dict(
                deploy_kwargs=dict(backup='no'),
                expected_calls=[
                    mock.call.run('docker pull test:latest'),
                    mock.call.migrate(tag=None, registry=None),
                    mock.call.update(force=False, tag=None, registry=None),
                ],
            ),
            skip_backup_bool=dict(
                deploy_kwargs=dict(backup=False),
                expected_calls=[
                    mock.call.run('docker pull test:latest'),
                    mock.call.migrate(tag=None, registry=None),
                    mock.call.update(force=False, tag=None, registry=None),
                ],
            ),
            custom_tag=dict(
                deploy_kwargs=dict(tag='tag'),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker pull test:tag'),
                    mock.call.migrate(tag='tag', registry=None),
                    mock.call.update(force=False, tag='tag', registry=None),
                ],
            ),
            forced=dict(
                deploy_kwargs=dict(force='yes'),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker pull test:latest'),
                    mock.call.migrate(tag=None, registry=None),
                    mock.call.update(force=True, tag=None, registry=None),
                ],
            ),
            forced_bool=dict(
                deploy_kwargs=dict(force=True),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker pull test:latest'),
                    mock.call.migrate(tag=None, registry=None),
                    mock.call.update(force=True, tag=None, registry=None),
                ],
            ),
        )
        deploy = mock.Mock()
        deploy.attach_mock(backup, 'backup')
        deploy.attach_mock(migrate, 'migrate')
        deploy.attach_mock(update, 'update')
        deploy.attach_mock(run, 'run')
        for case, data in cases.items():
            with self.subTest(case=case):
                tasks = DockerTasks(container=TestContainer('name'), **data.get('init_kwargs', {}))
                tasks.deploy(**data['deploy_kwargs'])
                self.assertListEqual(data['expected_calls'], deploy.mock_calls)
                deploy.reset_mock()


class PullDockerTasksTestCase(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)

    @mock.patch.multiple(TestContainer, backup=mock.DEFAULT, migrate=mock.DEFAULT, update=mock.DEFAULT)
    @mock.patch.multiple(fabricio, run=mock.DEFAULT, local=mock.DEFAULT)
    @mock.patch.object(fab, 'remote_tunnel', return_value=mock.MagicMock())
    def test_deploy(self, remote_tunnel, run, local, backup, migrate, update):
        cases = dict(
            default=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
            ),
            custom_registry=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=1234, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull host:1234/test:latest'),
                    mock.call.migrate(tag=None, registry='host:1234'),
                    mock.call.update(force=False, tag=None, registry='host:1234'),
                ],
                init_kwargs=dict(registry='host:1234'),
            ),
            custom_local_registry=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest host:1234/test:latest', use_cache=True),
                    mock.call.local('docker push host:1234/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:1234/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=1234, local_host='host'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
                init_kwargs=dict(local_registry='host:1234'),
            ),
            forced=dict(
                deploy_kwargs=dict(force='yes'),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=True, tag=None, registry='localhost:5000'),
                ],
            ),
            custom_tag=dict(
                deploy_kwargs=dict(tag='tag'),
                expected_calls=[
                    mock.call.local('docker pull test:tag', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:tag localhost:5000/test:tag', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:tag', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:tag', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:tag'),
                    mock.call.migrate(tag='tag', registry='localhost:5000'),
                    mock.call.update(force=False, tag='tag', registry='localhost:5000'),
                ],
            ),
            skip_backup=dict(
                deploy_kwargs=dict(backup='no'),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
            ),
            skip_migration=dict(
                deploy_kwargs=dict(migrate='no'),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
            ),
        )
        deploy = mock.Mock()
        deploy.attach_mock(backup, 'backup')
        deploy.attach_mock(migrate, 'migrate')
        deploy.attach_mock(update, 'update')
        deploy.attach_mock(run, 'run')
        deploy.attach_mock(local, 'local')
        deploy.attach_mock(remote_tunnel, 'remote_tunnel')
        for case, data in cases.items():
            with self.subTest(case=case):
                tasks = PullDockerTasks(container=TestContainer('name'), hosts=['host'], **data.get('init_kwargs', {}))
                tasks.deploy(**data['deploy_kwargs'])
                self.assertListEqual(data['expected_calls'], deploy.mock_calls)
                deploy.reset_mock()


class BuildDockerTasksTestCase(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)

    @mock.patch.multiple(TestContainer, backup=mock.DEFAULT, migrate=mock.DEFAULT, update=mock.DEFAULT)
    @mock.patch.multiple(fabricio, run=mock.DEFAULT, local=mock.DEFAULT)
    @mock.patch.object(fab, 'remote_tunnel', return_value=mock.MagicMock())
    def test_deploy(self, remote_tunnel, run, local, backup, migrate, update):
        cases = dict(
            default=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
            ),
            no_cache=dict(
                deploy_kwargs=dict(no_cache=True),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest --no-cache .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
            ),
            custom_build_path=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest build/path', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
                init_kwargs=dict(build_path='build/path'),
            ),
            custom_registry=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=1234, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull host:1234/test:latest'),
                    mock.call.migrate(tag=None, registry='host:1234'),
                    mock.call.update(force=False, tag=None, registry='host:1234'),
                ],
                init_kwargs=dict(registry='host:1234'),
            ),
            custom_local_registry=dict(
                deploy_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest host:1234/test:latest', use_cache=True),
                    mock.call.local('docker push host:1234/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:1234/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=1234, local_host='host'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
                init_kwargs=dict(local_registry='host:1234'),
            ),
            forced=dict(
                deploy_kwargs=dict(force='yes'),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=True, tag=None, registry='localhost:5000'),
                ],
            ),
            custom_tag=dict(
                deploy_kwargs=dict(tag='tag'),
                expected_calls=[
                    mock.call.local('docker build --tag test:tag .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:tag localhost:5000/test:tag', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:tag', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:tag', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:tag'),
                    mock.call.migrate(tag='tag', registry='localhost:5000'),
                    mock.call.update(force=False, tag='tag', registry='localhost:5000'),
                ],
            ),
            skip_backup=dict(
                deploy_kwargs=dict(backup='no'),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.migrate(tag=None, registry='localhost:5000'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
            ),
            skip_migration=dict(
                deploy_kwargs=dict(migrate='no'),
                expected_calls=[
                    mock.call.local('docker build --tag test:latest .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi $(docker images --filter "dangling=true" --quiet)', ignore_errors=True),
                    mock.call.local('docker tag test:latest localhost:5000/test:latest', use_cache=True),
                    mock.call.local('docker push localhost:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi localhost:5000/test:latest', use_cache=True),
                    mock.call.backup(),
                    mock.call.remote_tunnel(remote_port=5000, local_port=5000, local_host='localhost'),
                    mock.call.run('docker pull localhost:5000/test:latest'),
                    mock.call.update(force=False, tag=None, registry='localhost:5000'),
                ],
            ),
        )
        deploy = mock.Mock()
        deploy.attach_mock(backup, 'backup')
        deploy.attach_mock(migrate, 'migrate')
        deploy.attach_mock(update, 'update')
        deploy.attach_mock(run, 'run')
        deploy.attach_mock(local, 'local')
        deploy.attach_mock(remote_tunnel, 'remote_tunnel')
        for case, data in cases.items():
            with self.subTest(case=case):
                tasks = BuildDockerTasks(container=TestContainer('name'), hosts=['host'], **data.get('init_kwargs', {}))
                tasks.deploy(**data['deploy_kwargs'])
                self.assertListEqual(data['expected_calls'], deploy.mock_calls)
                deploy.reset_mock()
