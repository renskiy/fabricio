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


class ImageTestCase(unittest.TestCase):

    disable_warnings = mock.patch.dict(fabric.state.output, {'warnings': False})

    def setUp(self):
        self.disable_warnings.start()

    def tearDown(self):
        self.disable_warnings.stop()

    def test_info(self):
        def side_effect(command):
            result = next(sudo_results)
            if callable(result):
                result = result() or _AttributeString(succeeded=False)
            return result
        cases = dict(
            without_container=dict(
                sudo_results=(
                    _AttributeString('[{"Id": "image_id"}]'),
                ),
                expected_commands=[
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
                ],
                init_kwargs=dict(name='image'),
            ),
            without_container_but_with_tag=dict(
                sudo_results=(
                    _AttributeString('[{"Id": "image_id"}]'),
                ),
                expected_commands=[
                    mock.call(docker.Image.COMMAND_INFO.format(image='image:tag')),
                ],
                init_kwargs=dict(name='image', tag='tag'),
            ),
            with_container=dict(
                sudo_results=(
                    _AttributeString('[{"Image": "image_id"}]'),
                    _AttributeString('[{"Id": "image_id"}]'),
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
                with mock.patch.object(fabric.api, 'sudo', side_effect=side_effect) as sudo:
                    self.assertEqual({'Id': 'image_id'}, image.info)
                    sudo.assert_has_calls(expected_commands)
                    self.assertEqual(len(expected_commands), sudo.call_count)
