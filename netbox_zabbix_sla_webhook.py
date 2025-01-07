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

import logging

# Initialize logging and file name 
logging.basicConfig(filename="service.log", level=logging.INFO,format='%(lineno)d - %(asctime)s [%(levelname)s] - %(message)s')
logging.info("Running service.py")  # Added logging

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

# Authentication
auth_data = {
    "jsonrpc": "2.0",
    "method": "user.login",
    "params": {
        "user": "{zabbix_user}",
    },
    "id": 1
}

headers = {
    "Content-Type": "application/json-rpc"
}


auth_token = zabbix_token 

# Set Netbox headers and authentication
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Token {netbox_token}"
}


########## MAP SITES TO SERVICES ##########Start
# Get Zabbix services
service_data = {
    "jsonrpc": "2.0",
    "method": "service.get",
    "params": {
        "output": "extend"
    },
    "auth": auth_token,
    "id": 5
}

response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(service_data))

# Check the response status code and content
if response.status_code != 200:
    logging.error(f"Failed to get Zabbix services. Status code: {response.status_code}, Response: {response.text}")
    sys.exit(1)

response_json = response.json()
if "result" not in response_json:
    logging.error(f"Unexpected response format: {response_json}")
    sys.exit(1)

services = response_json["result"]
logging.debug(f"Zabbix services are {services}")

# Get Netbox sites
netbox_response = requests.get(f"{netbox_api_endpoint}/dcim/sites/?limit=0", headers=headers)
netbox_sites = netbox_response.json()["results"]

# Map Netbox sites to Zabbix services
zabbix_site_service_map = {}
for service in services:
    for netbox_site in netbox_sites:
        #print(f"Checking if Zabbix service {service['name']} matches Netbox site {netbox_site['name']}")
        if netbox_site["name"] == service["name"]:
            #print(f"Mapping Zabbix service {service['name']} to Netbox site {netbox_site['name']}")
            zabbix_site_service_map[netbox_site["name"]] = service["serviceid"]

######### MAP SITES TO SERVICES ##########End

########## Get list of tags that start sla from netbox ##########Start
response = requests.get(f"{netbox_api_endpoint}/extras/tags/?limit=0", headers=headers)
response_data_tag = response.json()
sla_tag_names = [tag['slug'] for tag in response_data_tag['results'] if tag['slug'].startswith('sla-')]

for sla_tag_name in sla_tag_names:
    sla_tag_type_var = sla_tag_name
