# hcp_config.py

import os
from update_macros import read_vault_credentials, get_vault_credentials, get_item_ids
from zabbix_utils import ZabbixAPI

def initialize_config():
    # Read Vault credentials from environment variables
    vault_url, vault_token, mount_point = read_vault_credentials()

    # Set the path to the secrets in Vault
    netbox_secret_path = 'netbox'
    zabbix_secret_path = 'zabbix'

    # Retrieve NetBox and Zabbix credentials from Vault
    netbox_credentials = get_vault_credentials(vault_url, vault_token, mount_point, netbox_secret_path)
    netbox_url = netbox_credentials['netbox_url']
    netbox_token = netbox_credentials['netbox_token']

    zabbix_credentials = get_vault_credentials(vault_url, vault_token, mount_point, zabbix_secret_path)
    zabbix_url = zabbix_credentials['zabbix_url']
    zabbix_token = zabbix_credentials['zabbix_token']

    # Initialize Zabbix API
    zabbix = ZabbixAPI(zabbix_url, token=zabbix_token)

    # Get Zabbix item IDs for monitoring
    ZBX_Monitoring_host = os.getenv('ZBX_MONITORING_HOST_NAME')
    item_names = ["error", "update_false", "update_true", "uptime"]
    item_ids = get_item_ids(zabbix, ZBX_Monitoring_host, item_names)

    return netbox_url, netbox_token, zabbix, item_ids

netbox_url, netbox_token, zabbix, item_ids = initialize_config()
itemid_uptime = item_ids.get("uptime", "")
itemid_error = item_ids.get("error", "")
itemid_update_true = item_ids.get("update_true", "")
itemid_update_false = item_ids.get("update_false", "")
