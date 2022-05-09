"""
Run gobuster save data and create images of the results

USAGE: python gobuster_image.py <url> <output_dir> [-s <screenshot directory>]
"""
import re
import os
import logging
import argparse
import requests
from urllib.parse import urlparse, urljoin

from utils import utils  # noqa
from utils import logging_config  # noqa pylint: disable=unused-import
from utils import run_commands


LOG = logging.getLogger("ptscripts.dirb_image")
COMMAND = "gobuster -q dir -w /usr/share/wordlists/dirbuster/directory-list-lowercase-2.3-medium.txt -u {url} -o gobuster_{domain}.txt"
PROXY_COMMAND = "gobuster dir -p {proxy} -w /usr/share/wordlists/dirbuster/directory-list-lowercase-2.3-medium.txt -u {url}"
PROXIES = {
    "http": "127.0.0.1:8080",
    "https": "127.0.0.1:8080"
}


def read_gobuster_output(url, output_path):
    """Returns a set of URLs that were found"""
    regex = re.compile(r"^(\/.*?) .*\(Status: ([0-9]{3})\).*\[Size: [0-9]+\](?: \[--> (.*)\])?$")
    results = set(())
    with open(output_path, "r") as file_pointer:
        raw_output = file_pointer.readlines()
    for line in raw_output:
        line = line.strip()
        matches = regex.match(line)
        if matches:
            path, status, redirect_url = matches.groups()
            if redirect_url and redirect_url.startswith("/"):
                redirect_url = urljoin(url, redirect_url)
                results.add(redirect_url)
            elif redirect_url:
                results.add(redirect_url)
            else:
                results.add(urljoin(url, path))
    return results


def proxy_results(url, output_path):
    # read the output file and build list of paths
    results = read_gobuster_output(url, output_path)
    for item in results:
        requests.get(item, proxy=PROXIES)


def main(args):
    LOG.info("Running gobuster for {}".format(args.url))
    netloc = urlparse(args.url).netloc
    domain = netloc.split(":")[0]
    if args.proxy:
        command = PROXY_COMMAND.format(url=args.url, proxy=args.proxy)
    else:
        command = COMMAND.format(url=args.url, domain=domain)
    LOG.info(f"Running command: {command}")
    html_path = os.path.join(args.output, "gobuster_{}.html".format(domain))
    txt_path = os.path.join(args.output, f"gobuster_{domain}.txt")
    text_output = run_commands.bash_command(command)
    html_output = run_commands.create_html_file(text_output, command, html_path)
    if html_output and args.screenshot:
        LOG.info("Creating a screenshot of the output and saving it to {}".format(args.screenshot))
        utils.dir_exists(args.screenshot, True)
        utils.selenium_image(html_output, args.screenshot)
    if not html_output:
        LOG.error("Didn't receive a response from running the command.")

    if args.burp:
        proxy_results(args.url, txt_path)


def parse_args(args):
    parser = argparse.ArgumentParser(
        parents=[utils.parent_argparser()],
        description='Capture gobuster data and image.',
    )
    parser.add_argument('url', help="url to be tested")
    parser.add_argument('output', help="where to store results")
    parser.add_argument("-s", "--screenshot",
                        help="full path to where the screenshot will be saved.")
    parser.add_argument("-p", "--proxy",
                        help="Proxy")
    parser.add_argument("-b", "--burp", action="store_true", help="Once done, proxy all found URLs through burp.")
    args = parser.parse_args(args)
    logger = logging.getLogger("ptscripts")
    if args.quiet:
        logger.setLevel('ERROR')
    elif args.verbose:
        logger.setLevel('DEBUG')
        logger.debug("Logger set to debug.")
    else:
        logger.setLevel('INFO')
    return args


if __name__ == "__main__":
    import sys
    main(parse_args(sys.argv[1:]))
