# dclots

Parse and label District of Columbia SSL (square, suffix, lot) identifiers.

`dclots` is one module with no dependencies outside the standard library. It
supports Python 3.11 through 3.15. Every function takes a single value and
returns a single value, so each one works as a scalar UDF in pandas, polars,
DuckDB, ibis or PySpark.

## Install

```sh
uv add git+https://github.com/dchud/dclots
```

Or copy `src/dclots.py` into your project. Its header carries the MIT license
and a link back to this repository.

## SSL values

DC's real property data identifies a lot by its SSL: a four-digit square, a
four-character suffix padded with spaces, and a four-character lot. Parcels,
reservations and appropriations put a prefix and a number where the square and
suffix go. DC describes the format under "Common Questions" at
<https://opendata.dc.gov/pages/changes-in-lots>; the `APPR` prefix appears in
DC's Appropriations layer.

| SSL | Kind | Fields |
|---|---|---|
| `0120    0001` | square | square `0120`, lot `0001` |
| `0120E   0001` | square | square `0120`, suffix `E`, lot `0001` |
| `0667ESS 0802` | square | square `0667`, suffix `ESS`, lot `0802` |
| `PAR 00870075` | parcel | number `0087`, lot `0075` |
| `RES 015P0000` | reservation | number `015P`, lot `0000` |
| `APPR00070000` | appropriation | number `0007`, lot `0000` |

Some lots in DC's historical layers carry an of-lot marker after the lot, as
in `1220    0076-of2`. "Of-lot" is the DC Surveyor's term for the remaining
part of an original lot. The parser reads the marker separately from the lot.

## Usage

```pycon
>>> import dclots
>>> dclots.parse("0120E   0001")
SSL(kind='square', square='0120', suffix='E', number=None, lot='0001', is_of_lot=False, of_lot_number=None)
>>> dclots.lot_type("0120E   0001")
'record'
>>> dclots.display("PAR 00870075")
'Parcel 0087 Lot 0075'
>>> dclots.normalize("0120e 0001")
'0120E   0001'
>>> dclots.is_valid("PT OF SQUARE")
False
>>> print(dclots.lot_type("PT OF SQUARE"))
None
```

| Function | Returns | Example |
|---|---|---|
| `parse(value)` | an `SSL` record | |
| `is_valid(value)` | `True` if the value parses | `"PT OF SQUARE"` → `False` |
| `kind(value)` | `square`, `parcel`, `reservation` or `appropriation` | `"PAR 00870075"` → `"parcel"` |
| `square(value)` | the square; `None` for a prefixed SSL | `"0120E   0001"` → `"0120"` |
| `suffix(value)` | the square suffix | `"0120E   0001"` → `"E"` |
| `number(value)` | the parcel, reservation or appropriation number | `"PAR 00870075"` → `"0087"` |
| `lot(value)` | the lot, without an of-lot marker | `"1220    0076-of2"` → `"0076"` |
| `is_of_lot(value)` | `True` if the lot has an of-lot marker | `"1220    0076-of2"` → `True` |
| `of_lot_number(value)` | the number in the marker | `"1220    0076-of2"` → `2` |
| `has_suffix(value)` | `True` for a square with a suffix | `"0120E   0001"` → `True` |
| `lot_type(value)` | the lot type implied by the SSL | `"0120E   0001"` → `"record"` |
| `display(value)` | a readable label | `"0120E   0001"` → `"Square 0120E Lot 0001"` |
| `normalize(value, of_lot="drop")` | the canonical twelve-character SSL | `"0120e 0001"` → `"0120E   0001"` |
| `lot_type_name(code)` | the name for a DC `LOT_TYPE` code | `1` → `"record"` |

Every function accepts any value. All of them except `is_valid` and
`lot_type_name` return `None` for a value that doesn't parse, including `None`,
`NaN` and numbers.

## Lot types

`lot_type()` infers the type from the prefix, or from the lot number using
DC's numbering ranges:

