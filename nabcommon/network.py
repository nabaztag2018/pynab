import fcntl
import re
import socket
import struct


def ip_address(ifname="wlan0"):
    """
    Return the IP address for given interface
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            ip_addr = socket.inet_ntoa(
                fcntl.ioctl(
                    s.fileno(),
                    0x8915,  # SIOCGIFADDR
                    struct.pack("256s", bytes(ifname[:15], "utf-8")),
                )[20:24]
            )
            matchObj = re.match(r"169\.254", ip_addr)
            if matchObj:
                # ignore self-assigned link-local address
                return None
            else:
                return ip_addr
    except OSError:
        return None


def internet_connection():
    """
    Return True if connected to Internet, False otherwise
    """
    DNS_SERVER_LIST = [
        "1.1.1.1",  # Cloudflare
        "208.67.222.222",  # Open DNS
        "8.8.8.8",  # Google DNS
        "1.0.0.1",  # Cloudflare
        "208.67.220.220",  # Open DNS
        "8.8.4.4",  # Google DNS
    ]
    dns_port = 53
    timeout = 3.0
    for dns_server in DNS_SERVER_LIST:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((dns_server, dns_port))
                return True
        except OSError:
            pass
    return False
