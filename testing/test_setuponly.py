# mypy: allow-untyped-defs
from __future__ import annotations

import sys

from _testrunner.config import ExitCode
from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.fixture(
    params=["--setup-only", "--setup-plan", "--setup-show"], scope="module"
)
def mode(request):
    return request.param


def test_show_only_active_fixtures(
    testrunnerer: Testrunnerer, mode, dummy_yaml_custom_test
) -> None:
    testrunnerer.makepyfile(
        '''
        import testrunner
        @testrunner.fixture
        def _arg0():
            """hidden arg0 fixture"""
        @testrunner.fixture
        def arg1():
            """arg1 docstring"""
        def test_arg1(arg1):
            pass
    '''
    )

    result = testrunnerer.runtestrunner(mode)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        ["*SETUP    F arg1*", "*test_arg1 (fixtures used: arg1)*", "*TEARDOWN F arg1*"]
    )
    result.stdout.no_fnmatch_line("*_arg0*")


def test_show_different_scopes(testrunnerer: Testrunnerer, mode) -> None:
    p = testrunnerer.makepyfile(
        '''
        import testrunner
        @testrunner.fixture
        def arg_function():
            """function scoped fixture"""
        @testrunner.fixture(scope='session')
        def arg_session():
            """session scoped fixture"""
        def test_arg1(arg_session, arg_function):
            pass
    '''
    )

    result = testrunnerer.runtestrunner(mode, p)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        [
            "SETUP    S arg_session*",
            "*SETUP    F arg_function*",
            "*test_arg1 (fixtures used: arg_function, arg_session)*",
            "*TEARDOWN F arg_function*",
            "TEARDOWN S arg_session*",
        ]
    )


def test_show_nested_fixtures(testrunnerer: Testrunnerer, mode) -> None:
    testrunnerer.makeconftest(
        '''
        import testrunner
        @testrunner.fixture(scope='session')
        def arg_same():
            """session scoped fixture"""
        '''
    )
    p = testrunnerer.makepyfile(
        '''
        import testrunner
        @testrunner.fixture(scope='function')
        def arg_same(arg_same):
            """function scoped fixture"""
        def test_arg1(arg_same):
            pass
    '''
    )

    result = testrunnerer.runtestrunner(mode, p)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        [
            "SETUP    S arg_same*",
            "*SETUP    F arg_same (fixtures used: arg_same)*",
            "*test_arg1 (fixtures used: arg_same)*",
            "*TEARDOWN F arg_same*",
            "TEARDOWN S arg_same*",
        ]
    )


def test_show_fixtures_with_autouse(testrunnerer: Testrunnerer, mode) -> None:
    p = testrunnerer.makepyfile(
        '''
        import testrunner
        @testrunner.fixture
        def arg_function():
            """function scoped fixture"""
        @testrunner.fixture(scope='session', autouse=True)
        def arg_session():
            """session scoped fixture"""
        def test_arg1(arg_function):
            pass
    '''
    )

    result = testrunnerer.runtestrunner(mode, p)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        [
            "SETUP    S arg_session*",
            "*SETUP    F arg_function*",
            "*test_arg1 (fixtures used: arg_function, arg_session)*",
        ]
    )


def test_show_fixtures_with_parameters(testrunnerer: Testrunnerer, mode) -> None:
    testrunnerer.makeconftest(
        '''
        import testrunner
        @testrunner.fixture(scope='session', params=['foo', 'bar'])
        def arg_same():
            """session scoped fixture"""
        '''
    )
    p = testrunnerer.makepyfile(
        '''
        import testrunner
        @testrunner.fixture(scope='function')
        def arg_other(arg_same):
            """function scoped fixture"""
        def test_arg1(arg_other):
            pass
    '''
    )

    result = testrunnerer.runtestrunner(mode, p)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        [
            "SETUP    S arg_same?'foo'?",
            "TEARDOWN S arg_same?'foo'?",
            "SETUP    S arg_same?'bar'?",
            "TEARDOWN S arg_same?'bar'?",
        ]
    )


