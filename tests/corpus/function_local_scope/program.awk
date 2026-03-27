function f(x) { x = x + 1; return x }
BEGIN { x = 10; print f(2); print x }
