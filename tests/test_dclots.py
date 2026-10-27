"""Tests for dclots.

Unless a case is marked "constructed", the SSL values come from DC's
Vector Property Map layers on Open Data DC, and the expected fields
match the SQUARE, SUFFIX, LOT, PAR, RES and LOT_TYPE columns DC
publishes alongside them. The comment above each group names the layer.
"""

import math
from pathlib import Path

import pytest

import dclots
from dclots import SSL, Parser


def square_ssl(
    square: str,
    suffix: str | None,
    lot: str | None,
    of_lot_number: int | None = None,
    *,
    is_of_lot: bool = False,
) -> SSL:
    return SSL(
        kind="square",
        square=square,
        suffix=suffix,
        number=None,
        lot=lot,
        is_of_lot=is_of_lot,
        of_lot_number=of_lot_number,
    )


# Common Ownership Lots, Condo Relate Table, Tax Lots.
@pytest.mark.parametrize(
    ("value", "square", "suffix", "lot"),
    [
        ("0254    7003", "0254", None, "7003"),
        ("1929    7056", "1929", None, "7056"),
        ("0772N   7001", "0772", "N", "7001"),
        ("1068SE  0041", "1068", "SE", "0041"),
        ("0667ESS 0802", "0667", "ESS", "0802"),
        ("3377E   0807", "3377", "E", "0807"),
        ("0036    2013", "0036", None, "2013"),
    ],
)
def test_parse_square_ssl(
    value: str, square: str, suffix: str | None, lot: str
) -> None:
    assert dclots.parse(value) == square_ssl(square, suffix, lot)


# Common Ownership Lots (PAR, RES) and Appropriations (APPR).
@pytest.mark.parametrize(
    ("value", "kind", "number", "lot"),
    [
        ("PAR 00870075", "parcel", "0087", "0075"),
        ("PAR 01660072", "parcel", "0166", "0072"),
        ("RES 02010000", "reservation", "0201", "0000"),
        ("RES 015P0000", "reservation", "015P", "0000"),
        ("APPR00070000", "appropriation", "0007", "0000"),
    ],
)
def test_parse_prefixed_ssl(
    value: str, kind: dclots.Kind, number: str, lot: str
) -> None:
    assert dclots.parse(value) == SSL(
        kind=kind,
        square=None,
        suffix=None,
        number=number,
        lot=lot,
        is_of_lot=False,
        of_lot_number=None,
    )


@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        # Tax Lots (Historical): two spaces short.
        ("5557  0802", "5557    0802"),
        # Common Ownership Lots: one space too many.
        ("3569     0071", "3569    0071"),
        # Record Lots (Historical): suffix followed by six spaces.
        ("1264E      0003", "1264E   0003"),
        # Constructed.
        ("0120e   0001", "0120E   0001"),
        ("  0120    0001  ", "0120    0001"),
        ("0120E0001", "0120E   0001"),
        ("01200001", "0120    0001"),
        ("120 0001", "0120    0001"),
        ("120E 0001", "0120E   0001"),
        ("par 0087 0075", "PAR 00870075"),
        ("RES 015P 0000", "RES 015P0000"),
        ("appr00070000", "APPR00070000"),
    ],
)
def test_repairs_case_spacing_and_padding(value: str, normalized: str) -> None:
    assert dclots.normalize(value) == normalized


# Record Lots (Historical).
@pytest.mark.parametrize(
    ("value", "lot"), [("0211    000U", "000U"), ("0132    00B2", "00B2")]
)
def test_parse_letter_lots(value: str, lot: str) -> None:
    result = dclots.parse(value)
    assert result is not None
    assert result.lot == lot
    assert result.lot_type == "record"


# Record Lots (Historical) and Parcel Lots.
@pytest.mark.parametrize(
    ("value", "lot", "of_lot_number"),
    [
        ("1220    0076-of2", "0076", 2),
        ("2894    0041-OF1", "0041", 1),
        ("0368    0028-1", "0028", 1),
        ("2875    000C-1", "000C", 1),
        ("2079    0003-of", "0003", None),
        ("PAR 02410001-of1", "0001", 1),
    ],
)
def test_parse_of_lot_markers(
    value: str, lot: str, of_lot_number: int | None
) -> None:
    result = dclots.parse(value)
    assert result is not None
    assert result.lot == lot
    assert result.is_of_lot is True
    assert result.of_lot_number == of_lot_number


INVALID = [
    None,
    "",
    "   ",
    math.nan,
    120,
    # Record Lots (Historical) and Land Boundary Change.
    "0930    PT OF SQUARE",
    "3561    ORIGINAL",
    "1278    ORIGINAL-2",
    "1256    UNNUMBERED-3",
    "1270    0000-B",
    "0903    S-8-1",
    "0267    OF-41",
    "5730    0004.5",
    "00278    0032",
    "0580NORTH OF 2ND, C, CANAL STS.",
    # Air Rights Lots.
    "0000    Unassessed",
    # Common Ownership Lots.
    "2535    PART",
    # Reservations.
    "RES 06.50000",
    # Constructed.
    "0120",
    "0120    0001-",
    "120 1",
    "0000    0001",
    "Square 120 Lot 1",
]

