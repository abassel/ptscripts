import sys
import argparse
import subprocess

from utils import utils


def create_command(ip):
    return 'ike-scan -M -A --id=test {}'.format(ip)


def run_ike(command):
    try:
        subprocess.call(command.split())
    except KeyboardInterrupt:
        return


def run_ike_on_ips(args):
    """ Select ips with open ports 500 and then run ike_scan """
    for ip in utils.get_ips_with_port_open(args.input, 500):
        command = create_command(ip)
        run_ike(command)


def parse_args(args):
    parser = argparse.ArgumentParser(prog='multi_ike.py')
    parser.add_argument('input', help='CSV File of open ports.')
    return parser.parse_args(args)


if __name__ == '__main__':
    run_ike_on_ips(parse_args(sys.argv[1:]))
