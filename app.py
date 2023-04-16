import requests
from loguru import logger
import sys
import multiprocessing
import time
import websocket
import json
import humanize


API_KEY = "ptla_GMvlbcPve0veHKjTJl6jJajF8oPVWZPkxY3xrjJYmG0"
CLIENT_API_KEY = "ptlc_0NJ3Mn8ryKR22zJUjv8daeWL1sOT3y2xaqXPUnzYVif"
PANEL_URL = "https://gp.dnxrg.net"

MINIMUM_UPTIME = 15 * 60000
ONE_MB_BYTE = 1e+6
CHECK_AGAIN_AFTER_INTERVAL = 5 * 60

DEV = False

@logger.catch()
def initial_start():
    logger.info("Booting up...")
    global CHECK_AGAIN_AFTER_INTERVAL
    global MINIMUM_UPTIME

    if DEV:
        logger.trace("Starting development env")
        _temp_id = int(input("Enter the temperory server id: "))

        # Changes according to tests
        CHECK_AGAIN_AFTER_INTERVAL = 10
        MINIMUM_UPTIME = 60000 * 2

        logger.trace(f"Got temp id {_temp_id}, gathering information from {PANEL_URL}")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        req = requests.get(f"{PANEL_URL}/api/application/servers/{_temp_id}", headers=headers)
        req_json = req.json()

        logger.trace(f"Calling proceed funtion...")

        proceed_this_server(
            req_json['attributes']['name'],
            req_json['attributes']['identifier'],
            req_json['attributes']['uuid'],
            req_json['attributes']['container']['environment'].get("HIBERNATE", "true"))

    else:
        logger.trace("Reading servers")
        total_servers = read_servers()
        logger.trace(f"Total servers: {len(total_servers)}")

        processes = []

        for svr in total_servers:
            p = multiprocessing.Process(target=proceed_this_server, args=[
                svr['attributes']['name'],
                svr['attributes']['identifier'],
                svr['attributes']['uuid'],
                svr['attributes']['container']['environment'].get("HIBERNATE", "true")])
            
            processes.append(p)

        logger.info(f"About to start {len(processes)} processes for {len(total_servers)} servers!")
        for pr in processes:
            pr.start()

        for pr in processes:
            pr.join()

    # _temp_id = 28
    # psses = []

    # for i in range(5):
    #     p1 = multiprocessing.Process(target=proceed_this_server, args=[
    #         req_json['attributes']['name'],
    #         req_json['attributes']['identifier'],
    #         req_json['attributes']['uuid'],
    #         req_json['attributes']['container']['environment'].get("HIBERNATE", "true")])
        
    #     p1.start()
    #     psses.append(p1)
    
    # for p in psses:
    #     p.join()
    
    # return

