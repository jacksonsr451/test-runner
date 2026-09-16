from __future__ import annotations

from collections import ChainMap
from collections import Counter
from collections import defaultdict
from collections import deque
from collections import OrderedDict
from collections import UserDict
from collections import UserList
from collections import UserString
from dataclasses import dataclass
import textwrap
from types import MappingProxyType
from types import SimpleNamespace
from typing import Any

from _testrunner._io.pprint import _safe_tuple
from _testrunner._io.pprint import _wrap_bytes_repr
from _testrunner._io.pprint import PrettyPrinter
import testrunner


@dataclass
class EmptyDataclass:
    pass


@dataclass
class DataclassWithOneItem:
    foo: str


@dataclass
class DataclassWithTwoItems:
    foo: str
    bar: str


@testrunner.mark.parametrize(
    ("data", "expected"),
    (
        testrunner.param(
            EmptyDataclass(),
            "EmptyDataclass()",
            id="dataclass-empty",
        ),
        testrunner.param(
            DataclassWithOneItem(foo="bar"),
            """
            DataclassWithOneItem(
                foo='bar',
            )
            """,
            id="dataclass-one-item",
        ),
        testrunner.param(
            DataclassWithTwoItems(foo="foo", bar="bar"),
            """
            DataclassWithTwoItems(
                foo='foo',
                bar='bar',
            )
            """,
            id="dataclass-two-items",
        ),
        testrunner.param(
            {},
            "{}",
            id="dict-empty",
        ),
        testrunner.param(
            {"one": 1},
            """
            {
                'one': 1,
            }
            """,
            id="dict-one-item",
        ),
        testrunner.param(
            {"one": 1, "two": 2},
            """
            {
                'one': 1,
                'two': 2,
            }
            """,
            id="dict-two-items",
        ),
        testrunner.param(OrderedDict(), "OrderedDict()", id="ordereddict-empty"),
        testrunner.param(
            OrderedDict({"one": 1}),
            """
            OrderedDict({
                'one': 1,
            })
            """,
            id="ordereddict-one-item",
        ),
        testrunner.param(
            OrderedDict({"one": 1, "two": 2}),
            """
            OrderedDict({
                'one': 1,
                'two': 2,
            })
            """,
            id="ordereddict-two-items",
        ),
        testrunner.param(
            [],
            "[]",
            id="list-empty",
        ),
        testrunner.param(
            [1],
            """
            [
                1,
            ]
            """,
            id="list-one-item",
        ),
        testrunner.param(
            [1, 2],
            """
            [
                1,
                2,
            ]
            """,
            id="list-two-items",
        ),
        testrunner.param(
            tuple(),
            "()",
            id="tuple-empty",
        ),
        testrunner.param(
            (1,),
            """
            (
                1,
            )
            """,
            id="tuple-one-item",
        ),
        testrunner.param(
            (1, 2),
            """
            (
                1,
                2,
            )
            """,
            id="tuple-two-items",
        ),
        testrunner.param(
            set(),
            "set()",
            id="set-empty",
        ),
        testrunner.param(
            {1},
            """
            {
                1,
            }
            """,
            id="set-one-item",
        ),
        testrunner.param(
            {1, 2},
            """
            {
                1,
                2,
            }
            """,
            id="set-two-items",
        ),
        testrunner.param(
            MappingProxyType({}),
            "mappingproxy({})",
            id="mappingproxy-empty",
        ),
        testrunner.param(
            MappingProxyType({"one": 1}),
            """
            mappingproxy({
                'one': 1,
            })
            """,
            id="mappingproxy-one-item",
        ),
        testrunner.param(
            MappingProxyType({"one": 1, "two": 2}),
            """
            mappingproxy({
                'one': 1,
                'two': 2,
            })
            """,
            id="mappingproxy-two-items",
        ),
        testrunner.param(
            SimpleNamespace(),
            "namespace()",
            id="simplenamespace-empty",
        ),
        testrunner.param(
            SimpleNamespace(one=1),
            """
            namespace(
                one=1,
            )
            """,
            id="simplenamespace-one-item",
        ),
        testrunner.param(
            SimpleNamespace(one=1, two=2),
            """
            namespace(
                one=1,
                two=2,
            )
            """,
            id="simplenamespace-two-items",
        ),
        testrunner.param(
            defaultdict(str), "defaultdict(<class 'str'>, {})", id="defaultdict-empty"
        ),
        testrunner.param(
            defaultdict(str, {"one": "1"}),
            """
            defaultdict(<class 'str'>, {
                'one': '1',
            })
            """,
            id="defaultdict-one-item",
        ),
        testrunner.param(
            defaultdict(str, {"one": "1", "two": "2"}),
            """
            defaultdict(<class 'str'>, {
                'one': '1',
                'two': '2',
            })
            """,
            id="defaultdict-two-items",
        ),
        testrunner.param(
            Counter(),
            "Counter()",
            id="counter-empty",
        ),
        testrunner.param(
            Counter("1"),
            """
            Counter({
                '1': 1,
            })
            """,
            id="counter-one-item",
        ),
        testrunner.param(
            Counter("121"),
            """
            Counter({
                '1': 2,
                '2': 1,
            })
            """,
            id="counter-two-items",
        ),
        testrunner.param(ChainMap(), "ChainMap({})", id="chainmap-empty"),
        testrunner.param(
            ChainMap({"one": 1, "two": 2}),
            """
            ChainMap(
                {
                    'one': 1,
                    'two': 2,
                },
            )
            """,
            id="chainmap-one-item",
        ),
        testrunner.param(
            ChainMap({"one": 1}, {"two": 2}),
            """
            ChainMap(
                {
                    'one': 1,
                },
                {
                    'two': 2,
                },
            )
            """,
            id="chainmap-two-items",
        ),
        testrunner.param(
            deque(),
            "deque([])",
            id="deque-empty",
        ),
        testrunner.param(
            deque([1]),
            """
            deque([
                1,
            ])
            """,
            id="deque-one-item",
        ),
        testrunner.param(
            deque([1, 2]),
            """
            deque([
                1,
                2,
            ])
            """,
            id="deque-two-items",
        ),
        testrunner.param(
            deque([1, 2], maxlen=3),
            """
            deque(maxlen=3, [
                1,
                2,
            ])
            """,
            id="deque-maxlen",
        ),
        testrunner.param(frozenset(), "frozenset()", id="frozenset-empty"),
        testrunner.param(
            frozenset({1, 2, 3}),
            """
            frozenset({
                1,
                2,
                3,
            })
            """,
            id="frozenset-items",
        ),
        testrunner.param(UserDict(), "{}", id="userdict-empty"),
        testrunner.param(
            UserDict({"one": 1, "two": 2}),
            """
            {
                'one': 1,
                'two': 2,
            }
            """,
            id="userdict-items",
        ),
        testrunner.param(UserList(), "[]", id="userlist-empty"),
        testrunner.param(
            UserList([1, 2]),
            """
            [
                1,
                2,
            ]
            """,
            id="userlist-items",
        ),
        testrunner.param(UserString("hello world"), "'hello world'", id="userstring"),
        testrunner.param(b"short", "(b'short')", id="bytes-short"),
        testrunner.param(
            b"x" * 100,
            "(b'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'\n"
            " b'xxxxxxxxxxxxxxxxxxxxxxxx')",
            id="bytes-long",
        ),
        testrunner.param(
            # Length not a multiple of 4 so the final 4-byte group lands
            # exactly on ``last`` and exercises the allowance trim.
            b"z" * 102,
            "(b'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'\n"
            " b'zzzzzzzzzzzzzzzzzzzzzzzzzz')",
            id="bytes-long-unaligned",
        ),
        testrunner.param(
            bytearray(b"short"), "bytearray(b'short')", id="bytearray-short"
        ),
        testrunner.param(
            bytearray(b"y" * 100),
            "bytearray(b'yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy'\n"
            "          b'yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy')",
            id="bytearray-long",
        ),
        testrunner.param(
            "word " * 30,
            "('word word word word word word word word word word word word word word word '\n"
            " 'word word word word word word word word word word word word word word word ')",
            id="str-long-wrap",
        ),
        testrunner.param(
            "line1\nline2\nline3",
            "('line1\\n'\n 'line2\\n'\n 'line3')",
            id="str-multiline",
        ),
        testrunner.param("", "''", id="str-empty"),
        testrunner.param("hello", "'hello'", id="str-single-chunk"),
        testrunner.param(
            ["word " * 30],
            "[\n"
            "    'word word word word word word word word word word word word word word '\n"
            "    'word word word word word word word word word word word word word word '\n"
            "    'word word ',\n"
            "]",
            id="str-nested-wrap",
        ),
        testrunner.param(b"abc", "b'abc'", id="bytes-le-4"),
        testrunner.param(
            "word " * 30 + "\nshort",
            "('word word word word word word word word word word word word word word word '\n"
            " 'word word word word word word word word word word word word word word word \\n'\n"
            " 'short')",
            id="str-wrap-then-line",
        ),
        testrunner.param({(): 0}, "{\n    (): 0,\n}", id="dict-empty-tuple-key"),
        testrunner.param(
            {(1, 2): 0},
            """
            {
                (1, 2): 0,
            }
            """,
            id="dict-tuple-key",
        ),
        testrunner.param(
            {(1,): 0},
            """
            {
                (1,): 0,
            }
            """,
            id="dict-singleton-tuple-key",
        ),
        testrunner.param(
            {
                "chainmap": ChainMap({"one": 1}, {"two": 2}),
                "counter": Counter("122"),
                "dataclass": DataclassWithTwoItems(foo="foo", bar="bar"),
                "defaultdict": defaultdict(str, {"one": "1", "two": "2"}),
                "deque": deque([1, 2], maxlen=3),
                "dict": {"one": 1, "two": 2},
                "list": [1, 2],
                "mappingproxy": MappingProxyType({"one": 1, "two": 2}),
                "ordereddict": OrderedDict({"one": 1, "two": 2}),
                "set": {1, 2},
                "simplenamespace": SimpleNamespace(one=1, two=2),
                "tuple": (1, 2),
            },
            """
            {
                'chainmap': ChainMap(
                    {
                        'one': 1,
                    },
                    {
                        'two': 2,
                    },
                ),
                'counter': Counter({
                    '2': 2,
                    '1': 1,
                }),
                'dataclass': DataclassWithTwoItems(
                    foo='foo',
                    bar='bar',
                ),
                'defaultdict': defaultdict(<class 'str'>, {
                    'one': '1',
                    'two': '2',
                }),
                'deque': deque(maxlen=3, [
                    1,
                    2,
                ]),
                'dict': {
                    'one': 1,
                    'two': 2,
                },
                'list': [
                    1,
                    2,
                ],
                'mappingproxy': mappingproxy({
                    'one': 1,
                    'two': 2,
                }),
                'ordereddict': OrderedDict({
                    'one': 1,
                    'two': 2,
                }),
                'set': {
                    1,
                    2,
                },
                'simplenamespace': namespace(
                    one=1,
                    two=2,
                ),
                'tuple': (
                    1,
                    2,
                ),
            }
            """,
            id="deep-example",
        ),
    ),
)
def test_consistent_pretty_printer(data: Any, expected: str) -> None:
    assert PrettyPrinter().pformat(data) == textwrap.dedent(expected).strip()


