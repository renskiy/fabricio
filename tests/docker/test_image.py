import functools

import fabric.api
import fabric.state
import mock
import unittest2 as unittest

from fabric.utils import error

from fabricio import docker

from tests import AttributeString


class ImageTestCase(unittest.TestCase):

    disable_warnings = mock.patch.dict(fabric.state.output, {'warnings': False})

    def setUp(self):
        self.disable_warnings.start()

    def tearDown(self):
        self.disable_warnings.stop()

    def test_info(self):
        cases = dict(
            without_container=dict(
                sudo_results=(
                    AttributeString('[{"Id": "image_id"}]'),
                ),
                expected_commands=[
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                ],
                init_kwargs=dict(name='image'),
            ),
            without_container_but_with_tag=dict(
                sudo_results=(
                    AttributeString('[{"Id": "image_id"}]'),
                ),
                expected_commands=[
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:tag')),
                ],
                init_kwargs=dict(name='image', tag='tag'),
            ),
            with_container=dict(
                sudo_results=(
                    AttributeString('[{"Image": "image_id"}]'),
                    AttributeString('[{"Id": "image_id"}]'),
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                ],
                init_kwargs=dict(name='image', container=docker.Container(name='name')),
            ),
            with_container_and_tag=dict(
                sudo_results=(
                    AttributeString('[{"Image": "image_id"}]'),
                    AttributeString('[{"Id": "image_id"}]'),
                ),
                expected_commands=[
                    mock.call(docker.Container.COMMAND_INFO.format(container='name')),
                    mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
                ],
                init_kwargs=dict(name='image', tag='tag', container=docker.Container(name='name')),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                sudo_results = iter(params['sudo_results'])
                expected_commands = params['expected_commands']
                init_kwargs = params['init_kwargs']
                image = docker.Image(**init_kwargs)
                with mock.patch.object(fabric.api, 'sudo', side_effect=sudo_results) as sudo:
                    self.assertEqual({'Id': 'image_id'}, image.info)
                    sudo.assert_has_calls(expected_commands)
                    self.assertEqual(len(expected_commands), sudo.call_count)

    def test_delete(self):
        def side_effect(command):
            result = next(sudo_results)
            if callable(result):
                result = result() or AttributeString(succeeded=False)
            return result
        cases = dict(
            regular=dict(
                sudo_results=(
                    AttributeString('[{"Id": "image_id"}]'),
                    '',
                ),
                expected_commands=[
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='image_id')),
                ],
                delete_kwargs=dict(),
            ),
            failed_deletion=dict(
                sudo_results=(
                    AttributeString('[{"Id": "image_id"}]'),
                    functools.partial(error, 'can not delete image'),
                ),
                expected_commands=[
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                    mock.call(docker.Image.COMMAND_DELETE.format(image='image_id')),
                ],
                delete_kwargs=dict(ignore_delete_error=True),
            ),
            forced=dict(
                sudo_results=(
                    AttributeString('[{"Id": "image_id"}]'),
                    '',
                ),
                expected_commands=[
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                    mock.call(docker.Image.COMMAND_FORCE_DELETE.format(image='image_id')),
                ],
                delete_kwargs=dict(force=True),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                sudo_results = iter(params['sudo_results'])
                expected_commands = params['expected_commands']
                delete_kwargs = params['delete_kwargs']
                image = docker.Image(name='image')
                with mock.patch.object(fabric.api, 'sudo', side_effect=side_effect) as sudo:
                    image.delete(**delete_kwargs)
                    sudo.assert_has_calls(expected_commands)
                    self.assertEqual(len(expected_commands), sudo.call_count)