########## Get list of tags that start sla from netbox ##########End




    # Get device information from Netbox with tag sla_tag_type_var
    device_list_url = f"{netbox_api_endpoint}/dcim/devices/?tag={sla_tag_type_var}"
    device_list_response = requests.get(device_list_url, headers=headers)
    device_list = device_list_response.json()["results"]

    for device in device_list:
        # Get host information from Zabbix
        host_data = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "filter": {
                    "host": [device["name"]]
                }
            },
            "auth": auth_token,
            "id": 2
        }
        response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(host_data))
        host = response.json()["result"]
        

        # Check if a Zabbix service already exists for a specific site name
        if device['site']['name'] in zabbix_site_service_map.keys():
            zabbix_service_id = zabbix_site_service_map[device['site']['name']]
            logging.info(f"The Zabbix {sla_tag_type_var} service ID {zabbix_service_id} is for Device {device['name']} Site {device['site']['name']}")


        else:
            # Create Zabbix service if it doesn't exist
            logging.info(f"Creating Zabbix {sla_tag_type_var} service site as it does not exist for Device {device['name']} Site {device['site']['name']}")
            create_service_data = {
                "jsonrpc": "2.0",
                "method": "service.create",
                "params": {
                    "name": device['site']['name'],
                    "algorithm": 1,
                    "sortorder": 0
                },
                "auth": auth_token,
                "id": 4
            }
            response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(create_service_data))
            response_json = response.json()
            if 'result' in response_json.keys():
                zabbix_site_service_map[device['site']['name']] = response_json['result']['serviceids'][0]
        


    #############################################################################################
    #############################################################################################
    #############################################################################################


    ########## MAP TENANTS TO SERVICES ##########Start
    # Get Zabbix services
    service_data = {
        "jsonrpc": "2.0",
        "method": "service.get",
        "params": {
            "output": "extend"
        },
        "auth": auth_token,
        "id": 5
    }

    response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(service_data))
    services = response.json()["result"]

    # Get Netbox sites
    netbox_response = requests.get(f"{netbox_api_endpoint}/dcim/sites/?limit=0", headers=headers)
    netbox_sites = netbox_response.json()["results"]

    # Map Netbox sites to Zabbix services
    zabbix_site_service_map = {}
    for service in services:
        for netbox_site in netbox_sites:
            if netbox_site["name"] == service["name"]:
                zabbix_site_service_map[netbox_site["name"]] = service["serviceid"]

    ######### MAP TENANTS TO SERVICES ##########End

    for device in device_list:
        # Get host information from Zabbix
        host_data = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "filter": {
                    "host": [device["name"]]
                }
            },
            "auth": auth_token,
            "id": 2
        }
        response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(host_data))
        zbxhost = response.json()["result"]

        # Check if trigger exists in Zabbix
        if zbxhost:
            trigger_data = {
                "jsonrpc": "2.0",
                "method": "trigger.get",
                "params": {
                    "filter": {
                        "host": [device["name"]],
                        "description": sla_tag_type_var
                    }
                },
                "auth": auth_token,
                "id": 3
            }
            
            response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(trigger_data))     
            triggers = response.json()["result"]
            
        # If trigger does not exist, create it    
            
        if not triggers:
                print(("Trigger does not exist, creating ICMP and trigger"),{sla_tag_type_var},(device['name']))

########Get the hostid from zabbix##########Start

                host_data = {
                    "jsonrpc": "2.0",
                    "method": "host.get",
                    "params": {
                        
                        "filter": {
                            "host": [device["name"]]
                        }
                    },
                    "auth": auth_token,
                    "id": 2
                }
                response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(host_data))
                zbxhost = response.json()["result"]
                #print(zbxhost)
                host_id = zbxhost[0]["hostid"]

                print(host_id)


########Get the hostid from zabbix##########End

########Get the interfaceid from zabbix##########Start

                interfaceid_data = {
                    "jsonrpc": "2.0",
                    "method": "hostinterface.get",
                    "params": {
                        "type": "1",
                        "filter": {
                            "hostid": host_id
                        }
                    },
                    "auth": auth_token,
                    "id": 2
                }
                interface_response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(interfaceid_data))
                zbxhostinterid = interface_response.json()["result"]
                #print(zbxhostinterid)
                interface_id = zbxhostinterid[0]["interfaceid"]
                print(f"Interface ID is {interface_id}")

########Get the interfaceid from zabbix##########End



##########Add SLA ICMP ping #############
                                # Create the item
                item_payload = {
                    "jsonrpc": "2.0",
                    "method": "item.create",
                    "params": {
                        "name": "SLA ICMP ping",
                        "key_": "icmpping[,4]",
                        "hostid": host_id,
                        "interfaceid": interface_id,
                        "type": "3",
                        "value_type": "3",
                        "delay": "60",
                        "history": "7d",
                        "trends": "365d",
                        "status": "0"
                    },
                    "auth": auth_token,
                    "id": 3
                }
                item_response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(item_payload))
                #print(item_response.json())
                #item_id = item_response["result"]["itemids"][0]
                # Print the item ID
                #print(f"Item created with ID {item_id}")


