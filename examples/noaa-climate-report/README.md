# NOAA Climate Report Showcase

This example specifies a Quawk report generator that ingests NOAA GHCN-Daily
fixed-width files directly.

The showcase lives entirely in this directory:

- [README.md](README.md)
- [climate_report.awk](climate_report.awk)

## Goal

The program consumes:

1. `ghcnd-stations.txt`
2. station `.dly` record content, usually streamed from NOAA's tar archive

and emits a yearly state-level climate summary.

Recommended first target:

- state: `CA`
- year: `2023`

Expected command shape:

```sh
tar -xOf ghcnd_all.tar.gz -T selected-stations.txt \
  | quawk -v state=CA -v year=2023 \
      -f examples/noaa-climate-report/climate_report.awk \
      ghcnd-stations.txt -
```

## Official NOAA Source Files

These are the relevant official GHCN-Daily downloads from NOAA NCEI:

- `ghcnd-stations.txt`
  - `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt`
- all station `.dly` files as a tarball
  - `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd_all.tar.gz`
- individual station `.dly` files after extraction
  - `https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/<STATION_ID>.dly`

NOAA also publishes yearly CSV subsets under `by_year/`, but this showcase
intentionally targets the canonical fixed-width station metadata and `.dly`
records instead.

## Can These Be Downloaded Directly With `curl`?

Yes.

Example commands:

```sh
curl -O https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt
curl -O https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd_all.tar.gz
```

For spot checks or small demos, individual station files can also be fetched
directly:

```sh
curl -O https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/USW00023183.dly
```

The files do not need to be committed to this repo. They can stay in a temp
workdir or any local data directory.

## Practical Local Workflow

The program expects the first input file to be `ghcnd-stations.txt`. Every
later input, including `-` for stdin, is treated as station `.dly` content.

Do not extract the full NOAA archive just to run this example:

- `ghcnd_all.tar.gz` is very large
- untarring it locally is slow and disk-heavy
- `selected/*.dly` can exceed shell command-line limits for larger states

Instead, stream only the station members you want from the tarball into stdin.

Recommended workflow:

1. download `ghcnd-stations.txt`
2. download `ghcnd_all.tar.gz`
3. derive a list of station member names for the state you want
4. ask `tar` to write just those members to stdout
5. pass that stdout stream to Quawk as `-`

For example, this builds a California member list from the fixed-width station
metadata and then streams those `.dly` members directly from the archive:

```sh
awk 'substr($0, 39, 2) == "CA" { print substr($0, 1, 11) ".dly" }' \
  ghcnd-stations.txt > selected-stations.txt

tar -xOf ghcnd_all.tar.gz -T selected-stations.txt \
  | quawk -v state=CA -v year=2023 \
      -f examples/noaa-climate-report/climate_report.awk \
      ghcnd-stations.txt -
```

That keeps the data out of the repo, avoids unpacking a multi-gigabyte archive,
and avoids an oversized shell glob.

For a very small demo or spot check, downloading one station file directly is
still fine:

```sh
curl -O https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/USW00023183.dly
quawk -v state=CA -v year=2023 \
  -f examples/noaa-climate-report/climate_report.awk \
  ghcnd-stations.txt USW00023183.dly
```

## Input Contract

### `ghcnd-stations.txt`

The program reads NOAA's fixed-width station metadata format directly.

Relevant columns from the NOAA readme:

- `ID`: columns `1-11`
- `LATITUDE`: columns `13-20`
- `LONGITUDE`: columns `22-30`
- `ELEVATION`: columns `32-37`
- `STATE`: columns `39-40`
- `NAME`: columns `42-71`

Only stations whose `STATE` matches `-v state=...` are retained.

### Station `.dly` files

The program reads NOAA's fixed-width monthly records directly. Those records may
come from ordinary `.dly` files or from a concatenated stdin stream produced by
`tar -xOf ...`.

Relevant columns from the NOAA readme:

- `ID`: columns `1-11`
- `YEAR`: columns `12-15`
- `MONTH`: columns `16-17`
- `ELEMENT`: columns `18-21`
- per-day repeated groups:
  - `VALUE`: 5 chars
  - `MFLAG`: 1 char
  - `QFLAG`: 1 char
  - `SFLAG`: 1 char

The program currently targets these elements:

- `TMAX`
- `TMIN`
- `PRCP`

NOAA units:

- `TMAX`: tenths of degrees C
- `TMIN`: tenths of degrees C
- `PRCP`: tenths of mm

The AWK program converts them to:

- Celsius
- millimeters