| SSL | `lot_type()` |
|---|---|
| lot `0001`–`0799` | `record` |
| lot `0800`–`1999` | `tax` |
| lot `2000`–`6999` | `condo` |
| lot `7000`–`9999` | `air_rights` |
| letter lot, such as `000A` or `00B2` | `record` |
| lot `0000` | `None` |
| `PAR` | `parcel` |
| `RES` | `reservation` |
| `APPR` | `appropriation` |

The ranges have exceptions. In the Common Ownership Lots layer as downloaded
on 2026-10-27, the inferred type differs from DC's `LOT_TYPE` column for 596
of 137,388 SSLs. Most of the 596 are record lots numbered in the tax range.
Where a dataset has a `LOT_TYPE` column, use it: `lot_type_name()` maps its
codes to the same names `lot_type()` returns.

```pycon
>>> dclots.lot_type("1301    1082")
'tax'
>>> dclots.lot_type_name(1)
'record'
```

| `LOT_TYPE` | `lot_type_name()` |
|---|---|
| 1 | `record` |
| 2 | `tax` |
| 3 | `air_rights` |
| 4 | `reservation` |
| 5 | `appropriation` |
| 6 | `parcel` |

`LOT_TYPE` has no code for condo lots. `lot_type_name()` accepts an integer,
an integral float such as `6.0`, or a string of digits.

## Repairs and invalid values

The parser repairs:

- case: `0120e   0001`
- whitespace around the value
- spacing between the fields: `5557  0802`, `3569     0071`, `0120E0001`,
  `PAR 0087 0075`
- a square with fewer than four digits, followed by a suffix or a space:
  `120 0001` reads as `0120    0001`

The lot must have four characters, so `120 1` does not parse.

A repair can't restore a missing suffix. In DC's Common Ownership Lots,
`2586   0413` has `W` in its `SUFFIX` column; the parser reads it as square
`2586` with no suffix.

These do not parse with the default options:

- text in place of a lot: `0930    PT OF SQUARE`, `3561    ORIGINAL`,
  `0000    Unassessed`
- a decimal lot: `5730    0004.5`
- a five-digit square: `00278    0032`
- square `0000`
- any marker other than an of-lot marker: `1270    0000-B`

## Options

The module-level functions use the default for each option. To change an
option, create a `Parser`. It has every function above as a method, except
`lot_type_name`, which takes no options.

```pycon
>>> parser = dclots.Parser(unreadable_lot="square_only")
>>> parser.square("3561    ORIGINAL")
'3561'
```

A `Parser` raises `ValueError` for an option value it doesn't recognize.

### `dash_marker`

How a trailing `-N` on the lot is read. `-ofN`, `-OFN` and a bare `-of` are
always read as of-lot markers.

- `"of_lot"` (default): `-N` is an of-lot marker, the same as `-ofN`.
- `"invalid"`: a value ending in `-N` does not parse.

In DC's Record Lots (Historical) layer, the `OF_LOT_SEQ` flag is set for 128
of the 207 lots written with `-N`, and for 181 of the 200 written with `-ofN`.

```pycon
>>> dclots.of_lot_number("0368    0028-1")
1
>>> strict = dclots.Parser(dash_marker="invalid")
>>> strict.is_valid("0368    0028-1")
False
>>> strict.of_lot_number("1220    0076-of2")
2
```

### `unreadable_lot`

What to do when a value starts with a four-digit square, optionally with a
suffix, followed by a space and text that is not a lot.

- `"invalid"` (default): the value does not parse.
- `"square_only"`: the result has the square and suffix, and `lot` is `None`.
  `lot_type()` and `normalize()` return `None` for it, and `display()` shows
  the square.

```pycon
>>> partial = dclots.Parser(unreadable_lot="square_only")
>>> partial.parse("0604W   ORIGINAL")
SSL(kind='square', square='0604', suffix='W', number=None, lot=None, is_of_lot=False, of_lot_number=None)
>>> partial.display("0930    PT OF SQUARE")
'Square 0930'
>>> print(partial.lot_type("0930    PT OF SQUARE"))
None
>>> print(partial.parse("0000    Unassessed"))
None
```

### `extra_zeros`

How a square or lot written with more than four digits is read.

