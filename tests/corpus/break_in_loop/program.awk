BEGIN {
    for (i = 0; i < 5; i = i + 1) {
        if (i == 2) {
            break
        } else {
            print i
        }
    }
}
