"""Property tests for dclots.

Each test states a rule that holds for every input, and Hypothesis
generates inputs looking for one that breaks it. The SSL strategies
build values from parts that follow DC's format, so a test can compare
what the parser returns with the parts it was given.
"""

import itertools
from typing import Any, get_args

from hypothesis import example, given
from hypothesis import strategies as st

import dclots
from dclots import SSL, Parser

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
WHITESPACE = " \t\u00a0"

PARSERS = [
    Parser(dash_marker=dash, unreadable_lot=unreadable, extra_zeros=zeros)
    for dash, unreadable, zeros in itertools.product(
        get_args(dclots.DashMarker),
        get_args(dclots.UnreadableLot),
        get_args(dclots.ExtraZeros),
    )
]

FIELDS = (
    "kind",
    "square",
    "suffix",
    "number",
    "lot",
    "is_of_lot",
    "of_lot_number",
    "has_suffix",
    "lot_type",
    "display",
)

KINDS: dict[str, dclots.Kind] = {
    "PAR": "parcel",
    "RES": "reservation",
    "APPR": "appropriation",
}


def digits(count: int) -> st.SearchStrategy[str]:
    return st.text("0123456789", min_size=count, max_size=count)


letter = st.sampled_from(LETTERS)
squares = digits(4).filter(lambda square: square != "0000")
suffixes = st.none() | st.text(LETTERS, min_size=1, max_size=4)
lots = (
    digits(4)
    | st.builds(lambda head, tail: head + tail, digits(3), letter)
    | st.builds(lambda a, b, c: a + b + c, digits(2), letter, digits(1))
)
numbers = {
    "PAR": digits(4),
    "RES": st.builds(
        lambda head, tail: head + tail,
        digits(3),
        st.sampled_from("0123456789" + LETTERS),
    ),
    "APPR": digits(4),
}


@st.composite
def markers(draw: st.DrawFn) -> tuple[str, bool, int | None]:
    """An of-lot marker as written, whether it marks an of-lot, its number."""
    form = draw(st.sampled_from(["none", "of", "of_number", "dash_number"]))
    if form == "none":
        return "", False, None
    of = draw(st.sampled_from(["-of", "-OF", "-Of", "-oF"]))
    if form == "of":
        return of, True, None
    number = draw(st.text("0123456789", min_size=1, max_size=4))
    if form == "of_number":
        return of + number, True, int(number)
    return "-" + number, True, int(number)


@st.composite
def ssls(draw: st.DrawFn) -> tuple[str, SSL]:
    """A canonical SSL and the record it should parse to."""
    marker, is_of_lot, of_lot_number = draw(markers())
    prefix = draw(st.sampled_from(["", "PAR", "RES", "APPR"]))
    if not prefix:
        square, suffix, lot = draw(squares), draw(suffixes), draw(lots)
        text = f"{square}{suffix or '':<4}{lot}{marker}"
        expected = SSL(
            "square", square, suffix, None, lot, is_of_lot, of_lot_number
        )
    else:
        number, lot = draw(numbers[prefix]), draw(digits(4))
        text = f"{prefix:<4}{number}{lot}{marker}"
        expected = SSL(
            KINDS[prefix], None, None, number, lot, is_of_lot, of_lot_number
        )
    return text, expected


@st.composite
def respelled_ssls(draw: st.DrawFn) -> tuple[str, SSL]:
    """An SSL written with the variations the parser repairs."""
    _, expected = draw(ssls())
    marker = draw(st.just(_marker_text(expected)))
    gap = st.text(WHITESPACE, max_size=6)
    if expected.kind == "square":
        assert expected.square is not None and expected.lot is not None
        suffix = expected.suffix or ""
        between = draw(gap)
        square = expected.square
        # A square may drop its leading zeros when a suffix or a space
        # separates it from the lot.
        if (suffix or between) and draw(st.booleans()):
            square = square.lstrip("0")
        text = f"{square}{suffix}{between}{expected.lot}{marker}"
    else:
        prefix = next(p for p, kind in KINDS.items() if kind == expected.kind)
        text = (
            f"{prefix}{draw(gap)}{expected.number}{draw(gap)}"
            f"{expected.lot}{marker}"
        )
    flips = draw(
        st.lists(st.booleans(), min_size=len(text), max_size=len(text))
    )
    text = "".join(
        char.lower() if flip else char
        for char, flip in zip(text, flips, strict=True)
    )
    return draw(gap) + text + draw(gap), expected