class TestPformatLines:
    """``pformat_lines`` returns the pretty-printed lines, pulling from
    the lazy formatter only until a line/char budget is reached so an
    input a downstream truncator will clip anyway is never fully built.
    """

    def test_no_budget_matches_pformat_splitlines(self) -> None:
        pp = PrettyPrinter()
        data = list(range(50))
        assert pp.pformat_lines(data) == pp.pformat(data).splitlines()

    def test_under_budget_is_complete_and_a_prefix(self) -> None:
        # When the whole thing fits, the result is the full pformat,
        # regardless of how the budget was reached.
        pp = PrettyPrinter()
        data = list(range(5))
        full = pp.pformat(data).splitlines()
        assert pp.pformat_lines(data, max_lines=11) == full
        assert pp.pformat_lines(data, max_chars=10_000) == full

    def test_line_budget_stops_early(self) -> None:
        pp = PrettyPrinter()
        # 50 scalars, one per line, budget well below 50.
        full = pp.pformat(list(range(50))).splitlines()
        lines = pp.pformat_lines(list(range(50)), max_lines=11)
        assert len(lines) <= 11 + 1  # budget, plus a trailing partial line
        # everything but the last line (which may stop mid-line) is a
        # prefix of the full output
        assert lines[:-1] == full[: len(lines) - 1]

    def test_char_budget_stops_early(self) -> None:
        # A *flat* container of huge strings has few lines but explodes on
        # chars; a line-only budget wouldn't stop it. The char budget must.
        pp = PrettyPrinter()
        data = ["x" * 100_000, "y" * 100_000, "z" * 100_000]
        lines = pp.pformat_lines(data, max_chars=640)
        assert sum(len(line) for line in lines) < 200_000  # bailed, didn't format all 3

    def test_nested_element_respects_line_budget(self) -> None:
        # ``len(object)`` is only a *lower* bound on the line count: a
        # single nested element expands to many lines. The lazy pull must
        # stop regardless of the container's element count.
        pp = PrettyPrinter()
        for data in ([{i: "x" * 40 for i in range(50)}], {1: list(range(100))}):
            lines = pp.pformat_lines(data, max_lines=11)
            assert len(lines) <= 11 + 1

    def test_nested_dataclass_element_respects_line_budget(self) -> None:
        @dataclass
        class Many:
            a: int
            b: int
            c: int
            d: int
            e: int
            f: int
            g: int
            h: int

        pp = PrettyPrinter()
        lines = pp.pformat_lines([Many(*range(8))], max_lines=4)
        assert len(lines) <= 4 + 1
        assert len(lines) < len(pp.pformat([Many(*range(8))]).splitlines())

    def test_sized_non_iterable_does_not_raise(self) -> None:
        class Sized:
            def __len__(self) -> int:
                return 3  # pragma: no cover - exists only to make the type Sized

        pp = PrettyPrinter()
        obj = Sized()
        assert pp.pformat_lines(obj, max_lines=5) == pp.pformat(obj).splitlines()


