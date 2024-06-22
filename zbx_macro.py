#This application requires the following environment variables to be set in Azure & HCP Vault

#Azure  Environment Variables
#The `MOUNT_POINT` environment variable is used to specify HCP Vault
#The `VAULT_TOKEN` environment variable is used to authenticate with the Vault. This should be a valid token that has the necessary permissions to access the secrets stored in the Vault.
#The `VAULT_URL` environment variable is used to specify the URL of the Vault. This should be the base URL of your Vault instance, (e.g., `vault.example.com`).
#The `ZBX_MONITORING_HOST_NAME` environment variable is used to specify the hostname of the Zabbix monitoring host.

#HCP Vault Secrets locations are
#/{mount_point}/netbox/netbox_token
#/{mount_point}/netbox/netbox_url
#/{mount_point}/zabbix/zabbix_token
#/{mount_point}/zabbix/zabbix_url

from flask import Flask, request, jsonify
import hvac
import requests
import json
import logging
from datetime import datetime
import os
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import pynetbox
import zabbix_utils

# read debug webhook url
debug_webhook_url = os.getenv('DEBUG_WEBHOOK_URL')



# Global variable to keep track of uptime
uptime_counter = 0

def send_heartbeat():
    global uptime_counter
    uptime_counter += 1
    requests.post(debug_webhook_url , json={"message": f"App is up. Uptime: {uptime_counter} minutes"})

scheduler = BackgroundScheduler()
scheduler.add_job(send_heartbeat, 'interval', minutes=1)
scheduler.add_job(lambda: push_to_zabbix(zabbix_url, zabbix_token, itemid_uptime, uptime_counter), 'interval', minutes=1)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())




def get_item_ids(url, token, host_name, item_names):
    data = {
        "jsonrpc": "2.0",
        "method": "item.get",
        "params": {
            "output": ["itemid", "name"],
            "host": host_name,
            "sortfield": "name"
        },
        "auth": token,
        "id": 1
    }

    headers = {
        'content-type': 'application/json',
    }

    response = requests.post(url, data=json.dumps(data), headers=headers)
    items = response.json().get('result', [])

    item_ids = {}
    for item in items:
        if item['name'] in item_names:
            item_ids[item['name']] = item['itemid']

    return item_ids


### Add zabbix itme update 
def push_to_zabbix(zabbix_url, zabbix_token, itemid, zbx_item_value):
    data = {
        "jsonrpc": "2.0",
        "method": "history.push",
        "params": [
            {
                "itemid": itemid,
                "value": zbx_item_value,
            }
        ],
        "auth": zabbix_token,
        "id": 1
    }

    headers = {
        'content-type': 'application/json',
    }

    response = requests.post(zabbix_url, data=json.dumps(data), headers=headers)
    print(response.text)
    return response.json()


app = Flask(__name__)
requests.post(debug_webhook_url , json={"message": "Starting App"})

logging.basicConfig( level=logging.DEBUG, format='%(lineno)d - %(asctime)s [%(levelname)s] - %(message)s')

def read_vault_credentials():
    vault_url = os.getenv('VAULT_URL')
    vault_token = os.getenv('VAULT_TOKEN')
    mount_point = os.getenv('MOUNT_POINT')
    
    if not vault_url or not vault_token or not mount_point:
        raise ValueError("Environment variables for Vault credentials are not set properly.")
    
    return vault_url, vault_token, mount_point


def get_vault_credentials(vault_url, vault_token, mount_point, secret_path):
    try:
        client = hvac.Client(url=vault_url, token=vault_token)
        secret = client.secrets.kv.v2.read_secret_version(
            mount_point=mount_point,
            path=secret_path,
            raise_on_deleted_version=True
        )
        return secret['data']['data']
    except hvac.exceptions.Forbidden:
        logging.error("Permission denied. Check if the token has read access to the specified path.")
        exit(1)
    except Exception as e:
        logging.error(f"An error occurred while retrieving secrets from Vault: {e}")
        exit(1)

def get_differences(pre_tags, post_tags):
    pre_tags_set = set(pre_tags.split(", "))
    post_tags_set = set(post_tags.split(", "))
    
    removed_tags = pre_tags_set - post_tags_set
    added_tags = post_tags_set - pre_tags_set
    
    differences = {
        "removed_tags": list(removed_tags),
        "added_tags": list(added_tags)
    }
    
    return differences

