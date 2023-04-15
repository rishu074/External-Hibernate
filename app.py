import requests
from loguru import logger
import sys

API_KEY = "ptla_GMvlbcPve0veHKjTJl6jJajF8oPVWZPkxY3xrjJYmG0"
CLIENT_API_KEY = "ptlc_0NJ3Mn8ryKR22zJUjv8daeWL1sOT3y2xaqXPUnzYVif"
PANEL_URL = "https://gp.dnxrg.net"

def initial_start():
    logger.info("Booting up...")


def get_server_stats():
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CLIENT_API_KEY}"
    }




def read_servers():
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    req = requests.get(f"{PANEL_URL}/api/application/servers", headers=headers)
    return req.json()

if __name__ == '__main__':
    logger.remove(0)
    logger.add(sys.stderr, level="TRACE")
    initial_start()
    