def test_show_fixtures_with_parameter_ids(testrunnerer: Testrunnerer, mode) -> None:
    testrunnerer.makeconftest(
        '''
        import testrunner
        @testrunner.fixture(
            scope='session', params=['foo', 'bar'], ids=['spam', 'ham'])
        def arg_same():
            """session scoped fixture"""
        '''
    )
    p = testrunnerer.makepyfile(
        '''
        import testrunner
        @testrunner.fixture(scope='function')
        def arg_other(arg_same):
            """function scoped fixture"""
        def test_arg1(arg_other):
            pass
    '''
    )

    result = testrunnerer.runtestrunner(mode, p)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        ["SETUP    S arg_same?'spam'?", "SETUP    S arg_same?'ham'?"]
    )


def test_show_fixtures_with_parameter_ids_function(
    testrunnerer: Testrunnerer, mode
) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.fixture(params=['foo', 'bar'], ids=lambda p: p.upper())
        def foobar():
            pass
        def test_foobar(foobar):
            pass
    """
    )

    result = testrunnerer.runtestrunner(mode, p)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        ["*SETUP    F foobar?'FOO'?", "*SETUP    F foobar?'BAR'?"]
    )


def test_dynamic_fixture_request(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.fixture()
        def dynamically_requested_fixture():
            pass
        @testrunner.fixture()
        def dependent_fixture(request):
            request.getfixturevalue('dynamically_requested_fixture')
        def test_dyn(dependent_fixture):
            pass
    """
    )

    result = testrunnerer.runtestrunner("--setup-only", p)
    assert result.ret == 0

    result.stdout.fnmatch_lines(
        [
            "*SETUP    F dynamically_requested_fixture",
            "*TEARDOWN F dynamically_requested_fixture",
        ]
    )


def test_capturing(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner, sys
        @testrunner.fixture()
        def one():
            sys.stdout.write('this should be captured')
            sys.stderr.write('this should also be captured')
        @testrunner.fixture()
        def two(one):
            assert 0
        def test_capturing(two):
            pass
    """
    )

    result = testrunnerer.runtestrunner("--setup-only", p)
    result.stdout.fnmatch_lines(
        ["this should be captured", "this should also be captured"]
    )


def test_show_fixtures_and_execute_test(testrunnerer: Testrunnerer) -> None:
    """Verify that setups are shown and tests are executed."""
    p = testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.fixture
        def arg():
            assert True
        def test_arg(arg):
            assert False
    """
    )

    result = testrunnerer.runtestrunner("--setup-show", p)
    assert result.ret == 1

    result.stdout.fnmatch_lines(
        ["*SETUP    F arg*", "*test_arg (fixtures used: arg) F*", "*TEARDOWN F arg*"]
    )


def test_setup_show_with_KeyboardInterrupt_in_test(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.fixture
        def arg():
            pass
        def test_arg(arg):
            raise KeyboardInterrupt()
    """
    )
    result = testrunnerer.runtestrunner("--setup-show", p, no_reraise_ctrlc=True)
    result.stdout.fnmatch_lines(
        [
            "*SETUP    F arg*",
            "*test_arg (fixtures used: arg)*",
            "*TEARDOWN F arg*",
            "*! KeyboardInterrupt !*",
            "*= no tests ran in *",
        ]
    )
    assert result.ret == ExitCode.INTERRUPTED


def test_show_fixture_action_with_bytes(testrunnerer: Testrunnerer) -> None:
    # Issue 7126, BytesWarning when using --setup-show with bytes parameter
    test_file = testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.mark.parametrize('data', [b'Hello World'])
        def test_data(data):
            pass
        """
    )
    result = testrunnerer.run(
        sys.executable, "-bb", "-m", "testrunner", "--setup-show", str(test_file)
    )
    assert result.ret == 0
