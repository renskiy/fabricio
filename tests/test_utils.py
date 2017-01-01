# coding: utf-8
import mock
import six
import unittest2 as unittest

from fabric import api as fab

from fabricio import docker, utils


class OptionsTestCase(unittest.TestCase):

    def test_str_version(self):
        cases = dict(
            empty_options_list=dict(
                options=utils.OrderedDict(),
                expected_str_version='',
            ),
            with_underscore=dict(
                options=utils.OrderedDict(foo_baz='bar'),
                expected_str_version='--foo_baz bar',
            ),
            multiword=dict(
                options=utils.OrderedDict(foo='bar baz'),
                expected_str_version='--foo "bar baz"',
            ),
            empty=dict(
                options=utils.OrderedDict(foo=''),
                expected_str_version='--foo ""',
            ),
            with_single_quotes=dict(
                options=utils.OrderedDict(foo="'bar'"),
                expected_str_version='--foo "\'bar\'"',
            ),
            with_double_quotes=dict(
                options=utils.OrderedDict(foo='"bar"'),
                expected_str_version='--foo "\\"bar\\""',
            ),
            with_quotes_and_spaces=dict(
                options=utils.OrderedDict(foo='"bar" \'baz\''),
                expected_str_version='--foo "\\"bar\\" \'baz\'"',
            ),
            str=dict(
                options=utils.OrderedDict(foo='bar'),
                expected_str_version='--foo bar',
            ),
            unicode=dict(
                options=utils.OrderedDict(foo=u'привет'),
                expected_str_version=u'--foo привет',
            ),
            integer=dict(
                options=utils.OrderedDict(foo=42),
                expected_str_version='--foo 42',
            ),
            image=dict(
                options=utils.OrderedDict(image=docker.Image('image:tag')),
                expected_str_version='--image image:tag',
            ),
            triple_length=dict(
                options=utils.OrderedDict([
                    ('foo', 'foo'),
                    ('bar', 'bar'),
                    ('baz', 'baz'),
                ]),
                expected_str_version='--foo foo --bar bar --baz baz',
            ),
            multi_value=dict(
                options=utils.OrderedDict(foo=['bar', 'baz']),
                expected_str_version='--foo bar --foo baz',
            ),
            multi_value_integer=dict(
                options=utils.OrderedDict(foo=[42, 43]),
                expected_str_version='--foo 42 --foo 43',
            ),
            boolean_values=dict(
                options=utils.OrderedDict(foo=True, bar=False),
                expected_str_version='--foo',
            ),
            mix=dict(
                options=utils.OrderedDict([
                    ('foo', 'foo'),
                    ('bar', True),
                    ('baz', ['1', 'a']),
                ]),
                expected_str_version='--foo foo --bar --baz 1 --baz a',
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                options = utils.Options(params['options'])
                expected_str_version = params['expected_str_version']
                self.assertEqual(expected_str_version, six.text_type(options))

    def test_once_per_command(self):
        cases = dict(
            default=dict(
                all_hosts=[],
                command=None,
                infrastructure=None,
            ),
            same_infrastructure=dict(
                all_hosts=[],
                command=None,
                infrastructure='inf',
            ),
            same_command=dict(
                all_hosts=[],
                command='command',
                infrastructure=None,
            ),
            same_hosts=dict(
                all_hosts=['host1', 'host2'],
                command=None,
                infrastructure=None,
            ),
            complex=dict(
                all_hosts=['host1', 'host2'],
                command='command',
                infrastructure='inf',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                real_method = mock.Mock(__name__='method')
                method = utils.once_per_command(real_method)
                with fab.settings(**data):
                    method()
                    method()
                real_method.assert_called_once()
