import os
import socket
import logging
import ipaddress
import subprocess

import click
from requests import get
import netifaces as ni


def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:
        log.debug(f"AttributeError socket.inet_pton({socket.AF_INET}, {address})")
        try:
            socket.inet_aton(address)
        except socket.error:
            log.debug(f"socket.error socket.inet_aton({address})")
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        log.debug(f"socket.error socket.inet_pton({socket.AF_INET}, {address})")
        return False
    return True


def get_dns_ips():
    # TODO: Get this to run cat /etc/resolv.conf saving the output as a screenshot
    log.debug(f"Reading /etc/resolv.conf to get DNS server")
    dns_ips = []
    with open('/etc/resolv.conf') as fp:
        for _, line in enumerate(fp):
            columns = line.split()
            if columns[0] == 'nameserver':
                ip = columns[1:][0]
                if is_valid_ipv4_address(ip):
                    dns_ips.append(ip)
    log.debug(f"Found the following DNS IPs {', '.join(dns_ips)}")
    return dns_ips


def get_domain_names():
    log.debug(f"Reading /etc/resolv.conf to get domain names")
    domain_names = []
    with open('/etc/resolv.conf') as fp:
        for _, line in enumerate(fp):
            columns = line.split()
            if columns[0] == 'search':
                domain_names.append(columns[1:][0])
    log.debug(f"Found the following domains {', '.join(domain_names)}")
    return domain_names


def get_domain_controllers(domain_names, commands, output):
    # TODO: Get this to run the command saving the output and creating a screenshot
    log.debug("Querying the network for domain controllers.")
    domain_controllers = []
    for domain in domain_names:
        for ending in ["", ".com", ".local"]:
            args = ["nslookup", "-type=srv", f"_ldap._tcp.dc._msdcs.{domain}{ending}"]
            commands.append(" ".join(args))
            nslookup_results = subprocess.run(args, capture_output=True, text=True)
            for line in nslookup_results.stdout.splitlines():
                if line.startswith("_ldap"):
                    domain_controllers.append(line.split()[6][:-1])  # Just get the hostname
    if not domain_controllers:
        domain_controllers.append("No Domain Controllers found.")
    else:
        with open(os.path.join(output, "dcs.txt"), "w") as fp:
            fp.write("\n".join(domain_controllers))
            fp.write("\n")
    log.debug(f"Domain Controllers: {', '.join(domain_controllers)}")
    return domain_controllers, commands


def ping_scan(subnet, hosts, commands):
    # TODO: Get this to run the command saving the output and creating a screenshot
    # expects that hosts is a set
    log.info(f"Running an nmap ping scan on the subnet: {subnet}")
    args = ["nmap", "-sn", "-PS", "-n", subnet]  # Ping scan, TCP SYN/ACK, No DNS resolution
    commands.append(" ".join(args))
    nmap_results = subprocess.run(args, capture_output=True, text=True)
    for line in nmap_results.stdout.splitlines():
        if line.startswith("Nmap scan"):
            hosts.add(line.split()[4])  # Just get the IP address
    log.debug(f"Nmap ping scan done. Found {len(hosts)} ips.")
    return hosts, commands


def nbt_scan(subnet, hosts, commands):
    # TODO: Get this to run the command saving the output and creating a screenshot
    # expects that hosts is a set
    log.info(f"Running an nbtscan on the subnet: {subnet}")
    args = ["nbtscan", "-q", subnet]
    commands.append(" ".join(args))
    nbtscan_results = subprocess.run(args, capture_output=True, text=True)
    for line in nbtscan_results.stdout.splitlines():
        hosts.add(line.split()[0])
    log.debug(f"nbtscan done. Hosts now contains {len(hosts)} ips")
    return hosts, commands


