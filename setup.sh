#!/bin/bash

SCRIPT_DIR=$(dirname $0)
cd $SCRIPT_DIR

TURI_VENV=
RMVENV=0
VERBOSE=0
DEP_DIR="dependencies"

function usage
{
	  echo "Usage: $0 [-e ENV]"
	  echo
	  echo "    -e ENV	create or reuse a cpython environment ENV"
	  echo "    -E ENV	re-create a cpython environment ENV"
	  echo
	  echo "This script clones all the turi repository and sets up a turi"
	  echo "development environment."
    
	  exit 1
}

function info
{
	echo "$(tput setaf 4 2>/dev/null)[+] $(date +%H:%M:%S) $@$(tput sgr0 2>/dev/null)"
	if [ $VERBOSE -eq 0 ]; then echo "[+] $@"; fi >> $OUTFILE
}

function warning
{
	echo "$(tput setaf 3 2>/dev/null)[!] $(date +%H:%M:%S) $@$(tput sgr0 2>/dev/null)"
	if [ $VERBOSE -eq 0 ]; then echo "[!] $@"; fi >> $OUTFILE
}

function debug
{
	echo "$(tput setaf 6 2>/dev/null)[-] $(date +%H:%M:%S) $@$(tput sgr0 2>/dev/null)"
	if [ $VERBOSE -eq 0 ]; then echo "[-] $@"; fi >> $OUTFILE
}

function error
{
	echo "$(tput setaf 1 2>/dev/null)[!!] $(date +%H:%M:%S) $@$(tput sgr0 2>/dev/null)" >&2
	if [ $VERBOSE -eq 0 ]
	then
		echo "[!!] $@" >> $ERRFILE
		cat $OUTFILE
		[ $OUTFILE == $ERRFILE ] || cat $ERRFILE
	fi
	exit 1
}

function install_angr
{
    mkdir -p $DEP_DIR
    cd $DEP_DIR

    # angr
    git clone git@github.com:angr/angr-dev.git
    cd angr-dev/
    git checkout 54a50162e9b68baf89e81c0fd62530cc64558957
    ./setup.sh -i -e $TURI_VENV -b py2k
    #./git_all.sh checkout feat/mixed_java
    cd ../
    cd ../

}

function install_pysoot
{
    mkdir -p $DEP_DIR
    cd $DEP_DIR

    git clone https://github.com/conand/pysoot
    pip install -e ./pysoot
    pip install pysmt
    cd ..
}

function enable_virtualenv
{
    info "Enabling virtualenvwrapper."
    if [ -e /etc/pacman.conf ]
    then
	      sudo pacman -S --needed python-virtualenvwrapper >>$OUTFILE 2>>$ERRFILE
	      set +e
	      source /usr/bin/virtualenvwrapper.sh >>$OUTFILE 2>>$ERRFILE
	      set -e
    else
	      pip install virtualenvwrapper >>$OUTFILE 2>>$ERRFILE
	      set +e
	      source /etc/bash_completion.d/virtualenvwrapper >>$OUTFILE 2>>$ERRFILE
	      set -e
    fi
}

while getopts "vE:e:" opt
do
	  case $opt in
        v)
			      VERBOSE=1
			      ;;
		  e)
			    TURI_VENV=$OPTARG
			    ;;
		  E)
			    TURI_VENV=$OPTARG
          RMVENV=1
			    ;;
		  \?)
			    usage
			    ;;
		  h)
			    usage
			;;
	esac
done

if [ $VERBOSE -eq 1 ]
then
	OUTFILE=/dev/stdout
	ERRFILE=/dev/stderr
else
	OUTFILE=/tmp/setup-$$
	ERRFILE=/tmp/setup-$$
	touch $OUTFILE
fi

if [ $RMVENV -eq 1 ]
then
    rm -rf ~/.virtualenvs/$TURI_VENV
fi

if [ -z "$TURI_VENV" ]
then
    usage
fi

set +e

ANGR_INSTALLED=$(ls ~/.virtualenvs/$TURI_VENV/lib/python2.7/site-packages 2> /dev/null | grep angr)
# install angr first
if [ -z "$ANGR_INSTALLED" ]
then
    install_angr
else
    # create virtual env
    enable_virtualenv    

    # deactivate
    if [ -n "$VIRTUAL_ENV" ]
	  then
		    # We can't just deactivate, since those functions are in the parent shell.
		    # So, we do some hackish stuff.
		    PATH=${PATH/$VIRTUAL_ENV\/bin:/}
		    unset VIRTUAL_ENV
	  fi

    # check if already exists
    if lsvirtualenv | grep -q "^$TURI_VENV$"
	  then
		    info "Virtualenv $TURI_VENV already exists, reusing it. Use -E instead of -e if you want to re-create the environment."
    else
  	    info "Creating cpython virtualenv $TURI_VENV..."
		    mkvirtualenv --python=$(which python2) $TURI_VENV >>$OUTFILE 2>>$ERRFILE
    fi
fi

workon $TURI_VENV

# install pysoot
PYSOOT_INSTALLED=$(ls ~/.virtualenvs/$TURI_VENV/lib/python2.7/site-packages 2> /dev/null | grep pysoot)
if [ -z "$PYSOOT_INSTALLED" ]
then
    install_pysoot
else


    
info "Exec workon $TURI_ENV to use your new angr virtual"

