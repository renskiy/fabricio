import fabric.api
import fabric.state
import functools
import mock
import unittest2 as unittest

from fabric.utils import error

from fabricio import docker, Options


class _AttributeString(str):

    def __new__(cls, *args, **kwargs):
        kwargs.pop('succeeded', None)
        return super(_AttributeString, cls).__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        self.succeeded = kwargs.pop('succeeded', True)
        super(_AttributeString, self).__init__(*args, **kwargs)


class ContainerTestCase(unittest.TestCase):

    disable_warnings = mock.patch.dict(fabric.state.output, {'warnings': False})

    def setUp(self):
        self.disable_warnings.start()

    def tearDown(self):
        self.disable_warnings.stop()

    def test_info(self):
        return_value = _AttributeString('[{"Id": "123", "Image": "abc"}]')
        container = docker.Container(name='name')
        expected_command = container.COMMAND_INFO.format(container='name')
        with mock.patch.object(fabric.api, 'sudo', return_value=return_value) as sudo:
            self.assertEqual(dict(Id='123', Image='abc'), container.info)
            sudo.assert_called_once_with(expected_command)

    def test_delete(self):
        return_value = _AttributeString('[{"Id": "123", "Image": "image"}]')
        cases = dict(
            delete=dict(
                delete_kwargs=dict(),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_DELETE.format(container='name')),
                ],
            ),
            force_delete=dict(
                delete_kwargs=dict(force=True),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_FORCE_DELETE.format(container='name')),
                ],
            ),
            delete_with_image=dict(
                delete_kwargs=dict(delete_image=True),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image')),
                    mock.call(docker.Container.COMMAND_DELETE.format(container='name')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='123')),
                ],
            ),
            force_delete_with_image=dict(
                delete_kwargs=dict(force=True, delete_image=True),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image')),
                    mock.call(docker.Container.COMMAND_FORCE_DELETE.format(container='name')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='123')),
                ],
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container = docker.Container(image='image', name='name')
                with mock.patch.object(fabric.api, 'sudo', return_value=return_value) as sudo:
                    expected_commands = params['expected_commands']
                    commands_count = len(expected_commands)
                    delete_kwargs = params['delete_kwargs']
                    container.delete(**delete_kwargs)
                    sudo.assert_has_calls(expected_commands)
                    self.assertEqual(commands_count, sudo.call_count)

    def test_execute(self):
        cases = dict(
            regular=dict(
                container_kwargs=dict(
                    image='image',
                    name='name',
                ),
                expected_command=docker.Container.COMMAND_EXECUTE.format(
                    container='name',
                    cmd='cmd',
                ),
            ),
            temporary=dict(
                container_kwargs=dict(
                    image='image',
                    name='name',
                    temporary=True,
                ),
                expected_command=docker.Container.COMMAND_RUN.format(
                    image='image:latest',
                    cmd='cmd',
                    options=Options([
                        ('name', 'name'),
                        ('rm', True),
                        ('tty', True),
                    ]),
                ),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container_kwargs = params['container_kwargs']
                expected_command = params['expected_command']
                container = docker.Container(**container_kwargs)
                with mock.patch.object(fabric.api, 'sudo') as sudo:
                    container.execute('cmd')
                    sudo.assert_called_once_with(expected_command)

    def test_run(self):
        cases = dict(
            regular=dict(
                init_kwargs=dict(
                    image='image',
                    name='name',
                ),
                expected_command=docker.Container.COMMAND_RUN.format(
                    image='image:latest',
                    cmd='',
                    options=Options([
                        ('name', 'name'),
                        ('detach', True),
                    ]),
                ),
                expected_vars=dict(id='id'),
            ),
            complex=dict(
                init_kwargs=dict(
                    image='image',
                    name='name',
                    cmd='cmd',
                    user='user',
                    ports=['80:80', '443:443'],
                    env=['VAR1=val1', 'VAR2=val2'],
                    volumes=['/tmp:/tmp', '/root:/root:ro'],
                    links=['db:db', 'queue:queue'],
                    hosts=['host1:127.0.0.1', 'host2:127.0.0.1'],
                    network='network',
                    restart_policy='always',
                    stop_signal='SIGINT',
                    options=Options([
                        ('option1', 'value1'),
                        ('option2', 'value2'),
                    ])
                ),
                expected_command=docker.Container.COMMAND_RUN.format(
                    image='image:latest',
                    cmd='cmd',
                    options=Options([
                        ('option1', 'value1'),
                        ('option2', 'value2'),
                        ('name', 'name'),
                        ('detach', True),
                        ('publish', ['80:80', '443:443']),
                        ('restart', 'always'),
                        ('user', 'user'),
                        ('env', ['VAR1=val1', 'VAR2=val2']),
                        ('volume', ['/tmp:/tmp', '/root:/root:ro']),
                        ('link', ['db:db', 'queue:queue']),
                        ('add-host', ['host1:127.0.0.1', 'host2:127.0.0.1']),
                        ('net', 'network'),
                        ('stop-signal', 'SIGINT'),
                    ]),
                ),
                expected_vars=dict(id='id'),
            ),
            temporary=dict(
                init_kwargs=dict(
                    image='image',
                    name='name',
                    temporary=True,
                ),
                expected_command=docker.Container.COMMAND_RUN.format(
                    image='image:latest',
                    cmd='',
                    options=Options([
                        ('name', 'name'),
                        ('rm', True),
                        ('tty', True),
                    ]),
                ),
                expected_vars=dict(),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                init_kwargs = params['init_kwargs']
                expected_command = params['expected_command']
                expected_vars = params['expected_vars']
                container = docker.Container(**init_kwargs)
                with mock.patch.object(fabric.api, 'sudo', return_value='id') as sudo:
                    container.run()
                    sudo.assert_called_once_with(expected_command)
                    self.assertDictContainsSubset(expected_vars, vars(container))

    @mock.patch.object(fabric.api, 'sudo')
    def test_start(self, sudo):
        expected_command = docker.Container.COMMAND_START.format(container='name')
        container = docker.Container(name='name')
        container.start()
        sudo.assert_called_once_with(expected_command)

    @mock.patch.object(fabric.api, 'sudo')
    def test_stop(self, sudo):
        expected_command = docker.Container.COMMAND_STOP.format(
            container='name',
            timeout=10,
        )
        container = docker.Container(name='name')
        container.stop(timeout=10)
        sudo.assert_called_once_with(expected_command)

    @mock.patch.object(fabric.api, 'sudo')
    def test_restart(self, sudo):
        expected_command = docker.Container.COMMAND_RESTART.format(
            container='name',
            timeout=10,
        )
        container = docker.Container(name='name')
        container.restart(timeout=10)
        sudo.assert_called_once_with(expected_command)

    @mock.patch.object(fabric.api, 'sudo')
    def test_signal(self, sudo):
        expected_command = docker.Container.COMMAND_SIGNAL.format(
            container='name',
            signal='SIGINT',
        )
        container = docker.Container(name='name')
        container.signal('SIGINT')
        sudo.assert_called_once_with(expected_command)

    @mock.patch.object(fabric.api, 'sudo')
    def test_rename(self, sudo):
        expected_command = docker.Container.COMMAND_RENAME.format(
            container='name',
            new_name='new_name',
        )
        container = docker.Container(name='name')
        container.rename('new_name')
        sudo.assert_called_once_with(expected_command)
        self.assertEqual('new_name', container.name)

    @mock.patch.object(fabric.api, 'puts')
    def test_update(self, *args):
        def side_effect(command):
            result = next(sudo_results)
            if callable(result):
                result = result() or _AttributeString(succeeded=False)
            return result
        cases = dict(
            no_change=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "image_id"}]'),  # current container info
                    _AttributeString('[{"Id": "image_id"}]'),  # current container image info
                    _AttributeString('[{"Id": "image_id"}]'),  # new image info
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                ],
                update_kwargs=dict(),
            ),
            no_change_with_tag=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "image_id"}]'),  # current container info
                    _AttributeString('[{"Id": "image_id"}]'),  # current container image info
                    _AttributeString('[{"Id": "image_id"}]'),  # new image info
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:tag')),
                ],
                update_kwargs=dict(tag='tag'),
            ),
            no_change_forced=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "image_id"}]'),  # obsolete container info
                    _AttributeString('[{"Id": "image_id"}]'),  # obsolete container image info
                    _AttributeString(''),  # delete obsolete container
                    functools.partial(error, 'can not delete image'),  # delete obsolete container image
                    _AttributeString(''),  # rename current container
                    _AttributeString(''),  # stop current container
                    _AttributeString('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                    mock.call(docker.Container.COMMAND_DELETE.format(container='name_backup')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='image_id')),
                    mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
                    mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
                    mock.call(docker.Container.COMMAND_RUN.format(
                        cmd='',
                        image='image:latest',
                        options=Options([
                            ('name', 'name'),
                            ('detach', True),
                        ]),
                    )),
                ],
                update_kwargs=dict(force=True),
            ),
            regular=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "image_id"}]'),  # current container info
                    _AttributeString('[{"Id": "image_id"}]'),  # current container image info
                    _AttributeString('[{"Id": "new_image_id"}]'),  # new image info
                    _AttributeString('[{"Image": "old_image_id"}]'),  # obsolete container info
                    _AttributeString('[{"Id": "old_image_id"}]'),  # obsolete container image info
                    _AttributeString(''),  # delete obsolete container
                    _AttributeString(''),  # delete obsolete container image
                    _AttributeString(''),  # rename current container
                    _AttributeString(''),  # stop current container
                    _AttributeString('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                    mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='old_image_id')),
                    mock.call(docker.Container.COMMAND_DELETE.format(container='name_backup')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='old_image_id')),
                    mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
                    mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
                    mock.call(docker.Container.COMMAND_RUN.format(
                        cmd='',
                        image='image:latest',
                        options=Options([
                            ('name', 'name'),
                            ('detach', True),
                        ]),
                    )),
                ],
                update_kwargs=dict(),
            ),
            regular_with_tag=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "image_id"}]'),  # current container info
                    _AttributeString('[{"Id": "image_id"}]'),  # current container image info
                    _AttributeString('[{"Id": "new_image_id"}]'),  # new image info
                    _AttributeString('[{"Image": "old_image_id"}]'),  # obsolete container info
                    _AttributeString('[{"Id": "old_image_id"}]'),  # obsolete container image info
                    _AttributeString(''),  # delete obsolete container
                    _AttributeString(''),  # delete obsolete container image
                    _AttributeString(''),  # rename current container
                    _AttributeString(''),  # stop current container
                    _AttributeString('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:tag')),
                    mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='old_image_id')),
                    mock.call(docker.Container.COMMAND_DELETE.format(container='name_backup')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='old_image_id')),
                    mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
                    mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
                    mock.call(docker.Container.COMMAND_RUN.format(
                        cmd='',
                        image='image:latest',
                        options=Options([
                            ('name', 'name'),
                            ('detach', True),
                        ]),
                    )),
                ],
                update_kwargs=dict(tag='tag'),
            ),
            regular_without_backup=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "image_id"}]'),  # current container info
                    _AttributeString('[{"Id": "image_id"}]'),  # current container image info
                    _AttributeString('[{"Id": "new_image_id"}]'),  # new image info
                    functools.partial(error, 'backup container not found'),  # obsolete container info
                    _AttributeString(''),  # rename current container
                    _AttributeString(''),  # stop current container
                    _AttributeString('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                    mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
                    mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
                    mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
                    mock.call(docker.Container.COMMAND_RUN.format(
                        cmd='',
                        image='image:latest',
                        options=Options([
                            ('name', 'name'),
                            ('detach', True),
                        ]),
                    )),
                ],
                update_kwargs=dict(),
            ),
            from_scratch=dict(
                sudo_results=(
                    functools.partial(error, 'current container not found'),  # current container info
                    functools.partial(error, 'backup container not found'),  # obsolete container info
                    functools.partial(error, 'current container not found'),  # rename current container
                    functools.partial(error, 'current container not found'),  # stop current container
                    _AttributeString('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
                    mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
                    mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
                    mock.call(docker.Container.COMMAND_RUN.format(
                        cmd='',
                        image='image:latest',
                        options=Options([
                            ('name', 'name'),
                            ('detach', True),
                        ]),
                    )),
                ],
                update_kwargs=dict(),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container = docker.Container(image='image', name='name')
                sudo_results = iter(params['sudo_results'])
                expected_commands = params['expected_commands']
                update_kwargs = params['update_kwargs']
                commands_count = len(expected_commands)
                with mock.patch.object(fabric.api, 'sudo', side_effect=side_effect) as sudo:
                    container.update(**update_kwargs)
                    sudo.assert_has_calls(expected_commands)
                    self.assertEqual(commands_count, sudo.call_count)

    def test_revert(self):
        def side_effect(command):
            result = next(sudo_results)
            if callable(result):
                result = result() or _AttributeString(succeeded=False)
            return result
        cases = dict(
            regular=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "failed_image_id"}]'),  # failed container info
                    _AttributeString('[{"Id": "failed_image_id"}]'),  # failed container image info
                    _AttributeString(''),  # delete failed container
                    _AttributeString(''),  # delete failed container image
                    _AttributeString(''),  # start backup container
                    _AttributeString(''),  # rename backup container
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='failed_image_id')),
                    mock.call(docker.Container.COMMAND_FORCE_DELETE.format(container='name')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='failed_image_id')),
                    mock.call(docker.Container.COMMAND_START.format(container='name_backup')),
                    mock.call(docker.Container.COMMAND_RENAME.format(container='name_backup', new_name='name')),
                ],
                revert_kwargs=dict(),
            ),
            can_not_delete_failed_image=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "failed_image_id"}]'),  # failed container info
                    _AttributeString('[{"Id": "failed_image_id"}]'),  # failed container image info
                    _AttributeString(''),  # delete failed container
                    functools.partial(error, 'can not delete image'),  # delete failed container image
                    _AttributeString(''),  # start backup container
                    _AttributeString(''),  # rename backup container
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='failed_image_id')),
                    mock.call(docker.Container.COMMAND_FORCE_DELETE.format(container='name')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='failed_image_id')),
                    mock.call(docker.Container.COMMAND_START.format(container='name_backup')),
                    mock.call(docker.Container.COMMAND_RENAME.format(container='name_backup', new_name='name')),
                ],
                revert_kwargs=dict(),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container = docker.Container(image='image', name='name')
                sudo_results = iter(params['sudo_results'])
                expected_commands = params['expected_commands']
                revert_kwargs = params['revert_kwargs']
                commands_count = len(expected_commands)
                with mock.patch.object(fabric.api, 'sudo', side_effect=side_effect) as sudo:
                    container.revert(**revert_kwargs)
                    sudo.assert_has_calls(expected_commands)
                    self.assertEqual(commands_count, sudo.call_count)
