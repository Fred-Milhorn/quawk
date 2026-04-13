BEGIN {
    top_n = 10
    require_param("state")
    require_param("year")
}

NR == 1 {
    metadata_filename = FILENAME
}

FILENAME == metadata_filename {
    load_station_line()
    next
}

{
    process_dly_record()
    next
}

END {
    print_report()
}

function require_param(name) {
    if (name == "state" && state == "") {
        print "missing required -v state=..." > "/dev/stderr"
        exit 2
    }
    if (name == "year" && year == "") {
        print "missing required -v year=..." > "/dev/stderr"
        exit 2
    }
}

function trim(text) {
    sub(/^[[:space:]]+/, "", text)
    sub(/[[:space:]]+$/, "", text)
    return text
}

function rtrim(text) {
    sub(/[[:space:]]+$/, "", text)
    return text
}

function load_station_line(    id, row_state, row_name, row_lat, row_lon, row_elev) {
    id = substr($0, 1, 11)
    row_state = trim(substr($0, 39, 2))
    if (row_state != state) {
        return
    }

    if (!(id in selected_station)) {
        stations_matched += 1
    }

    row_name = rtrim(substr($0, 42, 30))
    row_lat = trim(substr($0, 13, 8)) + 0
    row_lon = trim(substr($0, 22, 9)) + 0
    row_elev = trim(substr($0, 32, 6)) + 0

    selected_station[id] = 1
    station_name[id] = row_name
    station_state[id] = row_state
    station_lat[id] = row_lat
    station_lon[id] = row_lon
    station_elev[id] = row_elev
}

function process_dly_record(    id, rec_year, rec_month, element, day, base, raw_value, qflag) {
    id = substr($0, 1, 11)
    if (!(id in selected_station)) {
        return
    }

    rec_year = substr($0, 12, 4) + 0
    if (rec_year != year + 0) {
        return
    }

    element = substr($0, 18, 4)
    if (element != "TMAX" && element != "TMIN" && element != "PRCP") {
        return
    }

    element_record_count += 1

    rec_month = substr($0, 16, 2) + 0
    for (day = 1; day <= 31; day++) {
        base = 22 + ((day - 1) * 8)
        raw_value = substr($0, base, 5)
        qflag = substr($0, base + 6, 1)
        process_day_value(id, rec_year, rec_month, day, element, raw_value, qflag)
    }
}

function process_day_value(id, rec_year, rec_month, rec_day, element, raw_value, qflag, numeric_value) {
    if (raw_value == "-9999") {
        if (element == "TMAX") {
            missing_tmax_count += 1
        } else if (element == "TMIN") {
            missing_tmin_count += 1
        } else if (element == "PRCP") {
            missing_prcp_count += 1
        }
        return
    }

    if (qflag != " ") {
        qflag_skip_count += 1
        skip_value_count += 1
        return
    }

    numeric_value = raw_value + 0
    if (element == "TMAX" || element == "TMIN") {
        numeric_value = numeric_value / 10.0
    } else if (element == "PRCP") {
        numeric_value = numeric_value / 10.0
    }

    accepted_value_count += 1
    mark_station_seen(id)
    update_monthly(rec_month, element, numeric_value)
    update_extremes(id, rec_year, rec_month, rec_day, element, numeric_value)

    station_value_count[id] += 1
    if (element == "TMAX") {
        sum_tmax += numeric_value
        count_tmax += 1
    } else if (element == "TMIN") {
        sum_tmin += numeric_value
        count_tmin += 1
    } else if (element == "PRCP") {
        sum_prcp += numeric_value
        station_prcp_sum[id] += numeric_value
    }
}

function mark_station_seen(id) {
    if (!(id in station_seen)) {
        station_seen[id] = 1
        stations_with_observations += 1
    }
}

function update_monthly(rec_month, element, value) {
    month_value_count[rec_month] += 1
    if (element == "TMAX") {
        month_tmax_sum[rec_month] += value
        month_tmax_count[rec_month] += 1
    } else if (element == "TMIN") {
        month_tmin_sum[rec_month] += value
        month_tmin_count[rec_month] += 1
    } else if (element == "PRCP") {
        month_prcp_sum[rec_month] += value
    }
}

