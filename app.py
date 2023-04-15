import requests
from loguru import logger
import sys

API_KEY = "ptla_GMvlbcPve0veHKjTJl6jJajF8oPVWZPkxY3xrjJYmG0"
CLIENT_API_KEY = "ptlc_0NJ3Mn8ryKR22zJUjv8daeWL1sOT3y2xaqXPUnzYVif"
PANEL_URL = "https://gp.dnxrg.net"

FIFTEEN_MINUTES_IN_MS = 15 * 60000

def initial_start():
    logger.info("Booting up...")
    _temp_id = 28

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    req = requests.get(f"{PANEL_URL}/api/application/servers/{_temp_id}", headers=headers)
    req_json = req.json()

    print(proceed_this_server(
        req_json['attributes']['name'],
        req_json['attributes']['identifier'],
        req_json['attributes']['uuid'],
        req_json['attributes']['container']['environment'].get("HIBERNATE", "true")))

def proceed_this_server(
        name: str, 
        identifier: 
        str, 
        uuid: str, 
        environment_hibernet: str):
    
    if environment_hibernet == 'false':
        return logger.info(f"{name} - {identifier}, is not allowing hibernate!")
    

    print(name, identifier, uuid, environment_hibernet)
    svr_stats = get_server_stats(identifier)

    node_maintenance = svr_stats['attributes']['is_node_under_maintenance']
    limits = svr_stats['attributes']['limits']
    is_suspended = svr_stats['attributes']['is_suspended']
    is_installing = svr_stats['attributes']['is_installing']
    is_transferring = svr_stats['attributes']['is_transferring']
    internal_id = svr_stats['attributes']['internal_id']

    print(node_maintenance, limits, is_suspended, is_installing, is_transferring)
    
    if node_maintenance:
        return logger.info(f"{name} - {identifier}, Node under maintenance!")
    elif is_suspended:
        return logger.info(f"{name} - {identifier}, Server suspended!")
    elif is_installing:
        return logger.info(f"{name} - {identifier}, Server Installing!")
    elif is_transferring:
        return logger.info(f"{name} - {identifier}, Server Transferring!")
    

    svr_usage = get_resource_usage(identifier)

    svr_state = svr_usage['attributes']['current_state']
    svr_resources_usage = svr_usage['attributes']['resources']

    print(svr_state, svr_resources_usage)
    # Case 1: Server is stuck in starting for more than 15 minutes, kill the server)



def kill_server(identifier: str):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CLIENT_API_KEY}"
    }

    req = requests.post(f"{PANEL_URL}/api/client/servers/{identifier}/power", headers=headers, json={"signal": "kill"})
    return

def suspend_server(internal_id: int):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    req = requests.post(f"{PANEL_URL}/api/application/servers/{internal_id}/suspend", headers=headers)
    return

def force_delete_svr(internal_id: int):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    req = requests.delete(f"{PANEL_URL}/api/application/servers/{internal_id}/force", headers=headers)
    return

def get_server_stats(identifier: str):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CLIENT_API_KEY}"
    }

    req = requests.get(f"{PANEL_URL}/api/client/servers/{identifier}", headers=headers)
    return req.json()

def get_resource_usage(identifier: str):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CLIENT_API_KEY}"
    }

    req = requests.get(f"{PANEL_URL}/api/client/servers/{identifier}/resources", headers=headers)
    return req.json()


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
    