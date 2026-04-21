BEGIN {
  print (1 ? 2 : 3) || (4 != 5) || (6 <= 7) || (8 > 9) || (10 >= 11)
  print (a ~ /x/)
  print (a !~ /y/)
  print (1 in a)
  print (b == 1)
  print 1 "x"
  print 8 - 3 * 2 / 1 % 4 ^ 2
  print !-x
  ++x
  x++
}