## Filtering Rules

The program accepts a daily value only when:

- the station is in the selected `state`
- the record `YEAR` matches `-v year=...`
- the `ELEMENT` is one of `TMAX`, `TMIN`, or `PRCP`
- the day `VALUE` is not `-9999`
- the day `QFLAG` is blank

## Output Contract

The program emits a plain-text report with these sections:

1. title and run parameters
2. coverage summary
3. overall summary
4. single-day extremes
5. monthly summary
6. warmest stations
7. wettest stations
8. data quality summary

Representative layout:

```text
NOAA Climate Summary
State: CA
Year: 2023

Coverage
Stations matched: 412
Stations with observations: 398
Element records processed: 219884
Accepted daily values: 142917
Skipped daily values: 1844

Overall Summary
Mean daily high: 22.4 C
Mean daily low: 10.8 C
Total precipitation: 482391.6 mm

Single-Day Extremes
Hottest day: 47.2 C  2023-07-16  DEATH VALLEY
Coldest day: -18.9 C  2023-01-25  SIERRA VALLEY
Wettest day: 186.4 mm  2023-03-14  MONTE RIO
```

## Aggregates

### Coverage

- stations matched by state
- stations with at least one accepted daily value
- element records processed
- accepted daily values
- skipped daily values

### Overall Summary

- mean daily high from accepted `TMAX`
- mean daily low from accepted `TMIN`
- total precipitation from accepted `PRCP`

### Monthly Summary

Per month:

- average high
- average low
- total precipitation
- accepted daily value count

### Station Rankings

Targets for the full version:

- warmest stations by annual mean temperature
- wettest stations by annual precipitation

The scaffold keeps the ranking section as an explicit follow-on step.

### Data Quality

- missing `TMAX`
- missing `TMIN`
- missing `PRCP`
- values skipped for nonblank `QFLAG`
- stations with sparse accepted coverage

## AWK Data Structures

Global counters:

- `element_record_count`
- `accepted_value_count`
- `skip_value_count`
- `stations_matched`
- `stations_with_observations`
- `missing_tmax_count`
- `missing_tmin_count`
- `missing_prcp_count`
- `qflag_skip_count`
- `sum_tmax`
- `count_tmax`
- `sum_tmin`
- `count_tmin`
- `sum_prcp`

Station metadata arrays keyed by `station_id`:

- `selected_station[id]`
- `station_name[id]`
- `station_state[id]`
- `station_lat[id]`
- `station_lon[id]`
- `station_elev[id]`
- `station_seen[id]`

Monthly arrays keyed by `month`:

- `month_tmax_sum[m]`
- `month_tmax_count[m]`
- `month_tmin_sum[m]`
- `month_tmin_count[m]`
- `month_prcp_sum[m]`
- `month_value_count[m]`

Per-station yearly arrays keyed by `station_id`:

- `station_prcp_sum[id]`
- `station_value_count[id]`

Extreme trackers:

- hottest: `max_tmax_value`, `max_tmax_date`, `max_tmax_station`
- coldest: `min_tmin_value`, `min_tmin_date`, `min_tmin_station`
- wettest: `max_prcp_value`, `max_prcp_date`, `max_prcp_station`

## Function Contract

The scaffold program uses these functions:

- `require_param(name)`
- `trim(text)`
- `rtrim(text)`
- `load_station_line()`
- `process_dly_record()`
- `process_day_value(id, year, month, day, element, raw_value, qflag)`
- `mark_station_seen(id)`
- `update_monthly(month, element, value)`
- `update_extremes(id, year, month, day, element, value)`
- `mean_or_na(sum_value, count_value)`
- `date_string(year, month, day)`
- `print_report()`
- `print_coverage_section()`
- `print_overall_summary()`
- `print_extremes_section()`
- `print_monthly_summary()`
- `print_station_rankings()`
- `print_data_quality()`

## Control Flow

1. `BEGIN`
   - validate `state` and `year`
2. first input file
   - parse `ghcnd-stations.txt`
   - retain only stations whose fixed-width `STATE` matches
3. later input files or stdin
   - parse station `.dly` monthly records
   - expand day slots for `TMAX`, `TMIN`, and `PRCP`
   - reject `-9999` and nonblank `QFLAG`
   - update counters, monthly aggregates, and extremes
4. `END`
   - print the report

## Showcase Value

This example is a good Quawk demo because it exercises:

- multi-file processing
- fixed-width parsing with `substr()`
- associative arrays
- user-defined functions
- numeric aggregation
- formatted report output
- a recognizable large public NOAA dataset