##########Add trigger ##########                
                sla_report_name = (device['site']['name'], sla_tag_type_var)
                sla_report_name = '-'.join(sla_report_name)
                sla_report_name_tenant = (device['tenant']['name'], sla_tag_type_var)
                sla_report_name_tenant = '-'.join(sla_report_name_tenant)
                trigger_data = {
                    "jsonrpc": "2.0",
                    "method": "trigger.create",
                    "params": {
                    "description": sla_tag_type_var,
                    "expression": "max(/" + (device["name"]) + "/icmpping[,4],#3)=0",
                    "priority": 1,
                    "tags": [
                        {"tag": sla_tag_type_var,"value": device['name']},
                        {"tag": "SLA-Device", "value": device['name']},
                        {"tag": "SLA-Type", "value": sla_tag_type_var},
                        {"tag": "SLA-Site", "value": device['site']['name']},
                        {"tag": "SLA-Tenant", "value": device['tenant']['name']},
                        {"tag": "SLA-Report-Tenant", "value": (sla_report_name_tenant)},
                        {"tag": "SLA-Report", "value": (sla_report_name)}
                    ],
                },
                "auth": auth_token,
                "id": 3
                }
                response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(trigger_data))
                #print(trigger_data)
                #print(response.json())
        # Get trigger ID
                trigger_id = response.json()["result"]["triggerids"][0]
                print(("Trigger created"),{sla_tag_type_var},(device["name"]))         
        # Get Zabbix service ID for a specific site name if it does not exist, create it
                if device['site']['name'] in zabbix_site_service_map.keys():
                    zabbix_service_id = zabbix_site_service_map[device['site']['name']]      
        #Create child service
                service_name = (device["name"], sla_tag_type_var)
                service_name = '-'.join(service_name)
                service_data = {
                    "jsonrpc": "2.0",
                    "method": "service.create",
                    "params": {
                        "parents": [{ "serviceid":(zabbix_service_id)}],
                        "name": service_name,
                        "algorithm": 0,
                        "sortorder": 0,
                        "problem_tags": [{"tag": sla_tag_type_var, "value": device['name']}],
                        "tags": [
                            {"tag": "SLA-Device", "value": device['name']},
                            {"tag": "SLA-Type", "value": sla_tag_type_var},
                            {"tag": "SLA-Site", "value": device['site']['name']},
                            {"tag": "SLA-Tenant", "value": device['tenant']['name']},
                            {"tag": "SLA-Report-Tenant", "value": (sla_report_name_tenant)},
                            {"tag": "SLA-Report", "value": (sla_report_name)}
                        ],                    
                    },
                    
                    "auth": auth_token,
                    "id": 4
                }
                #print(service_data)
                response = requests.post(zabbix_api_endpoint, headers=headers, data=json.dumps(service_data))
                #print(response.json())

##############################################################################################################################################
############################################    Report Creation   ############################################################################
##############################################################################################################################################