ACCESSORS = [
    dclots.kind,
    dclots.square,
    dclots.suffix,
    dclots.number,
    dclots.lot,
    dclots.is_of_lot,
    dclots.of_lot_number,
    dclots.has_suffix,
    dclots.lot_type,
    dclots.display,
    dclots.normalize,
]


@pytest.mark.parametrize("value", INVALID)
def test_invalid_values_parse_to_none(value: object) -> None:
    assert dclots.parse(value) is None
    assert dclots.is_valid(value) is False
    for accessor in ACCESSORS:
        assert accessor(value) is None, accessor.__name__


@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        ("0120    0001", "0120    0001"),
        ("0667ESS 0802", "0667ESS 0802"),
        ("PAR 00870075", "PAR 00870075"),
        ("RES 015P0000", "RES 015P0000"),
        ("APPR00070000", "APPR00070000"),
        ("1220    0076-of2", "1220    0076"),
        ("2079    0003-of", "2079    0003"),
        ("PAR 02410001-of1", "PAR 02410001"),
    ],
)
def test_normalize_drops_of_lot_marker_by_default(
    value: str, normalized: str
) -> None:
    assert dclots.normalize(value) == normalized


@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        ("0368    0028-1", "0368    0028-of1"),
        ("2894    0041-OF1", "2894    0041-of1"),
        ("2079    0003-of", "2079    0003-of"),
        ("PAR 02410001-of1", "PAR 02410001-of1"),
        ("0120    0001", "0120    0001"),
    ],
)
def test_normalize_keeps_of_lot_marker(value: str, normalized: str) -> None:
    assert dclots.normalize(value, of_lot="keep") == normalized


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Constructed, at each boundary of DC's lot-number ranges.
        ("0100    0001", "record"),
        ("0100    0799", "record"),
        ("0100    0800", "tax"),
        ("0100    1999", "tax"),
        ("0100    2000", "condo"),
        ("0100    6999", "condo"),
        ("0100    7000", "air_rights"),
        ("0100    9999", "air_rights"),
        ("0100    0000", None),
        # Air Rights Lots (Historical), Tax Lots (Historical), Condo
        # Relate Table, Common Ownership Lots, Appropriations.
        ("1045    7007", "air_rights"),
        ("0507    0811", "tax"),
        ("0036    2013", "condo"),
        ("PAR 00870075", "parcel"),
        ("RES 015P0000", "reservation"),
        ("APPR00070000", "appropriation"),
        ("1220    0076-of2", "record"),
    ],
)
def test_lot_type(value: str, expected: str | None) -> None:
    assert dclots.lot_type(value) == expected


# Common Ownership Lots: DC's LOT_TYPE column disagrees with the range
# rule for these, which is why lot_type() is documented as an inference.
@pytest.mark.parametrize(
    ("value", "lot_type_code", "inferred"),
    [
        ("1301    1082", 1, "tax"),
        ("0542    8000", 2, "air_rights"),
    ],
)
def test_lot_type_is_inferred_from_range(
    value: str, lot_type_code: int, inferred: str
) -> None:
    assert dclots.lot_type(value) == inferred
    assert dclots.lot_type_name(lot_type_code) != inferred


@pytest.mark.parametrize(
    ("code", "name"),
    [
        (1, "record"),
        (2, "tax"),
        (3, "air_rights"),
        (4, "reservation"),
        (5, "appropriation"),
        (6, "parcel"),
        ("1", "record"),
        (" 6 ", "parcel"),
        (3.0, "air_rights"),
        (0, None),
        (7, None),
        (1.5, None),
        (True, None),
        ("x", None),
        (None, None),
        (math.nan, None),
    ],
)
def test_lot_type_name(code: object, name: str | None) -> None:
    assert dclots.lot_type_name(code) == name


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("0120E   0001", "Square 0120E Lot 0001"),
        ("0254    7003", "Square 0254 Lot 7003"),
        ("1220    0076-of2", "Square 1220 Lot 0076 (of-lot 2)"),
        ("2079    0003-of", "Square 2079 Lot 0003 (of-lot)"),
        ("PAR 00870075", "Parcel 0087 Lot 0075"),
        ("RES 015P0000", "Reservation 015P"),
        ("APPR00070000", "Appropriation 0007"),
    ],
)
def test_display(value: str, text: str) -> None:
    assert dclots.display(value) == text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0120E   0001", True),
        ("1068SE  0041", True),
        ("0120    0001", False),
        ("PAR 00870075", False),
        ("RES 015P0000", False),
    ],
)
def test_has_suffix(value: str, expected: bool) -> None:
    assert dclots.has_suffix(value) is expected


