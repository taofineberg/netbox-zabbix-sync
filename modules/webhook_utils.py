import json
import logging

def compare_snapshots(prechange, postchange):
    logging.info(f"prechange: {prechange}")
    logging.info(f"postchange: {postchange}")
    changes = {}

    for key in prechange.keys():
        pre_val = prechange.get(key)
        post_val = postchange.get(key)

        if pre_val != post_val:
            changes[key] = {'prechange': pre_val, 'postchange': post_val}
            logging.info(f"Changes detected: {changes}")

    return changes

def normalize_json(json_string):
    json_string = json_string.replace("None", "null").replace("'", '"')
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        return {}

def get_differences_tag(pre_tags, post_tags):
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

def get_host_macros(zabbix , host_id):
    host = zabbix .host.get(filter={"hostid": host_id}, selectMacros="extend")
    return host[0]['macros'] if host else []

def update_host_macros(zabbix , host_id, macros):
    zabbix .host.update({
        "hostid": host_id,
        "macros": macros
    })

def sanitize_value(value):
    return value.strip()

def get_item_ids(zabbix , host_name, item_names):
    items = zabbix .item.get(filter={"host": host_name}, output=["itemid", "name"], sortfield="name")
    
    item_ids = {}
    for item in items:
        if item['name'] in item_names:
            item_ids[item['name']] = item['itemid']

    return item_ids