function update_extremes(id, rec_year, rec_month, rec_day, element, value, when) {
    when = date_string(rec_year, rec_month, rec_day)
    if (element == "TMAX" && ((max_tmax_station == "") || (value > max_tmax_value))) {
        max_tmax_value = value
        max_tmax_station = id
        max_tmax_date = when
    }
    if (element == "TMIN" && ((min_tmin_station == "") || (value < min_tmin_value))) {
        min_tmin_value = value
        min_tmin_station = id
        min_tmin_date = when
    }
    if (element == "PRCP" && ((max_prcp_station == "") || (value > max_prcp_value))) {
        max_prcp_value = value
        max_prcp_station = id
        max_prcp_date = when
    }
}

function mean_or_na(sum_value, count_value) {
    if (count_value == 0) {
        return "n/a"
    }
    return sprintf("%.1f", sum_value / count_value)
}

function date_string(rec_year, rec_month, rec_day) {
    return sprintf("%04d-%02d-%02d", rec_year, rec_month, rec_day)
}

function print_report() {
    print "NOAA Climate Summary"
    print "State: " state
    print "Year: " year
    print ""

    print_coverage_section()
    print_overall_summary()
    print_extremes_section()
    print_monthly_summary()
    print_station_rankings()
    print_data_quality()
}

function print_coverage_section() {
    print "Coverage"
    printf("Stations matched: %d\n", stations_matched)
    printf("Stations with observations: %d\n", stations_with_observations)
    printf("Element records processed: %d\n", element_record_count)
    printf("Accepted daily values: %d\n", accepted_value_count)
    printf("Skipped daily values: %d\n", skip_value_count)
    print ""
}

function print_overall_summary() {
    print "Overall Summary"
    printf("Mean daily high: %s C\n", mean_or_na(sum_tmax, count_tmax))
    printf("Mean daily low: %s C\n", mean_or_na(sum_tmin, count_tmin))
    printf("Total precipitation: %.1f mm\n", sum_prcp)
    print ""
}

function print_extremes_section() {
    print "Single-Day Extremes"
    if (max_tmax_station != "") {
        printf("Hottest day: %.1f C  %s  %s\n", max_tmax_value, max_tmax_date, station_name[max_tmax_station])
    }
    if (min_tmin_station != "") {
        printf("Coldest day: %.1f C  %s  %s\n", min_tmin_value, min_tmin_date, station_name[min_tmin_station])
    }
    if (max_prcp_station != "") {
        printf("Wettest day: %.1f mm  %s  %s\n", max_prcp_value, max_prcp_date, station_name[max_prcp_station])
    }
    print ""
}

function print_monthly_summary(    rec_month) {
    print "Monthly Summary"
    print "Month  Avg High  Avg Low   Total PRCP  Value Count"
    for (rec_month = 1; rec_month <= 12; rec_month++) {
        printf("%02d     %-8s  %-8s  %-10.1f  %d\n", rec_month, mean_or_na(month_tmax_sum[rec_month], month_tmax_count[rec_month]), mean_or_na(month_tmin_sum[rec_month], month_tmin_count[rec_month]), month_prcp_sum[rec_month] + 0, month_value_count[rec_month] + 0)
    }
    print ""
}

function print_station_rankings() {
    print "Warmest Stations"
    print "(ranking output is intentionally left as a follow-on step in this fixed-width scaffold)"
    print ""
    print "Wettest Stations"
    print "(ranking output is intentionally left as a follow-on step in this fixed-width scaffold)"
    print ""
}

function print_data_quality(    id, sparse_count) {
    for (id in station_value_count) {
        if (station_value_count[id] < 300) {
            sparse_count += 1
        }
    }

    print "Data Quality"
    printf("Missing TMAX: %d\n", missing_tmax_count)
    printf("Missing TMIN: %d\n", missing_tmin_count)
    printf("Missing PRCP: %d\n", missing_prcp_count)
    printf("Values skipped for nonblank QFLAG: %d\n", qflag_skip_count)
    printf("Stations with fewer than 300 accepted daily values: %d\n", sparse_count)
}
