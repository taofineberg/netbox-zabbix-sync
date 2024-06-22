# update_macros.py

import hvac
import requests
import logging
from datetime import datetime
import os
from zabbix_utils import ZabbixAPI, AsyncSender

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

def get_host_macros(zabbix, host_id):
    host = zabbix.host.get(filter={"hostid": host_id}, selectMacros="extend")
    return host[0]['macros'] if host else []

def update_host_macros(zabbix, host_id, macros):
    zabbix.host.update({
        "hostid": host_id,
        "macros": macros
    })

def sanitize_value(value):
    return value.strip()

async def push_to_zabbix(zabbix_server, host, item_key, zbx_item_value, timestamp):
    try:
        sender = AsyncSender(server=zabbix_server, port=10051)
        response = await sender.send_value(host, item_key, zbx_item_value, timestamp)
        logging.info(f"Successfully pushed value to Zabbix: {response}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def get_item_ids(zabbix, host_name, item_names):
    items = zabbix.item.get(filter={"host": host_name}, output=["itemid", "name"], sortfield="name")
    
    item_ids = {}
    for item in items:
        if item['name'] in item_names:
            item_ids[item['name']] = item['itemid']

    return item_ids

def update_macros(data, netbox_url, netbox_token, zabbix, itemid_update_true, itemid_update_false, itemid_error):
    if 'Snapshots' in data and 'Prechange Tags' in data['Snapshots'] and 'Postchange Tags' in data['Snapshots']:
        prechange_tags = data['Snapshots']['Prechange Tags']
        postchange_tags = data['Snapshots']['Postchange Tags']
        
        differences = get_differences(prechange_tags, postchange_tags)
        logging.info(f"Differences: {differences}")
        
        for tag in differences['added_tags']:
            if tag.startswith('HCP'):
                device_id = data['Data'][0]['ID']
                device_info = fetch_netbox_device_info(netbox_url, netbox_token, device_id)
                if device_info:
                    logging.info(f"Device info from NetBox: {json.dumps(device_info, indent=4)}")
                    
                    zabbix_hostid = device_info['custom_fields']['zabbix_hostid']
                    tenant_id = device_info.get('tenant', {}).get('id', 'default_tenant')
                    site_id = device_info.get('site', {}).get('id', 'default_site')

                    zbx_macros = device_info['config_context']['HCP-Vault']['zbx_macros']
                    logging.info(f"Zabbix host ID: {zabbix_hostid}")
                    logging.info(f"Zabbix host macros from NetBox: {json.dumps(zbx_macros, indent=4)}")
                    
                    zbx_macros = {key: value.replace('-TENENT_ID-', str(tenant_id))
                                            .replace('-DEVICE_ID-', str(device_id))
                                            .replace('-SITE_ID-', str(site_id))
                                  for key, value in zbx_macros.items()}
                    
                    try:
                        current_macros = get_host_macros(zabbix, zabbix_hostid)
                        logging.info(f"Current Zabbix host macros: {json.dumps(current_macros, indent=4)}")
                        macro_dict = {macro['macro']: macro for macro in current_macros}
                        logging.info(f"Macro dictionary: {macro_dict}")
                        updated = False
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        combined_macros = []
                        
                        for key, value in zbx_macros.items():
                            sanitized_value = sanitize_value(value)
                            if key in macro_dict:
                                if macro_dict[key]['value'] != sanitized_value:
                                    combined_macros.append({
                                        "macro": key,
                                        "value": sanitized_value,
                                        "type": macro_dict[key]['type'],
                                        "description": f"Updated by NetBox-HCP-ZBX by TF on {current_time}"
                                    })
                                    updated = True
                                else:
                                    combined_macros.append({
                                        "macro": key,
                                        "value": sanitized_value,
                                        "type": macro_dict[key]['type'],
                                        "description": macro_dict[key].get('description', "")
                                    })
                            else:
                                combined_macros.append({
                                    "macro": key,
                                    "value": sanitized_value,
                                    "type": 2,
                                    "description": f"Added by NetBox-HCP-ZBX by TF on {current_time}"
                                })
                                updated = True

                        for key, macro in macro_dict.items():
                            if key not in zbx_macros:
                                combined_macros.append({
                                    "macro": key,
                                    "value": macro['value'],
                                    "type": macro['type'],
                                    "description": macro.get('description', "")
                                })

                        if updated:
                            response = update_host_macros(zabbix, zabbix_hostid, combined_macros)
                            logging.info(f"Updated Zabbix host macros: {json.dumps(response, indent=4)}")
                            requests.post(debug_webhook_url, json={"message": "Device needs to be updated.", "device_id": device_id, "zabbix_id": zabbix_hostid})
                            message = f"Device needs to be updated. Device ID: {device_id}, Zabbix host ID: {zabbix_hostid}"
                            push_to_zabbix(zabbix, itemid_update_true, message)
                        else:
                            logging.info("No changes to macros. Update not required.")
                            requests.post(debug_webhook_url, json={"message": "No changes to macros. Update not required.", "device_id": device_id, "zabbix_id": zabbix_hostid})
                            message = f"No changes to macros. Update not required. Device ID: {device_id}, Zabbix host ID: {zabbix_hostid}"
                            push_to_zabbix(zabbix, itemid_update_false, message)
                    except Exception as e:
                        logging.error(f"An error occurred while updating Zabbix host macros: {e}")
                        requests.post(debug_webhook_url, json={"message": "An error occurred while updating Zabbix host macros.", "device_id": device_id, "zabbix_id": zabbix_hostid})
                        message = f"An error occurred while updating Zabbix host macros: device_id: {device_id}, zabbix_id: {zabbix_hostid}, error: {e}"
                        push_to_zabbix(zabbix, itemid_error, message)
                break
        
        return differences
    else:
        logging.error("Invalid payload: 'Snapshots' key or tags not found")
        return {"error": "Invalid payload"}
