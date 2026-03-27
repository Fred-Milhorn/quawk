BEGIN {
    for (i = 0; i < 4; i = i + 1) {
        if (i == 1) {
            continue
        } else {
            print i
        }
    }
}
