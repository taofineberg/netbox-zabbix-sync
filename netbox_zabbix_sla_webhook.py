#!/opt/netbox-zabbix-sync/.venv/bin/python3.11
import requests
import json
import jsonpath_ng
import time
from datetime import datetime
from pynetbox import api
from pyzabbix import ZabbixAPI, ZabbixAPIException
from dotenv import load_dotenv
import os
import sys
import logging

# Initialize logging and file name 
logging.basicConfig(filename="service.log", level=logging.INFO, format='%(lineno)d - %(asctime)s [%(levelname)s] - %(message)s')
logging.info("Running service.py")

load_dotenv("/opt/creds/netbox_sync2.env")

# Get all virtual environment variables
zabbix_host = os.environ.get("ZABBIX_HOST")
zabbix_user = os.environ.get("ZABBIX_USER")
zabbix_pass = os.environ.get("ZABBIX_PASS")
zabbix_token = os.environ.get("ZABBIX_TOKENSLA")
netbox_host = os.environ.get("NETBOX_HOST")
netbox_token = os.environ.get("NETBOX_TOKEN")

# Zabbix API endpoint
zabbix_api_endpoint = f"{zabbix_host}/api_jsonrpc.php"

# Netbox API endpoint
netbox_api_endpoint = f"{netbox_host}/api"

# Set headers
zabbix_headers = {
    'Content-Type': 'application/json-rpc',
    'Authorization': f'Bearer {zabbix_token}'
}

netbox_headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Token {netbox_token}"
}

def log_and_exit(message):
    logging.error(message)
    sys.exit(1)

def post_request(url, headers, data):
    logging.debug(f"POST request to {url} with headers {headers} and data {data}")
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        log_and_exit(f"Failed request. Status code: {response.status_code}, Response: {response.text}")
    response_json = response.json()
    if "result" not in response_json:
        log_and_exit(f"Unexpected response format: {response_json}")
    return response_json["result"]

def get_request(url, headers):
    logging.debug(f"GET request to {url} with headers {headers}")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        log_and_exit(f"Failed request. Status code: {response.status_code}, Response: {response.text}")
    return response.json()["results"]

def get_zabbix_services():
    service_data = {
        "jsonrpc": "2.0",
        "method": "service.get",
        "params": {
            "output": "extend"
        },
        "id": 5
    }
    return post_request(zabbix_api_endpoint, zabbix_headers, service_data)

def get_netbox_sites():
    return get_request(f"{netbox_api_endpoint}/dcim/sites/?limit=0", netbox_headers)

def map_sites_to_services(services, netbox_sites):
    zabbix_site_service_map = {}
    for service in services:
        for netbox_site in netbox_sites:
            if netbox_site["name"] == service["name"]:
                zabbix_site_service_map[netbox_site["name"]] = service["serviceid"]
    return zabbix_site_service_map

def get_sla_tags():
    return [tag['slug'] for tag in get_request(f"{netbox_api_endpoint}/extras/tags/?limit=0", netbox_headers) if tag['slug'].startswith('sla-')]

def get_device_list(tag):
    return get_request(f"{netbox_api_endpoint}/dcim/devices/?tag={tag}", netbox_headers)

def get_zabbix_host(device_name):
    host_data = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "filter": {
                "host": [device_name]
            }
        },
        "id": 2
    }
    return post_request(zabbix_api_endpoint, zabbix_headers, host_data)

def create_zabbix_service(device, sla_tag_type_var, zabbix_site_service_map):
    logging.info(f"Creating Zabbix {sla_tag_type_var} service site as it does not exist for Device {device['name']} Site {device['site']['name']}")
    create_service_data = {
        "jsonrpc": "2.0",
        "method": "service.create",
        "params": {
            "name": device['site']['name'],
            "algorithm": 1,
            "sortorder": 0
        },
        "id": 4
    }
    response_json = post_request(zabbix_api_endpoint, zabbix_headers, create_service_data)
    zabbix_site_service_map[device['site']['name']] = response_json['serviceids'][0]

def create_sla_report(device, sla_tag_type_var, zabbix_site_service_map):
    sla_report_name = '-'.join((device['site']['name'], sla_tag_type_var))
    sla_report_period_text_array = {0: "daily", 1: "weekly", 2: "monthly", 3: "quarterly", 4: "annually"}
    logging.info(f"Creating SLA Report {sla_report_name}")
    for sla_report_period in range(0, 5):
        sla_report_period_text = sla_report_period_text_array[sla_report_period]
        sla_report_name_display = '-'.join((device['site']['name'], sla_tag_type_var, sla_report_period_text))
        sla_data = {
            "jsonrpc": "2.0",
            "method": "sla.create",
            "params": [
                {
                    "name": sla_report_name_display,
                    "slo": "99.9995",
                    "period": sla_report_period,
                    "timezone": "America/New_York",
                    "effective_date": int(time.time()),
                    "status": 1,
                    "schedule": [
                        {
                            "period_from": 0,
                            "period_to": 601200
                        }
                    ],
                    "service_tags": [
                        {"tag": "SLA-Report", "value": sla_report_name}
                    ],
                }
            ],
            "id": 1
        }
        response = requests.post(zabbix_api_endpoint, data=json.dumps(sla_data), headers=zabbix_headers)
        if response.status_code == 200:
            response_data = response.json()
            logging.info(response_data)
        else:
            logging.error('Error: ' + response.text)

def main():
    services = get_zabbix_services()
    netbox_sites = get_netbox_sites()
    zabbix_site_service_map = map_sites_to_services(services, netbox_sites)
    sla_tags = get_sla_tags()

    for sla_tag in sla_tags:
        devices = get_device_list(sla_tag)
        for device in devices:
            zabbix_host = get_zabbix_host(device["name"])
            if device['site']['name'] in zabbix_site_service_map.keys():
                zabbix_service_id = zabbix_site_service_map[device['site']['name']]
                logging.info(f"The Zabbix {sla_tag} service ID {zabbix_service_id} is for Device {device['name']} Site {device['site']['name']}")
            else:
                create_zabbix_service(device, sla_tag, zabbix_site_service_map)
            create_sla_report(device, sla_tag, zabbix_site_service_map)

if __name__ == "__main__":
    main()
