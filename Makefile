AP_NS = apns/*.py
TEST = apns/test/*.py
EXAMPLES = apns/examples/*.py
MN = bin/apns
PYTHON ?= python
PYMN = $(PYTHON) -B bin/apns
BIN = $(MN)
PYSRC = $(AP_NS) $(TEST) $(EXAMPLES) $(BIN)

CFLAGS += -Wall -Wextra

all: codecheck test

clean:
	rm -rf build dist *.egg-info *.pyc

codecheck: $(PYSRC)
	-echo "Running code check"
	pyflakes3 $(PYSRC)
	pylint --rcfile=.pylint $(PYSRC)
#	Exclude miniedit from pep8 checking for now
	pep8 --repeat --ignore=$(P8IGN) `ls $(PYSRC) | grep -v miniedit.py`

errcheck: $(PYSRC)
	-echo "Running check for errors only"
	pyflakes3 $(PYSRC)
	pylint -E --rcfile=.pylint $(PYSRC)

test: $(AP_NS) $(TEST)
	-echo "Running tests"
	apns/test/test_nets.py
	apns/test/test_hifi.py

slowtest: $(AP_NS)
	-echo "Running slower tests (walkthrough, examples)"
	apns/test/test_walkthrough.py -v
	apns/examples/test/runner.py -v

install:
	$(PYTHON) -m pip install --upgrade .