def _marker_text(result: SSL) -> str:
    if not result.is_of_lot:
        return ""
    if result.of_lot_number is None:
        return "-of"
    return f"-of{result.of_lot_number}"


def first(pair: tuple[str, SSL]) -> str:
    return pair[0]


ssl_like_text = st.text(
    "0123456789 ABEFNOPRSW-.of\t\u00a0", max_size=24
) | st.builds(
    lambda head, tail: head + tail,
    squares,
    st.text("0123456789 ABEFNOPRT-.of", max_size=12),
)

text_values = st.one_of(
    st.text(),
    ssl_like_text,
    ssls().map(first),
    respelled_ssls().map(first),
)

any_values: st.SearchStrategy[Any] = st.one_of(
    text_values,
    st.binary(),
    st.integers(),
    st.floats(),
    st.booleans(),
    st.none(),
)


@given(any_values)
@example("0120    0001-" + "1" * 5000)
@example("0120    0001-of" + "1" * 5000)
@example("0120\u00df   0001")
@example("0667e\u017f\u017f 0802")
def test_every_function_agrees_with_parse_and_never_raises(
    value: object,
) -> None:
    for parser in PARSERS:
        result = parser.parse(value)
        assert parser.is_valid(value) is (result is not None)
        for field in FIELDS:
            got = getattr(parser, field)(value)
            assert got == (None if result is None else getattr(result, field))
        for of_lot in ("drop", "keep"):
            normalized = parser.normalize(value, of_lot=of_lot)
            if result is None or result.lot is None:
                assert normalized is None
            else:
                assert normalized == result.normalize(of_lot)


@given(ssls())
def test_generated_ssls_parse_to_their_parts(case: tuple[str, SSL]) -> None:
    text, expected = case
    assert dclots.parse(text) == expected
    plain = dclots.normalize(text)
    assert plain is not None
    assert len(plain) == 12
    assert dclots.normalize(text, of_lot="keep") == plain + _marker_text(
        expected
    )


@given(respelled_ssls())
def test_repairs_do_not_change_the_result(case: tuple[str, SSL]) -> None:
    text, expected = case
    assert dclots.parse(text) == expected


@given(text_values)
def test_normalized_ssls_parse_to_the_same_result(value: str) -> None:
    for parser in PARSERS:
        result = parser.parse(value)
        if result is None or result.lot is None:
            continue
        normalized = parser.normalize(value, of_lot="keep")
        assert normalized is not None
        assert parser.parse(normalized) == result
        assert parser.normalize(normalized, of_lot="keep") == normalized


@given(text_values)
@example("PAR 00000075")
def test_options_relate_as_documented(value: str) -> None:
    default = Parser().parse(value)
    if default is not None:
        assert Parser(unreadable_lot="square_only").parse(value) == default
        assert Parser(extra_zeros="trim").parse(value) == default
    strict = Parser(dash_marker="invalid").parse(value)
    if strict is not None:
        assert strict == default


@given(squares, suffixes, digits(4))
def test_lot_type_follows_the_lot_number_ranges(
    square: str, suffix: str | None, lot: str
) -> None:
    number = int(lot)
    if number == 0:
        expected = None
    elif number < 800:
        expected = "record"
    elif number < 2000:
        expected = "tax"
    elif number < 7000:
        expected = "condo"
    else:
        expected = "air_rights"
    assert dclots.lot_type(f"{square}{suffix or '':<4}{lot}") == expected


@given(st.integers())
def test_lot_type_name_names_codes_one_to_seven(code: int) -> None:
    name = dclots.lot_type_name(code)
    assert (name is not None) is (1 <= code <= 7)
    assert dclots.lot_type_name(float(code)) == name
    if code >= 0:
        assert dclots.lot_type_name(str(code)) == name


@given(
    st.one_of(
        st.integers(),
        st.floats(),
        st.fractions(),
        st.decimals(),
        st.text(),
        st.booleans(),
        st.none(),
    )
)
def test_lot_type_name_never_raises(code: object) -> None:
    name = dclots.lot_type_name(code)
    assert name is None or isinstance(name, str)


@given(
    ssls().map(first),
    st.characters(min_codepoint=128).filter(lambda char: not char.isspace()),
    st.data(),
)
def test_non_ascii_characters_make_a_value_invalid(
    text: str, char: str, data: st.DataObject
) -> None:
    position = data.draw(st.integers(0, len(text)))
    value = text[:position] + char + text[position:]
    for parser in PARSERS:
        assert parser.parse(value) is None
