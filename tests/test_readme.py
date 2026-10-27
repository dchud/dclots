"""Run the examples in README.md.

``pycon`` blocks run as doctests, in order, in one shared namespace. Each
``python`` block runs on its own; when a ``text`` block follows it, what
the block prints must match that text.
"""

import contextlib
import doctest
import importlib
import io
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"
FENCE = re.compile(r"^```(\w*)\n(.*?)^```$", re.MULTILINE | re.DOTALL)
IMPORT = re.compile(r"^(?:from|import) (\w+)", re.MULTILINE)

# Spark 4 runs on these Java releases; newer ones fail at startup.
SPARK_JAVA = {17, 21}

# CI sets this so a missing library or Java fails the run instead of
# skipping a README example.
REQUIRE_ALL = bool(os.environ.get("DCLOTS_REQUIRE_ALL_EXAMPLES"))


def blocks() -> list[tuple[str, str, int]]:
    text = README.read_text(encoding="utf-8")
    return [
        (match[1], match[2], text.count("\n", 0, match.start()) + 1)
        for match in FENCE.finditer(text)
    ]


def python_examples() -> list[tuple[str, str | None, int]]:
    found = blocks()
    examples = []
    for index, (language, body, line) in enumerate(found):
        if language != "python":
            continue
        following = found[index + 1] if index + 1 < len(found) else None
        expected = (
            following[1] if following and following[0] == "text" else None
        )
        examples.append((body, expected, line))
    return examples


PYTHON_EXAMPLES = python_examples()


def tidy(output: str) -> str:
    return "\n".join(line.rstrip() for line in output.strip("\n").splitlines())


def java_major() -> int | None:
    java_home = os.environ.get("JAVA_HOME")
    java = (
        str(Path(java_home, "bin", "java"))
        if java_home
        else shutil.which("java")
    )
    if java is None:
        return None
    try:
        result = subprocess.run(
            [java, "-version"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    match = re.search(r'version "(\d+)', result.stderr)
    return int(match[1]) if match else None


def require_spark_java() -> None:
    major = java_major()
    if major in SPARK_JAVA:
        return
    reason = f"PySpark needs Java 17 or 21; found {major or 'no Java'}"
    if REQUIRE_ALL:
        pytest.fail(reason)
    pytest.skip(reason)


def require_module(name: str) -> None:
    if REQUIRE_ALL:
        importlib.import_module(name)
    else:
        pytest.importorskip(name)


def test_pycon_examples() -> None:
    parser = doctest.DocTestParser()
    runner = doctest.DocTestRunner()
    namespace: dict[str, object] = {}
    for language, body, line in blocks():
        if language != "pycon":
            continue
        example = parser.get_doctest(
            body, namespace, f"README.md:{line}", str(README), line
        )
        runner.run(example, clear_globs=False)
        # DocTest copies the namespace it is given.
        namespace.update(example.globs)
    results = runner.summarize(verbose=False)
    assert results.attempted > 0
    assert results.failed == 0


@pytest.mark.parametrize(
    ("body", "expected"),
    [(body, expected) for body, expected, _ in PYTHON_EXAMPLES],
    ids=[f"README.md:{line}" for _, _, line in PYTHON_EXAMPLES],
)
def test_python_example(body: str, expected: str | None) -> None:
    for module in sorted(set(IMPORT.findall(body)) - {"dclots"}):
        require_module(module)
    if "pyspark" in body:
        require_spark_java()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(body, {"__name__": "__main__"})
    if expected is not None:
        assert tidy(output.getvalue()) == tidy(expected)
