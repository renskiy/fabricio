# coding: utf-8
import collections

import six
import unittest2 as unittest

from fabricio import docker, utils


class OptionsTestCase(unittest.TestCase):

    def test_str_version(self):
        cases = dict(
            empty_options_list=dict(
                options=collections.OrderedDict(),
                expected_str_version='',
            ),
            with_underscore=dict(
                options=collections.OrderedDict(foo_baz='bar'),
                expected_str_version='--foo_baz=bar',
            ),
            multiword=dict(
                options=collections.OrderedDict(foo='bar baz'),
                expected_str_version="--foo='bar baz'",
            ),
            empty=dict(
                options=collections.OrderedDict(foo=''),
                expected_str_version="--foo=''",
            ),
            str=dict(
                options=collections.OrderedDict(foo='bar'),
                expected_str_version='--foo=bar',
            ),
            unicode=dict(
                options=collections.OrderedDict(foo=u'привет'),
                expected_str_version=u"--foo='привет'",
            ),
            integer=dict(
                options=collections.OrderedDict(foo=42),
                expected_str_version='--foo=42',
            ),
            integer_zero=dict(
                options=collections.OrderedDict(foo=0),
                expected_str_version='--foo=0',
            ),
            integer_one=dict(
                options=collections.OrderedDict(foo=1),
                expected_str_version='--foo=1',
            ),
            integer_minus_one=dict(
                options=collections.OrderedDict(foo=-1),
                expected_str_version='--foo=-1',
            ),
            image=dict(
                options=collections.OrderedDict(image=docker.Image('image:tag')),
                expected_str_version='--image=image:tag',
            ),
            triple_length=dict(
                options=collections.OrderedDict([
                    ('foo', 'foo'),
                    ('bar', 'bar'),
                    ('baz', 'baz'),
                ]),
                expected_str_version='--foo=foo --bar=bar --baz=baz',
            ),
            multi_value_empty=dict(
                options=collections.OrderedDict(foo=[]),
                expected_str_version='',
            ),
            multi_value=dict(
                options=collections.OrderedDict(foo=['bar', 'baz']),
                expected_str_version='--foo=bar --foo=baz',
            ),
            multi_value_integer=dict(
                options=collections.OrderedDict(foo=[42, 43]),
                expected_str_version='--foo=42 --foo=43',
            ),
            boolean_values=dict(
                options=collections.OrderedDict(foo=True, bar=False),
                expected_str_version='--foo',
            ),
            mix=dict(
                options=collections.OrderedDict([
                    ('foo', 'foo'),
                    ('bar', True),
                    ('baz', ['1', 'a']),
                ]),
                expected_str_version='--foo=foo --bar --baz=1 --baz=a',
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                options = utils.Options(params['options'])
                expected_str_version = params['expected_str_version']
                self.assertEqual(expected_str_version, six.text_type(options))
