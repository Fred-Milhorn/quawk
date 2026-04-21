function f(x, y) {
  return x ? y : x
}
BEGIN { print f(1, 2) }
