BEGIN { print "start" }
{ print $2 }
END { print "done" }