def test_accessors_match_parsed_fields() -> None:
    value = "1220N   0076-of2"
    result = dclots.parse(value)
    assert result is not None
    assert dclots.kind(value) == result.kind == "square"
    assert dclots.square(value) == result.square == "1220"
    assert dclots.suffix(value) == result.suffix == "N"
    assert dclots.number(value) is result.number is None
    assert dclots.lot(value) == result.lot == "0076"
    assert dclots.is_of_lot(value) is result.is_of_lot is True
    assert dclots.of_lot_number(value) == result.of_lot_number == 2
    assert dclots.has_suffix(value) is result.has_suffix is True
    assert dclots.lot_type(value) == result.lot_type == "record"
    assert dclots.display(value) == result.display
    assert dclots.normalize(value) == result.normalize() == "1220N   0076"
    assert dclots.is_valid(value) is True


def test_number_accessor() -> None:
    assert dclots.number("PAR 00870075") == "0087"
    assert dclots.number("0120    0001") is None


def test_module_functions_use_default_options() -> None:
    default = Parser()
    for value in ["0368    0028-1", "3561    ORIGINAL", "00278    0032"]:
        assert dclots.parse(value) == default.parse(value)


class TestDashMarkerOption:
    def test_invalid_rejects_bare_dash_number(self) -> None:
        parser = Parser(dash_marker="invalid")
        assert parser.parse("0368    0028-1") is None
        assert parser.is_valid("2875    000C-1") is False

    def test_invalid_still_reads_of_markers(self) -> None:
        parser = Parser(dash_marker="invalid")
        assert parser.of_lot_number("1220    0076-of2") == 2
        assert parser.is_of_lot("2079    0003-of") is True


class TestUnreadableLotOption:
    parser = Parser(unreadable_lot="square_only")

    @pytest.mark.parametrize(
        ("value", "square", "suffix"),
        [
            ("3561    ORIGINAL", "3561", None),
            ("0604W   ORIGINAL", "0604", "W"),
            ("0930    PT OF SQUARE", "0930", None),
            ("1278    ORIGINAL-2", "1278", None),
            ("5730    0004.5", "5730", None),
            ("2535    PART", "2535", None),
        ],
    )
    def test_square_only_keeps_square_and_suffix(
        self, value: str, square: str, suffix: str | None
    ) -> None:
        assert self.parser.parse(value) == square_ssl(square, suffix, None)

    def test_square_only_result_has_no_lot_labels(self) -> None:
        value = "0604W   ORIGINAL"
        assert self.parser.is_valid(value) is True
        assert self.parser.lot_type(value) is None
        assert self.parser.normalize(value) is None
        assert self.parser.display(value) == "Square 0604W"

    @pytest.mark.parametrize(
        "value",
        [
            "0000    Unassessed",
            "0580NORTH OF 2ND, C, CANAL STS.",
            "PT OF SQUARE",
            "0120",
            "12 MAIN ST",
        ],
    )
    def test_square_only_still_needs_a_square(self, value: str) -> None:
        assert self.parser.parse(value) is None

    def test_square_only_leaves_readable_values_alone(self) -> None:
        assert self.parser.parse("0120E   0001") == square_ssl(
            "0120", "E", "0001"
        )


class TestExtraZerosOption:
    parser = Parser(extra_zeros="trim")

    def test_trim_reads_five_digit_square(self) -> None:
        # Record Lots (Historical).
        assert self.parser.normalize("00278    0032") == "0278    0032"

    def test_trim_reads_five_digit_lot(self) -> None:
        # Constructed.
        assert self.parser.normalize("0120    00001") == "0120    0001"

    def test_trim_does_not_split_unspaced_digits(self) -> None:
        # Constructed.
        assert self.parser.normalize("01200001") == "0120    0001"
        assert self.parser.parse("012000001") is None


@pytest.mark.parametrize(
    "options",
    [
        {"dash_marker": "of-lot"},
        {"unreadable_lot": "partial"},
        {"extra_zeros": "strip"},
    ],
)
def test_unknown_option_value_raises(options: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="must be one of"):
        Parser(**options)  # type: ignore[arg-type]


def test_unknown_normalize_of_lot_value_raises() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        dclots.normalize("0120    0001", of_lot="strip")  # type: ignore[arg-type]


def test_module_header_carries_license_and_link() -> None:
    # A copy of the single module file has to carry the license with it.
    source = Path(dclots.__file__).read_text(encoding="utf-8")
    header = source.split('"""', 1)[0]
    header_words = " ".join(
        " ".join(line.removeprefix("#").split())
        for line in header.splitlines()
    ).split()
    license_path = Path(__file__).resolve().parent.parent / "LICENSE"
    license_words = license_path.read_text(encoding="utf-8").split()
    assert license_words[:2] == ["MIT", "License"]
    assert " ".join(license_words[2:]) in " ".join(header_words)
    assert "SPDX-License-Identifier: MIT" in header
    assert "https://github.com/dchud/dclots" in header
