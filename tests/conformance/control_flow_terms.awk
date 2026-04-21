BEGIN {
  while (1) {
    break
    continue
  }
  do {
    next
  } while (0)
}
{ nextfile }
END { exit 1 }
