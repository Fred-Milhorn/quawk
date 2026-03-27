NR == 1 { first = FILENAME }
{ last = FILENAME }
END {
    print (first != "")
    print (last != "")
    print (first != last)
}