def test_pformat_sorts_heterogeneous_set() -> None:
    # The set sort tries a natural sort first and falls back to a key
    # that compares the element types' names only for unorderable
    # mixes; both must succeed.
    pp = PrettyPrinter()
    assert pp.pformat({3, 1, 2}) == "{\n    1,\n    2,\n    3,\n}"
    # Mixed unorderable types must not raise; the fallback orders by type
    # name (ints before strs), then by value.
    assert pp.pformat({1, "a", 2, "b"}) == "{\n    1,\n    2,\n    'a',\n    'b',\n}"


@testrunner.mark.parametrize(
    "kwargs",
    [
        testrunner.param({"indent": -1}, id="indent-negative"),
        testrunner.param({"depth": 0}, id="depth-zero"),
        testrunner.param({"width": 0}, id="width-zero"),
    ],
)
def test_invalid_constructor_args_raise(kwargs: dict[str, int]) -> None:
    with testrunner.raises(ValueError):
        PrettyPrinter(**kwargs)


def test_recursive_list_shows_recursion_marker() -> None:
    pp = PrettyPrinter()
    a: list[Any] = [1]
    a.append(a)
    out = pp.pformat(a)
    assert f"<Recursion on list with id={id(a)}>" in out


def test_recursive_namespace_shows_ellipsis() -> None:
    # A self-referential namespace must render the cycle as ``...`` rather
    # than recursing forever.
    ns = SimpleNamespace(x=1)
    ns.self = ns
    out = PrettyPrinter().pformat(ns)
    assert "self=..." in out