- `"invalid"` (default): the value does not parse.
- `"trim"`: extra leading zeros are dropped from a number that has a space or
  the start or end of the value on each side. An unspaced run of digits is
  left as it is.

```pycon
>>> trim = dclots.Parser(extra_zeros="trim")
>>> trim.normalize("00278    0032")
'0278    0032'
>>> trim.is_valid("012000001")
False
```

### `normalize(value, of_lot=...)`

Whether `normalize()` keeps an of-lot marker.

- `"drop"` (default): return the twelve-character SSL without the marker, for
  joining against data keyed by plain SSLs.
- `"keep"`: append the marker as `-of` and its number.

```pycon
>>> dclots.normalize("0368    0028-1")
'0368    0028'
>>> dclots.normalize("0368    0028-1", of_lot="keep")
'0368    0028-of1'
>>> dclots.normalize("2079    0003-of", of_lot="keep")
'2079    0003-of'
```

## Dataframes

Pass a function, or a `Parser` method for other options, wherever the library
takes a Python function.

### pandas

```python
import pandas as pd

import dclots

df = pd.DataFrame(
    {
        "ssl": [
            "0120E   0001",
            "1301    1082",
            "PAR 00870075",
            "0368    0028-1",
            "PT OF SQUARE",
        ],
        "LOT_TYPE": [1, 1, 6, 1, None],
    }
)
df["square"] = df["ssl"].map(dclots.square)
df["lot"] = df["ssl"].map(dclots.lot)
df["lot_type"] = df["ssl"].map(dclots.lot_type)
df["dc_lot_type"] = df["LOT_TYPE"].map(dclots.lot_type_name)
print(df)
```

```text
              ssl  LOT_TYPE square   lot lot_type dc_lot_type
0    0120E   0001       1.0   0120  0001   record      record
1    1301    1082       1.0   1301  1082      tax      record
2    PAR 00870075       6.0    NaN  0075   parcel      parcel
3  0368    0028-1       1.0   0368  0028   record      record
4    PT OF SQUARE       NaN    NaN   NaN      NaN         NaN
```

### polars

```python
import polars as pl

import dclots

df = pl.DataFrame(
    {"ssl": ["0120E   0001", "0368    0028-1", "3561    ORIGINAL"]}
)
partial = dclots.Parser(unreadable_lot="square_only")
print(
    df.with_columns(
        normalized=pl.col("ssl").map_elements(
            dclots.normalize, return_dtype=pl.String
        ),
        square=pl.col("ssl").map_elements(
            partial.square, return_dtype=pl.String
        ),
    )
)
```

```text
shape: (3, 3)
┌──────────────────┬──────────────┬────────┐
│ ssl              ┆ normalized   ┆ square │
│ ---              ┆ ---          ┆ ---    │
│ str              ┆ str          ┆ str    │
╞══════════════════╪══════════════╪════════╡
│ 0120E   0001     ┆ 0120E   0001 ┆ 0120   │
│ 0368    0028-1   ┆ 0368    0028 ┆ 0368   │
│ 3561    ORIGINAL ┆ null         ┆ 3561   │
└──────────────────┴──────────────┴────────┘
```

### DuckDB

Register each function with `null_handling="special"`. The functions return
NULL for values they can't parse, and with DuckDB's default null handling, a
NULL result for a non-NULL input is an error.

```python
import duckdb

import dclots

con = duckdb.connect()
con.create_function(
    "ssl_lot_type",
    dclots.lot_type,
    ["VARCHAR"],
    "VARCHAR",
    null_handling="special",
)
con.create_function(
    "ssl_display",
    dclots.display,
    ["VARCHAR"],
    "VARCHAR",
    null_handling="special",
)
print(
    con.sql("""
        SELECT ssl, ssl_lot_type(ssl) AS lot_type, ssl_display(ssl) AS label
        FROM (VALUES ('0120E   0001'), ('PAR 00870075'), ('PT OF SQUARE'))
            AS t(ssl)
    """)
)
```

