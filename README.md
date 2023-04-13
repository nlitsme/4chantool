4chan tool
==========

A commandline tool for querying 4chan

Usage
=====

First you will have to create a configuration file in your `HOME` directory called `.4chan4c`, with the following:


    [cloudfare]
    clearance=.....cf_clearance.cookie........
    useragent=.....user-agent-string....


You can find both by looking at requests sent by your browser, in the browser debug-console.

Examples:

    python3 4chan.py -b pol --threads
    python3 4chan.py --search SomeQuery


Full usage:

    usage: 4chan.py [-h] [--debug] [--verbose] [--boards] [--board BOARD] [--cachedir CACHEDIR]
                    [--threads] [--catalog] [--archive] [--stats] [--search SEARCH]
                    [--config CONFIG] [--cfuseragent CFUSERAGENT] [--cfclearance CFCLEARANCE]

    List 4chan comments

    options:
      -h, --help            show this help message and exit
      --debug, -d           print all intermediate steps
      --verbose, -v
      --boards, -l          list boards
      --board BOARD, -b BOARD
                            specify board
      --cachedir CACHEDIR, -c CACHEDIR
                            Specify a different cache directory
      --threads             list threads for board
      --catalog             list threads from catalog for board
      --archive             list threads from archive for board
      --stats               show post keyword stats
      --search SEARCH       forum search
      --config CONFIG       specify configuration file.
      --cfuseragent CFUSERAGENT
      --cfclearance CFCLEARANCE


Author
======

Willem Hengeveld

itsme@xs4all.nl