def fetch_netbox_device_info(netbox_url, netbox_token, device_id):
    headers = {
        'Authorization': f'Token {netbox_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(f"{netbox_url}/api/dcim/devices/{device_id}/", headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to fetch device info from NetBox: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"RequestException while fetching device info from NetBox: {e}")
        return None

def get_host_macros(url, token, host_id):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid"],
            "selectMacros": "extend",
            "hostids": host_id
        },
        "auth": token,
        "id": 1
    }
    headers = {'content-type': 'application/json'}
    response = requests.post(url, data=json.dumps(payload), headers=headers, verify=False)
    
    if response.status_code != 200:
        raise Exception(f"Zabbix API request failed with status code {response.status_code}: {response.text}")
    
    response_json = response.json()
    if 'error' in response_json:
        raise Exception(response_json['error'])
    
    return response_json['result'][0]['macros']

def update_host_macros(url, token, host_id, macros):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.update",
        "params": {
            "hostid": host_id,
            "macros": macros
        },
        "auth": token,
        "id": 1
    }
    headers = {'content-type': 'application/json'}
    response = requests.post(url, data=json.dumps(payload), headers=headers, verify=False)
    
    if response.status_code != 200:
        raise Exception(f"Zabbix API request failed with status code {response.status_code}: {response.text}")
    
    response_json = response.json()
    if 'error' in response_json:
        raise Exception(response_json['error'])
    
    return response_json

def sanitize_value(value):
    # Placeholder function for any specific sanitization required by Zabbix
    # For now, we'll just strip leading/trailing whitespace
    return value.strip()


# Read Vault credentials from environment variables
vault_url, vault_token, mount_point = read_vault_credentials()

# Set the path to the secrets in Vault
netbox_secret_path = 'netbox'
zabbix_secret_path = 'zabbix'

# Retrieve NetBox and Zabbix credentials from Vault
netbox_credentials = get_vault_credentials(vault_url, vault_token, mount_point, netbox_secret_path)
netbox_url = netbox_credentials['netbox_url']
netbox_token = netbox_credentials['netbox_token']

# Retrieve Zabbix credentials from Vault
zabbix_credentials = get_vault_credentials(vault_url, vault_token, mount_point, zabbix_secret_path)
zabbix_url = zabbix_credentials['zabbix_url']
zabbix_token = zabbix_credentials['zabbix_token']

# Get Zabbix item IDs for monitoring
ZBX_Monitoring_host = os.getenv('ZBX_MONITORING_HOST_NAME')
item_names = ["error", "update_false", "update_true", "uptime"]
item_ids = get_item_ids(zabbix_url, zabbix_token, ZBX_Monitoring_host, item_names)
itemid_uptime = item_ids.get("uptime", "")
itemid_error = item_ids.get("error", "")
itemid_update_true = item_ids.get("update_true", "")
itemid_update_false = item_ids.get("update_false", "")


