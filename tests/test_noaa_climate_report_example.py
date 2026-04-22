from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
NOAA_AWK = ROOT / "examples" / "noaa-climate-report" / "climate_report.awk"
NOAA_METADATA = FIXTURES / "noaa_station_metadata.txt"
NOAA_DLY = FIXTURES / "USW00023183_2023_core.dly"

EXPECTED_OUTPUT = """\
NOAA Climate Summary
State: AZ
Year: 2023

Coverage
Stations matched: 1
Stations with observations: 1
Element records processed: 36
Accepted daily values: 1095
Skipped daily values: 0

Overall Summary
Mean daily high: 31.6 C
Mean daily low: 18.6 C
Total precipitation: 106.9 mm

Single-Day Extremes
Hottest day: 48.3 C  2023-07-19  PHOENIX AP
Coldest day: 1.7 C  2023-01-24  PHOENIX AP
Wettest day: 18.8 mm  2023-03-15  PHOENIX AP

Monthly Summary
Month  Avg High  Avg Low   Total PRCP  Value Count
01     17.4      6.9       26.1        93
02     20.1      7.8       9.6         84
03     22.3      10.8      37.3        93
04     31.1      15.8      0.0         90
05     35.5      21.4      0.0         93
06     39.6      24.2      0.0         90
07     45.9      32.7      0.0         93
08     43.1      31.1      3.0         93
09     39.7      26.1      0.8         90
10     34.6      20.9      0.0         93
11     27.0      14.5      7.4         90
12     22.0      9.6       22.7        93

Warmest Stations
(ranking output is intentionally left as a follow-on step in this fixed-width scaffold)

Wettest Stations
(ranking output is intentionally left as a follow-on step in this fixed-width scaffold)

Data Quality
Missing TMAX: 7
Missing TMIN: 7
Missing PRCP: 7
Values skipped for nonblank QFLAG: 0
Stations with fewer than 300 accepted daily values: 0
"""


def run_quawk(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("use_stdin", [False, True], ids=["direct-file", "stdin-stream"])
def test_noaa_climate_report_example_matches_expected_output(use_stdin: bool) -> None:
    args = [
        "-v",
        "state=AZ",
        "-v",
        "year=2023",
        "-f",
        str(NOAA_AWK),
        str(NOAA_METADATA),
    ]
    stdin = None
    if use_stdin:
        args.append("-")
        stdin = NOAA_DLY.read_text()
    else:
        args.append(str(NOAA_DLY))

    result = run_quawk(*args, stdin=stdin)

    assert result.returncode == 0, result.stderr
    assert result.stdout == EXPECTED_OUTPUT
    assert result.stderr == ""
