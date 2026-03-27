BEGIN { x = "0"; if (x) print "string-true" }
BEGIN { if (x + 0) print "numeric-true"; else print "numeric-false" }