def proceed_this_server(
        name: str, 
        identifier: str, 
        uuid: str, 
        environment_hibernet: str):
    
    if environment_hibernet == 'false':
        return logger.info(f"{name} - {identifier}, is not allowing hibernate!")
    

    logger.info(f"Proceeding with server {name} - {identifier}")
    try:
        svr_stats = get_server_stats(identifier)
    except Exception as e:
        logger.error(f"{name} - {identifier}, Error while retrieving server stats, {e}, Recheck will be performed after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")

        return proceed_this_server(
            name,
            identifier,
            uuid,
            environment_hibernet)

    node_maintenance = svr_stats['attributes']['is_node_under_maintenance']
    limits = svr_stats['attributes']['limits']
    is_suspended = svr_stats['attributes']['is_suspended']
    is_installing = svr_stats['attributes']['is_installing']
    is_transferring = svr_stats['attributes']['is_transferring']
    internal_id = svr_stats['attributes']['internal_id']

    logger.trace(f"{name} - {identifier}, Got few servers stats, node_maintenance: {node_maintenance}, limits: {limits}, is_suspended: {is_suspended}, is_installing: {is_installing}, is_transferring: {is_transferring}, internal_id: {internal_id}")
    
    if node_maintenance:
        return logger.info(f"{name} - {identifier}, Node under maintenance!")
    elif is_suspended:
        return logger.info(f"{name} - {identifier}, Server suspended!")
    elif is_installing:
        return logger.info(f"{name} - {identifier}, Server Installing!")
    elif is_transferring:
        return logger.info(f"{name} - {identifier}, Server Transferring!")
    

    try:
        svr_usage = get_resource_usage(identifier)
    except Exception as e:
        logger.error(f"{name} - {identifier}, Error while retrieving server usage, {e}, Recheck will be performed after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        req = requests.get(f"{PANEL_URL}/api/application/servers/{internal_id}", headers=headers)
        req_json = req.json()


        return proceed_this_server(
            req_json['attributes']['name'],
            req_json['attributes']['identifier'],
            req_json['attributes']['uuid'],
            req_json['attributes']['container']['environment'].get("HIBERNATE", "true"))

    svr_state = svr_usage['attributes']['current_state']
    svr_resources_usage = svr_usage['attributes']['resources']
    logger.trace(f"{name} - {identifier}, Got svr usages, svr_state: {svr_state}, svr_resources_usage: {svr_resources_usage}")

    # Case 1: Server is stuck in starting for more than 15 minutes, kill the server)
    if svr_state == "starting" and svr_resources_usage['uptime'] >= MINIMUM_UPTIME:
        # Kill the server
        kill_server(identifier)
        return logger.info(f"{name} - {identifier}, Killing server because it took more than {humanize.naturaldelta(MINIMUM_UPTIME / 1000)} to start, Killed server.")

    
    # Case 2: Disk overusage, forcedelete server
    if svr_resources_usage['disk_bytes'] > (limits['disk'] * ONE_MB_BYTE):
        force_delete_svr(internal_id)
        return logger.info(f"{name} - {identifier}, Server was overusing disk, deleted server.")

    # Case 3: Server is overusing resources after 15 minutes of runtime, kill the server
    if svr_state == "running" and svr_resources_usage['uptime'] >= MINIMUM_UPTIME and (
        svr_resources_usage['memory_bytes'] > (limits['memory'] * ONE_MB_BYTE) or
        svr_resources_usage['disk_bytes'] > (limits['disk'] * ONE_MB_BYTE) or
        svr_resources_usage['cpu_absolute'] > limits['cpu']):

        # Kill the server
        kill_server(identifier)
        return logger.info(f"{name} - {identifier}, Server is overusing resources, for more than {humanize.naturaldelta(MINIMUM_UPTIME / 1000)}, Killed server.")
    
    # Case 4: Server is offline, try again after five minutes
    if svr_state == "offline" or svr_resources_usage['uptime'] <= MINIMUM_UPTIME:
        if svr_state == "offline":
            logger.info(f"{name} - {identifier}, Server found offline, will check again after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")
        else:
            logger.info(f"{name} - {identifier}, Server was just started, will check again after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")

        time.sleep(CHECK_AGAIN_AFTER_INTERVAL)

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        req = requests.get(f"{PANEL_URL}/api/application/servers/{internal_id}", headers=headers)
        req_json = req.json()


        return proceed_this_server(
            req_json['attributes']['name'],
            req_json['attributes']['identifier'],
            req_json['attributes']['uuid'],
            req_json['attributes']['container']['environment'].get("HIBERNATE", "true"))
    
    
    # Last case: Server is online, proceed with websocket things

    # Get webscoket url and token
    def check_for_players():
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CLIENT_API_KEY}"
        }

        req = requests.get(f"{PANEL_URL}/api/client/servers/{identifier}/websocket", headers=headers)
        ws_creds = req.json()
        logger.trace(f"{name} - {identifier}, Got websocket credentials, {ws_creds['data']['socket']}")

        ws = websocket.WebSocket() # type: ignore
        ws.connect(ws_creds['data']['socket'], origin = PANEL_URL)
        logger.trace(f"{name} - {identifier}, Connected to websocket, {ws_creds['data']['socket']}")
        ws.send(json.dumps({
            "event": "auth", 
            "args": [ws_creds["data"]["token"]]
        }))

        msg = ws.recv()
        logger.info(f"{name} - {identifier}, Console connected and auth state: {msg}")  

        # We have successfully connected websockets, now onwards we have to check the players online
        ws.send(json.dumps({
            "event": "send command", 
            "args": ["minecraft:list"]
        }))

        # Get all the console logs
        ws.send(json.dumps({
            "event": "send logs", 
            "args": [None]
        }))
        await_check_logs = True
        no_players_online_arr = []

        while await_check_logs:
            msg = json.loads(ws.recv())


            if msg['event'] == "console output" and msg['args'][0].lower().find('players online') != -1: # type: ignore
                # print(msg)
                no_players_online_arr.append(msg['args'][0]) # type: ignore

            if msg['event'] == "stats": # type: ignore
                await_check_logs = False

        if len(no_players_online_arr) == 0:
            logger.info(f"{name} - {identifier}, Ignoring server because there was no output for list command., will check after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")
        else:
            # Check players
            cmd_output = no_players_online_arr[len(no_players_online_arr)-1].lower()
            
            try:
                players_online = int(cmd_output[cmd_output.find("there are")+10])
            except Exception as err:
                logger.error(f"{name} - {identifier}, Errored with {err}, (cmd_output: {cmd_output}) , Recheck will be performed after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")
                ws.close()
                return

            if players_online == 0:
                # Server should be closed here
                kill_server(identifier)
                logger.info(f"{name} - {identifier}, Closed this server having 0 players, Recheck will be performed after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")
            else:
                logger.info(f"{name} - {identifier}, {players_online} players were online in this server, Recheck will be performed after {humanize.naturaldelta(CHECK_AGAIN_AFTER_INTERVAL)}.")


        ws.close()

    check_for_players()
    time.sleep(CHECK_AGAIN_AFTER_INTERVAL)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    req = requests.get(f"{PANEL_URL}/api/application/servers/{internal_id}", headers=headers)
    req_json = req.json()


    return proceed_this_server(
        req_json['attributes']['name'],
        req_json['attributes']['identifier'],
        req_json['attributes']['uuid'],
        req_json['attributes']['container']['environment'].get("HIBERNATE", "true"))




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
    next_link = [True, f"{PANEL_URL}/api/application/servers"]
    servers = []

    while next_link[0]:
        req = requests.get(next_link[1], headers=headers)
        req_json = req.json()
        servers = servers + req_json['data']

        if req_json['meta']['pagination']['links'].get('next', 'null') != 'null':
            next_link[1] = req_json['meta']['pagination']['links']['next']
        else:
            next_link[0] = False
    return servers

if __name__ == '__main__':
    logger.remove(0)
    logger.add(sys.stderr, level="TRACE")
    logger.trace("Starting initial function")
    initial_start()
    