############# Create SLA Report #############Start
                sla_report_name = (device['site']['name'], sla_tag_type_var)  # i think this can be removed as it is already defined above 
                sla_report_name = '-'.join(sla_report_name) # i think this can be removed as it is already defined above
                sla_report_tag = {"tag": "SLA-Report", "value": (sla_report_name)}
                sla_report_period = json.dumps({"period": [0, 1, 2, 3, 4]})
                sla_report_period_text_array = {0: "daily", 1: "weekly", 2: "monthly", 3: "quarterly", 4: "annually"}
                print(("Creating SLA Report"),{sla_report_name})
                for sla_report_period in range(0, 5):
                    sla_report_period_text = sla_report_period_text_array[sla_report_period]
                    sla_report_name_display = (device['site']['name'], sla_tag_type_var, sla_report_period_text)
                    sla_report_name_display = '-'.join(sla_report_name_display)
                    sla_data = {
                        "jsonrpc": "2.0",
                        "method": "sla.create",
                        "params": [
                            {
                                "name": sla_report_name_display,
                                "slo": "99.9995",
                                "period": sla_report_period, #  {0: "daily", 1: "weekly", 2: "monthly", 3: "quarterly", 4: "annually"}
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
                        "auth": auth_token,
                        "id": 1
                    }

                    # Send the JSON-RPC request to the Zabbix API
                    response = requests.post(zabbix_api_endpoint, data=json.dumps(sla_data), headers={'Content-Type': 'application/json'})

                    # Check the response status code and print the response content
                    if response.status_code == 200:
                        response_data = response.json()
                        print(response_data)
                    else:
                        print('Error: ' + response.text)

############# Create SLA Report Tenant #############Start
                sla_report_name = (device['tenant']['name'], sla_tag_type_var)
                sla_report_name = '-'.join(sla_report_name)
                sla_report_tag = {"tag": "SLA-Report", "value": (sla_report_name)}
                sla_report_period = json.dumps({"period": [0, 1, 2, 3, 4]})
                sla_report_period_text_array = {0: "daily", 1: "weekly", 2: "monthly", 3: "quarterly", 4: "annually"}
                logging.info("Creating SLA Report %s", sla_report_name)
                for sla_report_period in range(0, 5):
                    sla_report_period_text = sla_report_period_text_array[sla_report_period]
                    sla_report_name_display = (device['tenant']['name'], sla_tag_type_var, sla_report_period_text)
                    sla_report_name_display = '-'.join(sla_report_name_display)
                    sla_data = {
                        "jsonrpc": "2.0",
                        "method": "sla.create",
                        "params": [
                            {
                                "name": sla_report_name_display,
                                "slo": "99.9995",
                                "period": sla_report_period, #  {0: "daily", 1: "weekly", 2: "monthly", 3: "quarterly", 4: "annually"}
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
                                    {"tag": "SLA-Report-Tenant", "value": sla_report_name}
                                ],
                            }
                        ],
                        "auth": auth_token,
                        "id": 1
                    }

                    

                    # Send the JSON-RPC request to the Zabbix API
                    response = requests.post(zabbix_api_endpoint, data=json.dumps(sla_data), headers={'Content-Type': 'application/json'})

                    # Check the response status code and print the response content
                    if response.status_code == 200:
                        response_data = response.json()
                        logging.info(response_data)
                    else:
                        logging.info('Error: ' + response.text)
############# Create SLA Report #############End

############# Create SLA Report Tenant All  #############Start
                sla_report_name = (device['tenant']['name'])
#                sla_report_name = '-'.join(sla_report_name)
                sla_report_tag = {"tag": "SLA-Report", "value": (sla_report_name)}
                sla_report_period = json.dumps({"period": [0, 1, 2, 3, 4]})
                sla_report_period_text_array = {0: "daily", 1: "weekly", 2: "monthly", 3: "quarterly", 4: "annually"}
                logging.info("Creating SLA Report %s", sla_report_name)
                for sla_report_period in range(0, 5):
                    sla_report_period_text = sla_report_period_text_array[sla_report_period]
                    sla_report_name_display = (device['tenant']['name'], "All", sla_report_period_text)
                    sla_report_name_display = '-'.join(sla_report_name_display)
                    sla_data = {
                        "jsonrpc": "2.0",
                        "method": "sla.create",
                        "params": [
                            {
                                "name": sla_report_name_display,
                                "slo": "99.9995",
                                "period": sla_report_period, #  {0: "daily", 1: "weekly", 2: "monthly", 3: "quarterly", 4: "annually"}
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
                                    {"tag": "SLA-Tenant", "value": sla_report_name}
                                ],
                            }
                        ],
                        "auth": auth_token,
                        "id": 1
                    }
                    
                    # Send the JSON-RPC request to the Zabbix API
                    response = requests.post(zabbix_api_endpoint, data=json.dumps(sla_data), headers={'Content-Type': 'application/json'})

                    # Check the response status code and print the response content
                    if response.status_code == 200:
                        response_data = response.json()
                        logging.info(response_data)
                    else:
                        logging.info('Error: ' + response.text)
############# Create SLA Report #############End
