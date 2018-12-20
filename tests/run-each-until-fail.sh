##
## Usage:
##
## # Run all tests in the current directory, one at a time. Stop if one fails.
## run-each-until-fail.sh
##
## # Same as above, but skip tests until we get to the one defined in SKIP_UNTIL
## SKIP_UNTIL=test_utilities.py 

for f in $(ls *test*.py)
do
    if [ ! -z "$SKIP_UNTIL" ] && [[ "$SKIP_UNTIL" != "$f" ]]; then
        continue
    else
        SKIP_UNTIL=""
        echo "Running $f"
	pytest $f
	RET=$?
        if [ $RET -ne 0 ]; then
	    exit $RET
        fi
    fi
done
