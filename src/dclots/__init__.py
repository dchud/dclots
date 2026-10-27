# dclots: parse and label District of Columbia SSL (square, suffix, lot)
# identifiers. https://github.com/dchud/dclots
#
# SPDX-License-Identifier: MIT
#
# Copyright (c) 2026 Daniel Chudnov
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Parse and label District of Columbia SSL (square, suffix, lot) values.

An SSL is twelve characters: a four-digit square, a four-character
suffix padded with spaces, and a four-character lot, as in
``0120E   0001``. Parcels, reservations and appropriations put a prefix
and a number where the square and suffix go: ``PAR 00870075``,
``RES 015P0000``, ``APPR00070000``.

The module-level functions use the default options. To change an
option, create a :class:`Parser` and call the same functions on it::

    parser = Parser(unreadable_lot="square_only")
    parser.square("3561    ORIGINAL")

Every function takes any value, so each one works as a dataframe UDF.
The accessors return None for a value that doesn't parse, and
``is_valid`` returns False.

This module has no dependencies outside the standard library. To use it
without installing the package, copy this file into a project as
``dclots.py``.
"""

from __future__ import annotations

import numbers
import re
from dataclasses import dataclass
from typing import Literal, get_args

__all__ = [
    "SSL",
    "DashMarker",
    "ExtraZeros",
    "Kind",
    "LotType",
    "OfLot",
    "Parser",
    "UnreadableLot",
    "display",
    "has_suffix",
    "is_of_lot",
    "is_valid",
    "kind",
    "lot",
    "lot_type",
    "lot_type_name",
    "normalize",
    "number",
    "of_lot_number",
    "parse",
    "square",
    "suffix",
]

Kind = Literal["square", "parcel", "reservation", "appropriation"]
LotType = Literal[
    "record",
    "tax",
    "condo",
    "air_rights",
    "parcel",
    "reservation",
    "appropriation",
]

DashMarker = Literal["of_lot", "invalid"]
UnreadableLot = Literal["invalid", "square_only"]
ExtraZeros = Literal["invalid", "trim"]
OfLot = Literal["drop", "keep"]

# A lot is four digits, or a letter lot such as 000A or 00B2.
_LOT = r"[0-9]{4}|[0-9]{3}[A-Z]|[0-9]{2}[A-Z][0-9]"
# An of-lot marker: -of2, -OF1, a bare -of, or -1.
_MARKER = r"-OF[0-9]*|-[0-9]+"

_SQUARE_SSL = re.compile(
    # A square written with fewer than four digits needs a suffix or a
    # space after it, so a run of digits is never split two ways.
    r"(?P<square>[0-9]{4}|[0-9]{1,3}(?=[A-Z\s]))"
    r"(?P<suffix>[A-Z]{1,4})?"
    r"\s*"
    rf"(?P<lot>{_LOT})"
    rf"(?P<marker>{_MARKER})?"
)
_PREFIXED_SSL = re.compile(
    r"(?P<prefix>PAR|RES|APPR)\s*"
    r"(?P<number>[0-9A-Z]{4})\s*"
    r"(?P<lot>[0-9]{4})"
    rf"(?P<marker>{_MARKER})?"
)
_SQUARE_ONLY = re.compile(
    r"(?P<square>[0-9]{4})(?P<suffix>[A-Z]{1,4})?\s+\S.*"
)
# Leading zeros that make a free-standing number longer than four
# digits. The guards keep an unspaced run like 01200001 intact.
_EXTRA_ZEROS = re.compile(r"(?<![0-9A-Z])0+(?=[0-9]{4}(?![0-9]))")

_PREFIX_KINDS: dict[str, Kind] = {
    "PAR": "parcel",
    "RES": "reservation",
    "APPR": "appropriation",
}
# Reservation numbers can end in a letter (015P); the others are digits.
_NUMBERS = {
    "PAR": re.compile(r"[0-9]{4}"),
    "RES": re.compile(r"[0-9]{3}[0-9A-Z]"),
    "APPR": re.compile(r"[0-9]{4}"),
}
_PREFIXES: dict[Kind, str] = {
    "parcel": "PAR ",
    "reservation": "RES ",
    "appropriation": "APPR",
}
_PREFIX_LOT_TYPES: dict[Kind, LotType] = {
    "parcel": "parcel",
    "reservation": "reservation",
    "appropriation": "appropriation",
}
_LOT_TYPE_CODES: dict[int, LotType] = {
    1: "record",
    2: "tax",
    3: "air_rights",
    4: "reservation",
    5: "appropriation",
    6: "parcel",
    7: "condo",
}


def _digits_to_int(digits: str) -> int | None:
    # int() refuses digit strings longer than its limit of 4,300 digits.
    try:
        return int(digits)
    except ValueError:
        return None


def _check_choice(name: str, value: object, choices: tuple[str, ...]) -> None:
    if value not in choices:
        allowed = ", ".join(repr(choice) for choice in choices)
        raise ValueError(f"{name} must be one of {allowed}; got {value!r}")


@dataclass(frozen=True, slots=True)
class SSL:
    """A parsed SSL.

    ``square`` and ``suffix`` are set for square SSLs. Parcels,
    reservations and appropriations have a ``number`` instead. ``lot``
    is the last four characters, without any of-lot marker; it is None
    only for a result read with ``unreadable_lot="square_only"``.
    """

    kind: Kind
    square: str | None
    suffix: str | None
    number: str | None
    lot: str | None
    is_of_lot: bool
    of_lot_number: int | None

    @property
    def has_suffix(self) -> bool:
        """True for a square with a suffix, such as 0120E."""
        return self.suffix is not None

    @property
    def lot_type(self) -> LotType | None:
        """The lot type implied by the prefix or the lot number.

        Square lots are typed by DC's numbering ranges: 0001-0799
        record, 0800-1999 tax, 2000-6999 condo, 7000 and above air
        rights. Letter lots are record lots. Lot 0000 has no type.
        """
        if self.kind != "square":
            return _PREFIX_LOT_TYPES[self.kind]
        if self.lot is None:
            return None
        if not self.lot.isdigit():
            return "record"
        lot_number = int(self.lot)
        if lot_number == 0:
            return None
        if lot_number < 800:
            return "record"
        if lot_number < 2000:
            return "tax"
        if lot_number < 7000:
            return "condo"
        return "air_rights"

    @property
    def display(self) -> str:
        """A readable label, such as ``Square 0120E Lot 0001``.

        The lot is left out when it is 0000 or missing.
        """
        if self.kind == "square":
            text = f"Square {self.square}{self.suffix or ''}"
        else:
            text = f"{self.kind.capitalize()} {self.number}"
        if self.lot is not None and self.lot != "0000":
            text += f" Lot {self.lot}"
        if self.is_of_lot:
            if self.of_lot_number is None:
                text += " (of-lot)"
            else:
                text += f" (of-lot {self.of_lot_number})"
        return text

    def normalize(self, of_lot: OfLot = "drop") -> str | None:
        """The canonical twelve-character SSL, or None without a lot.

        ``of_lot="drop"`` leaves out any of-lot marker, for joining
        against data keyed by plain SSLs. ``of_lot="keep"`` appends it
        as ``-of`` and its number.
        """
        _check_choice("of_lot", of_lot, get_args(OfLot))
        if self.lot is None:
            return None
        if self.kind == "square":
            text = f"{self.square}{self.suffix or '':<4}{self.lot}"
        else:
            text = f"{_PREFIXES[self.kind]}{self.number}{self.lot}"
        if of_lot == "keep" and self.is_of_lot:
            text += "-of"
            if self.of_lot_number is not None:
                text += str(self.of_lot_number)
        return text


@dataclass(frozen=True)
class Parser:
    """Parse SSLs with a fixed set of options.

    ``dash_marker`` sets how a trailing ``-N`` on a lot is read.
    ``"of_lot"`` reads it as an of-lot marker, the same as ``-ofN``.
    ``"invalid"`` rejects the value; ``-ofN`` is still read.

    ``unreadable_lot`` sets what happens when a value starts with a
    four-digit square, optionally with a suffix, followed by a space and
    text that is not a lot. ``"invalid"`` rejects the value.
    ``"square_only"`` returns the square and suffix with no lot.

    ``extra_zeros`` sets how a number written with more than four digits
    is read. ``"invalid"`` rejects the value. ``"trim"`` drops the
    leading zeros of a run of digits when exactly four digits remain and
    no letter or digit comes before the run, so ``00278    0032`` reads
    as square 0278 and ``PAR 00087 0075`` as parcel 0087.

    With ``unreadable_lot="square_only"``, a value that another option
    rejects for its lot, such as ``0368    0028-1`` under
    ``dash_marker="invalid"``, reads as a square with no lot.
    """

    dash_marker: DashMarker = "of_lot"
    unreadable_lot: UnreadableLot = "invalid"
    extra_zeros: ExtraZeros = "invalid"

    def __post_init__(self) -> None:
        _check_choice("dash_marker", self.dash_marker, get_args(DashMarker))
        _check_choice(
            "unreadable_lot", self.unreadable_lot, get_args(UnreadableLot)
        )
        _check_choice("extra_zeros", self.extra_zeros, get_args(ExtraZeros))

    def parse(self, value: object) -> SSL | None:
        """Parse an SSL, or return None if it can't be read.

        Case, surrounding whitespace, the spacing between fields and a
        square missing its leading zeros are repaired.
        """
        if not isinstance(value, str):
            return None
        text = value.strip()
        # upper() turns some non-ASCII letters into ASCII ones (ß into
        # SS), so non-ASCII characters other than whitespace are rejected
        # before it runs.
        if not "".join(text.split()).isascii():
            return None
        text = text.upper()
        if self.extra_zeros == "trim":
            text = _EXTRA_ZEROS.sub("", text)
        return (
            self._parse_square(text)
            or self._parse_prefixed(text)
            or self._parse_square_only(text)
        )

    def _parse_square(self, text: str) -> SSL | None:
        match = _SQUARE_SSL.fullmatch(text)
        if match is None:
            return None
        square = match["square"].zfill(4)
        marker = self._read_marker(match["marker"])
        if square == "0000" or marker is None:
            return None
        return SSL(
            "square", square, match["suffix"], None, match["lot"], *marker
        )

    def _parse_prefixed(self, text: str) -> SSL | None:
        match = _PREFIXED_SSL.fullmatch(text)
        if match is None:
            return None
        prefix, number = match["prefix"], match["number"]
        marker = self._read_marker(match["marker"])
        if not _NUMBERS[prefix].fullmatch(number) or marker is None:
            return None
        return SSL(
            _PREFIX_KINDS[prefix], None, None, number, match["lot"], *marker
        )

    def _parse_square_only(self, text: str) -> SSL | None:
        if self.unreadable_lot != "square_only":
            return None
        match = _SQUARE_ONLY.fullmatch(text)
        if match is None or match["square"] == "0000":
            return None
        return SSL(
            "square", match["square"], match["suffix"], None, None, False, None
        )

    def _read_marker(
        self, marker: str | None
    ) -> tuple[bool, int | None] | None:
        """Read an of-lot marker as (is_of_lot, number); None rejects it."""
        if marker is None:
            return False, None
        if marker.startswith("-OF"):
            digits = marker[3:]
        elif self.dash_marker == "of_lot":
            digits = marker[1:]
        else:
            return None
        if not digits:
            return True, None
        number = _digits_to_int(digits)
        return None if number is None else (True, number)

    def is_valid(self, value: object) -> bool:
        """True if the value parses."""
        return self.parse(value) is not None

    def kind(self, value: object) -> Kind | None:
        """``square``, ``parcel``, ``reservation`` or ``appropriation``."""
        result = self.parse(value)
        return None if result is None else result.kind

    def square(self, value: object) -> str | None:
        """The four-digit square; None for a prefixed SSL."""
        result = self.parse(value)
        return None if result is None else result.square

    def suffix(self, value: object) -> str | None:
        """The square suffix, such as ``E`` or ``NE``, or None."""
        result = self.parse(value)
        return None if result is None else result.suffix

    def number(self, value: object) -> str | None:
        """The parcel, reservation or appropriation number."""
        result = self.parse(value)
        return None if result is None else result.number

    def lot(self, value: object) -> str | None:
        """The four-character lot, without any of-lot marker."""
        result = self.parse(value)
        return None if result is None else result.lot

    def is_of_lot(self, value: object) -> bool | None:
        """True if the lot carries an of-lot marker."""
        result = self.parse(value)
        return None if result is None else result.is_of_lot

    def of_lot_number(self, value: object) -> int | None:
        """The number in an of-lot marker: 2 for ``-of2``."""
        result = self.parse(value)
        return None if result is None else result.of_lot_number

    def has_suffix(self, value: object) -> bool | None:
        """True for a square with a suffix, such as 0120E."""
        result = self.parse(value)
        return None if result is None else result.has_suffix

    def lot_type(self, value: object) -> LotType | None:
        """The lot type implied by the prefix or the lot number.

        See :attr:`SSL.lot_type` for the ranges. DC's LOT_TYPE column is
        authoritative where a dataset has it; :func:`lot_type_name`
        reads it.
        """
        result = self.parse(value)
        return None if result is None else result.lot_type

    def display(self, value: object) -> str | None:
        """A readable label, such as ``Square 0120E Lot 0001``."""
        result = self.parse(value)
        return None if result is None else result.display

    def normalize(self, value: object, of_lot: OfLot = "drop") -> str | None:
        """The canonical twelve-character SSL; see :meth:`SSL.normalize`."""
        _check_choice("of_lot", of_lot, get_args(OfLot))
        result = self.parse(value)
        return None if result is None else result.normalize(of_lot)


def lot_type_name(code: object) -> LotType | None:
    """Name a LOT_TYPE code from DC's lot layers: 1 is ``record``.

    The codes are the LOT_TYPE domain of DC's lot layers, 1 through 7.
    Accepts an integer, an integral float or a string of digits,
    including numpy number types. The names match the values
    :func:`lot_type` returns.
    """
    if isinstance(code, bool):
        return None
    if isinstance(code, str):
        text = code.strip()
        if not (text.isascii() and text.isdigit()):
            return None
        index = _digits_to_int(text)
    elif isinstance(code, numbers.Integral):
        index = int(code)
    elif isinstance(code, numbers.Real):
        value = float(code)
        if not value.is_integer():
            return None
        index = int(value)
    else:
        return None
    return None if index is None else _LOT_TYPE_CODES.get(index)


_DEFAULT = Parser()

parse = _DEFAULT.parse
is_valid = _DEFAULT.is_valid
kind = _DEFAULT.kind
square = _DEFAULT.square
suffix = _DEFAULT.suffix
number = _DEFAULT.number
lot = _DEFAULT.lot
is_of_lot = _DEFAULT.is_of_lot
of_lot_number = _DEFAULT.of_lot_number
has_suffix = _DEFAULT.has_suffix
lot_type = _DEFAULT.lot_type
display = _DEFAULT.display
normalize = _DEFAULT.normalize
