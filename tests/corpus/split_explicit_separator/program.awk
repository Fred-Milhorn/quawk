BEGIN {
    n = split("a:b:c", a, ":")
    print n
    print a[1]
    print a[2]
    print a[3]
}
