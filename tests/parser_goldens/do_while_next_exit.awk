{ next }
{ nextfile }
BEGIN { x = 0; do { x = x + 1 } while (x < 3); exit 1 }
