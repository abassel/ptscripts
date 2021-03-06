import os
import logging
import argparse
import subprocess
from urllib.parse import urlparse  # pylint: disable=no-name-in-module,import-error

from utils import utils


LOG = logging.getLogger("ptscripts.multi_wpscan")


def run_update():
    LOG.info("Running wpscan --update")
    try:
        subprocess.run(["wpscan", "--update"], timeout=60 * 5)
    except subprocess.TimeoutExpired:
        LOG.warning("Timeout error ocurred trying to update wpscan.")
    return


def run_command_tee_aha(command, html_output):
    LOG.info("Running command {}".format(command))
    try:
        process = subprocess.run(command.split(), stderr=subprocess.PIPE,
                                 stdout=subprocess.PIPE, timeout=60 * 5)  # pylint: disable=no-member
        process_stdout = str(process.stdout, 'utf-8')
        p2 = subprocess.run(['tee', '/dev/tty'], input=process.stdout, stdout=subprocess.PIPE)  # pylint: disable=no-member
        process_stderr = str(process.stderr, 'utf-8')
    except subprocess.TimeoutExpired:  # pylint: disable=no-member
        LOG.warning("Timeout error occurred for url.")
        return "timeout"
    if "SystemStackError" in process_stderr:
        LOG.error("SystemStackError")
        return "stackerror"
    if "The remote website is up, but" in process_stdout:
        LOG.info("The remote website is up found in process_stdout")
        LOG.info("No Wordpress found at URL.")
        return "not wordpress"
    if "seems to be down. Maybe" in process_stdout:
        LOG.info("Seems to be down found in process_stdout")
        LOG.info("No Wordpress found at URL.")
        return "down"
    if "The target is responding with a 403" in process_stdout:
        LOG.info("Response code 403, moving on.")
        return "403"
    p3 = subprocess.run(['aha', '-b'], input=p2.stdout, stdout=subprocess.PIPE)  # pylint: disable=no-member
    output = p3.stdout
    LOG.info("Writing output to {}".format(html_output))
    with open(html_output, 'wb') as h:
        h.write(output)
    return "wordpress"


def create_command(url, output_dir):
    command = "wpscan -u {} -e u --random-agent --follow-redirection --disable-tls-checks".format(url)
    url_parsed = urlparse(url)
    if url_parsed.scheme == 'http':
        port = '80'
    else:
        port = '443'
    if url_parsed.port:
        port = str(url_parsed.port)
    html_output = os.path.join(
        output_dir, 'wpscan_{}_{}.html'.format(url_parsed.netloc, port))
    return (command, html_output)


def main(args):  # noqa
    utils.dir_exists(args.output_dir, True)
    run_update()
    tested = 0
    down = 0
    timeout = 0
    received_403 = 0
    not_wordpress = 0
    wordpress = 0
    stackerror = 0
    for url in utils.parse_webserver_urls(args.input):
        if utils.check_url(url)[0]:
            tested += 1
            command, html_output = create_command(url, args.output_dir)
            results = run_command_tee_aha(command, html_output)
            if results == "down":
                down += 1
            elif results == "403":
                received_403 += 1
            elif results == "timeout":
                timeout += 1
            elif results == "not wordpress":
                not_wordpress += 1
            elif results == "wordpress":
                wordpress += 1
            elif results == "stackerror":
                stackerror += 1
    LOG.info("Finished testing:")
    LOG.info("Total sites tested {} - (some sites skipped based on response)".format(tested))
    if down != 0:
        LOG.info("Websites that appeared to be down: {}".format(down))
    if timeout != 0:
        LOG.info("Websites that timedout: {}".format(timeout))
    if received_403 != 0:
        LOG.info("Websites that responded with a 403: {}".format(received_403))
    if stackerror != 0:
        LOG.info("Stack error received: {}".format(stackerror))
    if not_wordpress != 0:
        LOG.info("Websites that do not appear to be running WordPress: {}".format(not_wordpress))
    LOG.info("Total running WordPress: {}".format(wordpress))


def parse_args(args):
    parser = argparse.ArgumentParser(
        parents=[utils.parent_argparser()],
        description='Run wpscan on multiple urls.',
        prog='multi_wpscan.py',
    )
    parser.add_argument('input', help='File with a URL each line.')
    parser.add_argument('output_dir', help='Output directory where wpscan reports will be created.')
    args = parser.parse_args(args)
    logger = logging.getLogger("ptscripts")
    if args.quiet:
        logger.setLevel('ERROR')
    elif args.verbose:
        logger.setLevel('DEBUG')
    else:
        logger.setLevel('INFO')
    return args


if __name__ == '__main__':
    import sys
    main(parse_args(sys.argv[1:]))