def test_depth_limit_truncates_nested_container() -> None:
    # ``depth`` caps nesting in the ``_safe_repr`` fallback: containers
    # past the limit collapse to ``...``.
    pp = PrettyPrinter(depth=1)
    assert pp.pformat({((1, 2),): 0}) == "{\n    (...,): 0,\n}"


def test_simplenamespace_subclass_uses_class_name() -> None:
    # Plain ``SimpleNamespace`` prints as ``namespace(...)``; a subclass
    # uses its own class name instead.
    class MyNamespace(SimpleNamespace):
        pass

    pp = PrettyPrinter()
    assert pp.pformat(MyNamespace(one=1)) == "MyNamespace(\n    one=1,\n)"


def test_safe_tuple_sorts_unorderable_pairs() -> None:
    # ``_safe_tuple`` wraps each element of a 2-tuple in ``_safe_key`` so a
    # list of pairs with unorderable elements can be sorted without raising.
    pairs = [(2, "b"), (1, "a"), ("z", 3)]
    assert sorted(pairs, key=_safe_tuple)  # does not raise


class _HashableDict(dict[Any, Any]):
    # ``dict`` subclasses that are hashable can be used as dict keys, which
    # is the only way the ``_safe_repr`` ``dict`` branch is reached.
    def __hash__(self) -> int:  # type: ignore[override]
        return id(self)


