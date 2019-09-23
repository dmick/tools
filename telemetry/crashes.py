#!/usr/bin/env python3

import hashlib
import json
import os
import os.path
import psycopg2
import sys

HOST = 'localhost'
DBNAME = 'telemetry'
USER = 'postgres'
PASSPATH = os.path.join(os.environ['HOME'], '.pgpass')
PASSWORD = open(PASSPATH, "r").read().strip().split(':')[-1]


def sanitize_backtrace(bt):
    ret = list()
    for func_record in bt:
        # split into two fields on last space, take the first one,
        # strip off leading ( and trailing )
        func_plus_offset = func_record.rsplit(' ', 1)[0][1:-1]
        ret.append(func_plus_offset.split('+')[0])

    return ret


def collect_crashes_and_bin(conn, n):
    """
    Queries Postgres on conn for n reports; collects
    crashdump backtraces, sanitizes them (removing offsets and addresses),
    puts them into bins, and returns a large list of n entries, each entry

    Returns: list of n entries
    Each entry is a list: [report_id, num_crashes, crashbindict]
    crashbindict is a dict keyed by the md5 of the backtrace, with
     entries each being yet another list of [count, backtrace function list]
    """

    cur = conn.cursor()
    cur.execute('select json(report)->>\'report_id\', json(report)->>\'crashes\' from report limit %d;' % n)
    ret = list()
    for report_id, crashes in cur.fetchall():
        crashlist = json.loads(crashes)
        crashbins = dict()
        if len(crashlist) == 0:
            continue
        for crash in crashlist:
            sig = hashlib.md5()
            funclist = sanitize_backtrace(crash['backtrace'])
            for func in funclist:
                sig.update(func.encode())
            key = sig.digest()
            if key in crashbins:
                count, bt = crashbins[key]
                count += 1
                crashbins[key][0] = count
            else:
                crashbins[key] = [1, funclist]
        ret.append([report_id, len(crashlist), crashbins])
    cur.close()
    return ret


def print_bins(crashbinlist):
    """
    Print the return value of collect_crashes_and_bin
    """
    for crashrec in crashbinlist:
        report_id, num_crashes, crashbins = crashrec
        print('%s has %s total crashes' % (report_id, num_crashes))
        for count, bt in crashbins.values():
            print('%s of:\n\t%s\n' % (count, '\n\t'.join(bt)))

def main():
    conn = psycopg2.connect(host=HOST, dbname=DBNAME, user=USER, password=PASSWORD)
    crashbins = collect_crashes_and_bin(conn, int(sys.argv[1]))
    print_bins(crashbins)
    conn.close()


if __name__ == '__main__':
    sys.exit(main())