@app.route('/', methods=['POST'])
def webhook():
    try:
        if request.content_type != 'application/json':
            logging.error("Invalid content type: %s", request.content_type)
            return jsonify({"error": "Invalid content type, expecting application/json"}), 400
        
        data = request.get_json()
        if data is None:
            logging.error("No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400

        logging.info(f"Received data: {json.dumps(data, indent=4)}")
        
        if 'Snapshots' in data and 'Prechange Tags' in data['Snapshots'] and 'Postchange Tags' in data['Snapshots']:
            prechange_tags = data['Snapshots']['Prechange Tags']
            postchange_tags = data['Snapshots']['Postchange Tags']
            
            differences = get_differences(prechange_tags, postchange_tags)
            logging.info(f"Differences: {differences}")
            
            
            # Check for added tags that start with 'HCP'
            for tag in differences['added_tags']:
                if tag.startswith('HCP'):
                    device_id = data['Data'][0]['ID']  # Assuming device ID is in the Data field
                    device_info = fetch_netbox_device_info(netbox_url, netbox_token, device_id)
                    if device_info:
                        logging.info(f"Device info from NetBox: {json.dumps(device_info, indent=4)}")
                        
                        zabbix_hostid = device_info['custom_fields']['zabbix_hostid']
                        tenant_id = device_info.get('tenant', {}).get('id', 'default_tenant')
                        site_id = device_info.get('site', {}).get('id', 'default_site')

                        zbx_macros = device_info['config_context']['HCP-Vault']['zbx_macros']
                        logging.info(f"Zabbix host ID: {zabbix_hostid}")
                        logging.info(f"Zabbix host macros from NetBox: {json.dumps(zbx_macros, indent=4)}")
                        
                        # Replace placeholders in macros
                        zbx_macros = {key: value.replace('-TENENT_ID-', str(tenant_id))
                                                .replace('-DEVICE_ID-', str(device_id))
                                                .replace('-SITE_ID-', str(site_id))
                                      for key, value in zbx_macros.items()}
                        
                        try:
                            current_macros = get_host_macros(zabbix_url, zabbix_token, zabbix_hostid)
                            logging.info(f"Current Zabbix host macros: {json.dumps(current_macros, indent=4)}")
                            macro_dict = {macro['macro']: macro for macro in current_macros}
                            logging.info(f"Macro dictionary: {macro_dict}")
                            updated = False
                            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            combined_macros = []
                            
                            for key, value in zbx_macros.items():
                                sanitized_value = sanitize_value(value)
                                if key in macro_dict:
                                    # If the macro exists and the value is different, update it
                                    if macro_dict[key]['value'] != sanitized_value:
                                        combined_macros.append({
                                            "macro": key,
                                            "value": sanitized_value,
                                            "type": macro_dict[key]['type'],
                                            "description": f"Updated by NetBox-HCP-ZBX by TF on {current_time}"
                                        })
                                        updated = True
                                    else:
                                        # If the value is the same, retain the existing description and type
                                        combined_macros.append({
                                            "macro": key,
                                            "value": sanitized_value,
                                            "type": macro_dict[key]['type'],
                                            "description": macro_dict[key].get('description', "")
                                        })
                                else:
                                    # If the macro does not exist, add it
                                    combined_macros.append({
                                        "macro": key,
                                        "value": sanitized_value,
                                        "type": 2,  # Set type to 2
                                        "description": f"Added by NetBox-HCP-ZBX by TF on {current_time}"
                                    })
                                    updated = True

                            # Add existing macros that are not in zbx_macros
                            for key, macro in macro_dict.items():
                                if key not in zbx_macros:
                                    combined_macros.append({
                                        "macro": key,
                                        "value": macro['value'],
                                        "type": macro['type'],
                                        "description": macro.get('description', "")
                                    })

                            if updated:
                                response = update_host_macros(zabbix_url, zabbix_token, zabbix_hostid, combined_macros)
                                logging.info(f"Updated Zabbix host macros: {json.dumps(response, indent=4)}")
                                requests.post(debug_webhook_url , json={"message": "Device needs to be updated.", "device_id": device_id, "zabbix_id": zabbix_hostid})
                                message = f"Device needs to be updated. Device ID: {device_id}, Zabbix host ID: {zabbix_hostid}"
                                push_to_zabbix(zabbix_url, zabbix_token, itemid_update_true, message)
                            else:
                                logging.info("No changes to macros. Update not required.")
                                requests.post(debug_webhook_url , json={"message": "No changes to macros. Update not required.", "device_id": device_id, "zabbix_id": zabbix_hostid})
                                message = f"No changes to macros. Update not required. Device ID: {device_id}, Zabbix host ID: {zabbix_hostid}"
                                push_to_zabbix(zabbix_url, zabbix_token, itemid_update_false, message)
                        except Exception as e:
                            logging.error(f"An error occurred while updating Zabbix host macros: {e}")
                            requests.post(debug_webhook_url , json={"message": "An error occurred while updating Zabbix host macros.", "device_id": device_id, "zabbix_id": zabbix_hostid})
                            message = f"An error occurred while updating Zabbix host macros: device_id: {device_id}, zabbix_id: {zabbix_hostid}, error: {e}"
                            push_to_zabbix(zabbix_url, zabbix_token, itemid_error, message)
                    break
            
            return jsonify(differences)
        else:
            logging.error("Invalid payload: 'Snapshots' key or tags not found")
            return jsonify({"error": "Invalid payload"}), 400
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