def arp_scan(interface, hosts, commands):
    # TODO: Get this to run the command saving the output and creating a screenshot
    # expects that hosts is a set
    log.info(f"Running an arp-scan on the interface: {interface}")
    args = ["arp-scan", "-q", "-I", interface, "--localnet"]
    commands.append(" ".join(args))
    arp_results = subprocess.run(args, capture_output=True, text=True)
    for line in arp_results.stdout.splitlines():
        try:
            ip = line.split()[0]
        except IndexError:
            continue
        if is_valid_ipv4_address(ip):
            hosts.add(ip)
    log.debug(f"arp-scan done. Hosts now contains {len(hosts)} ips")
    return hosts, commands


@click.command()
@click.option("-v", "--verbose", "verbocity", flag_value="verbose",
              help="-v Will show DEBUG messages.")
@click.option("-q", "--quiet", "verbocity", flag_value="quiet",
              help="-q Will show only ERROR messages.")
@click.argument("output", type=click.Path(
    exists=True, file_okay=False, dir_okay=True, resolve_path=True))
@click.argument("interface", default="eth0")
def cli(verbocity, output, interface):
    commands = []
    if verbocity == "verbose":
        log.setLevel("DEBUG")
        log.debug("Setting logging level to DEBUG")
    elif verbocity == "quiet":
        log.setLevel("ERROR")
        log.error("Setting logging level to ERROR")
    else:
        log.setLevel("INFO")
        log.info("Setting logging level to INFO")

    log.debug(f"Running sa on interface {interface}")
    log.debug(f"Getting IP address for {interface}")
    commands.append("ip addr")
    ip_address = ni.ifaddresses(interface)[ni.AF_INET][0]["addr"]
    log.debug(f"IP address for {interface} is {ip_address}")
    log.debug(f"Getting netmask for {interface}")
    netmask = ni.ifaddresses(interface)[ni.AF_INET][0]["netmask"]
    log.debug(f"Netmask for {interface} is {netmask}")
    network = ipaddress.IPv4Network(f"{ip_address}/{netmask}", strict=False)
    log.debug(f"Network address {network.network_address}")
    cidr = network.compressed.split("/")[1]
    log.debug(f"Network subnet {network.compressed}, cidr = {cidr}")
    gateway = ni.gateways()['default'][ni.AF_INET][0]
    log.debug(f"Gateway address {gateway}")
    log.debug("Getting external IP from api.ipify.org")
    external_ip = get('https://api.ipify.org').text
    log.debug(f"External IP = {external_ip}")
    commands.append("cat /etc/resolv.conf")
    dns_ips = get_dns_ips()
    domain_names = get_domain_names()
    domain_controllers, commands = get_domain_controllers(domain_names, commands, output)
    hosts, commands = ping_scan(network.compressed, set(), commands)
    hosts, commands = nbt_scan(network.compressed, hosts, commands)
    hosts, commands = arp_scan(interface, hosts, commands)
    print("-----------------------------")
    print(f"IP Address: {ip_address}")
    print(f"Net Mask: {netmask}")
    print(f"CIDR: {cidr}")
    print(f"Network Address: {network.network_address}")
    print(f"DNS Servers: {', '.join(dns_ips)}")
    print(f"External IP: {external_ip}")
    print(f"Domain Controllers: {', '.join(domain_controllers)}")
    print(f"Domain Names: {', '.join(domain_names)}")
    print(f"Gateway IP: {gateway}")
    print(f"Writing IPs found to {os.path.join(output, 'hosts.txt')}")
    print("-----------------------------")
    with open(os.path.join(output, "hosts.txt"), "w") as fp:
        fp.write("\n".join(hosts))
        fp.write("\n")
    with open(os.path.join(output, "commands.txt"), "w") as fp:
        fp.write("\n".join(commands))
        fp.write("\n")


logging.basicConfig(
    format="{asctime} [{levelname}] {message}",
    style="{", datefmt="%H:%M:%S",
)
log = logging.getLogger()

if __name__ == "__main__":
    cli()  # pylint:disable=no-value-for-parameter