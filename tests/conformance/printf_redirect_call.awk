BEGIN {
  printf("%s\n", substr(x, 1, 3)) >> "out"
  print "z" | "cat"
  close("out")
}