```text
┌──────────────┬──────────┬───────────────────────┐
│     ssl      │ lot_type │         label         │
│   varchar    │ varchar  │        varchar        │
├──────────────┼──────────┼───────────────────────┤
│ 0120E   0001 │ record   │ Square 0120E Lot 0001 │
│ PAR 00870075 │ parcel   │ Parcel 0087 Lot 0075  │
│ PT OF SQUARE │ NULL     │ NULL                  │
└──────────────┴──────────┴───────────────────────┘
```

### ibis

On the DuckDB backend, which ibis uses by default, pass
`null_handling="special"` to the UDF decorator for the same reason.

```python
import ibis

import dclots


@ibis.udf.scalar.python(null_handling="special")
def ssl_lot_type(ssl: str) -> str:
    return dclots.lot_type(ssl)


t = ibis.memtable({"ssl": ["0120E   0001", "PAR 00870075", "PT OF SQUARE"]})
print(t.mutate(lot_type=ssl_lot_type(t.ssl)).to_pandas())
```

```text
            ssl lot_type
0  0120E   0001   record
1  PAR 00870075   parcel
2  PT OF SQUARE      NaN
```

### PySpark

Wrap the function in a lambda. Given the function itself, PySpark reads its
type hints, can't map them to a UDF type, and warns.

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf

import dclots

spark = SparkSession.builder.getOrCreate()
ssl_lot_type = udf(lambda ssl: dclots.lot_type(ssl), "string")
df = spark.createDataFrame(
    [("0120E   0001",), ("PAR 00870075",), ("PT OF SQUARE",)], ["ssl"]
)
df.withColumn("lot_type", ssl_lot_type("ssl")).show()
```

```text
+------------+--------+
|         ssl|lot_type|
+------------+--------+
|0120E   0001|  record|
|PAR 00870075|  parcel|
|PT OF SQUARE|    NULL|
+------------+--------+
```

On a cluster the executors import `dclots` too. Install the package on the
cluster, or ship the module with
`spark.sparkContext.addPyFile("path/to/dclots.py")`.

## Sample data

The patterns, the tests and the figures in this README are based on SSL values
from 14 of DC's Vector Property Map layers on Open Data DC
(<https://opendata.dc.gov/search?q=vpmdata>), downloaded on 2026-10-27. The
download took the SSL, square, suffix, lot and lot-type columns of every
record, without geometry, from the `Property_and_Land_WebMercator` service:
<https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land_WebMercator/FeatureServer>.
The downloaded records are not part of this repository. The tests use
individual values from them and name each value's layer in a comment.

| Layer | Service layer | Records | Parse with default options |
|---|---|---|---|
| Air Rights Lots | 3 | 1,020 | 1,009 |
| Air Rights Lots (Historical) | 2 | 418 | 416 |
| Appropriations | 5 | 17 | 17 |
| Common Ownership Lots | 40 | 137,400 | 137,388 |
| Condo Approval Lots | 44 | 4,865 | 4,863 |
| Condo Relate Table | 52 | 73,545 | 73,545 |
| Land Boundary Change | 78 | 23,886 | 23,836 |
| Parcel Lots | 33 | 1,124 | 1,124 |
| Parcel Lots (Historical) | 32 | 272 | 272 |
| Record Lots (Historical) | 34 | 14,915 | 14,875 |
| Reservations | 37 | 939 | 938 |
| Reservations (Historical) | 36 | 91 | 91 |
| Tax Lots | 39 | 30,867 | 30,867 |
| Tax Lots (Historical) | 38 | 8,066 | 8,065 |
| Total | | 297,425 | 297,306 |

Of the 119 records that don't parse, 14 have no SSL. The others have text in
place of a lot, such as `ORIGINAL` or `PT OF SQUARE`, a decimal lot, a
five-digit square, a marker such as `-B`, or the reservation number `06.5`.

## Development

```sh
uv sync
./scripts/check.sh
```

`scripts/check.sh` runs what CI runs: formatting, linting, type checking, the
process-label and workflow lints, and the tests. The README examples run as
tests. The PySpark example needs Java 17 or 21 and is skipped without it.

## License

MIT. See [LICENSE](LICENSE).
