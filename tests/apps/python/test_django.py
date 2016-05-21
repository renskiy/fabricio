import mock
import unittest2 as unittest

import fabricio

from fabricio.apps.python.django import DjangoContainer
from fabricio import docker


class TestContainer(DjangoContainer):

    image = docker.Image('image:tag')


class ContainerTestCase(unittest.TestCase):

    def test_revert_migrations(self):
        cases = dict(
            no_change=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    (
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                    ),
                    '[{"Image": "backup_image_id"}]',
                    (
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                    ),
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker run --rm --tty backup_image_id manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'),
                ],
            ),
            no_migrations=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    '',
                    '[{"Image": "backup_image_id"}]',
                    '',
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker run --rm --tty backup_image_id manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'),
                ],
            ),
            regular=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    (
                        'app0.0001_initial\n'
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                        'app3.0001_initial\n'
                        'app2.0002_foo\n'
                        'app3.0002_foo\n'
                    ),
                    '[{"Image": "backup_image_id"}]',
                    (
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                    ),
                    '',
                    '',
                    '',
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker run --rm --tty backup_image_id manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'),
                    mock.call('docker run --rm --tty current_image_id manage.py migrate --no-input app3 zero'),
                    mock.call('docker run --rm --tty current_image_id manage.py migrate --no-input app2 0001_initial'),
                    mock.call('docker run --rm --tty current_image_id manage.py migrate --no-input app0 zero'),
                ]
            ),
            current_container_not_found=dict(
                side_effect=(
                    RuntimeError,
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                ]
            ),
            backup_container_not_found=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    (
                        'app1.0001_initial\n'
                    ),
                    RuntimeError,
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'),
                    mock.call('docker inspect --type container name_backup'),
                ]
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                side_effect = data['side_effect']
                expected_commands = data['expected_commands']
                with mock.patch.object(
                    fabricio,
                    'exec_command',
                    side_effect=side_effect,
                ) as exec_command:
                    container = TestContainer(name='name')

                    container.revert_migrations()
                    del container.revert_migrations.__func__.return_value

                    exec_command.assert_has_calls(expected_commands)
                    self.assertEqual(
                        len(expected_commands),
                        exec_command.call_count,
                    )