class _HashableList(list[Any]):
    # Likewise for ``list`` and the ``_safe_repr`` ``list`` branch.
    def __hash__(self) -> int:  # type: ignore[override]
        return id(self)


@testrunner.mark.parametrize(
    ("key", "expected"),
    [
        testrunner.param(_HashableDict(), "{\n    {}: 0,\n}", id="empty-dict-key"),
        testrunner.param(
            _HashableDict({"a": 1}), "{\n    {'a': 1}: 0,\n}", id="dict-key"
        ),
        testrunner.param(_HashableList(), "{\n    []: 0,\n}", id="empty-list-key"),
        testrunner.param(_HashableList([1, 2]), "{\n    [1, 2]: 0,\n}", id="list-key"),
    ],
)
def test_hashable_container_subclass_as_key(key: Any, expected: str) -> None:
    # A hashable ``dict``/``list`` subclass key is rendered via the
    # ``_safe_repr`` fallback rather than a per-type dispatcher.
    assert PrettyPrinter().pformat({key: 0}) == expected


def test_safe_repr_depth_limit_on_dict_key() -> None:
    pp = PrettyPrinter(depth=1)
    assert pp.pformat({_HashableDict({"a": 1}): 0}) == "{\n    {...}: 0,\n}"


def test_safe_repr_recursion_marker() -> None:
    # Self-referential containers reached through ``_safe_repr`` (as dict
    # keys) must terminate with a recursion marker, for both the ``dict``
    # branch and the ``tuple``/``list`` branch.
    hd = _HashableDict()
    hd["self"] = hd
    assert "<Recursion on _HashableDict" in PrettyPrinter().pformat({hd: 0})

    hl = _HashableList()
    hl.append(hl)
    assert "<Recursion on _HashableList" in PrettyPrinter().pformat({(hl,): 0})


def test_wrap_bytes_repr_edges() -> None:
    # Empty input yields nothing; a width too small for a group still
    # emits each group rather than dropping bytes.
    assert list(_wrap_bytes_repr(b"", 80, 0)) == []
    assert list(_wrap_bytes_repr(b"abcdefgh", 6, 0)) == ["b'abcd'", "b'efgh'"]
