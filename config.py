## Template logic.
# Set to true to enable the template source information
# coming from config context instead of a custom field.
templates_config_context = False

# Set to true to give config context templates a 
# higher priority then custom field templates
templates_config_context_overrule = False

# Set template and device Netbox "custom field" names
# Template_cf is not used when templates_config_context is enabled
template_cf = "zabbix_template"
device_cf = "zabbix_hostid"

## Enable clustering of devices with virtual chassis setup
clustering = False

## Enable hostgroup generation. Requires permissions in Zabbix
create_hostgroups = True

## Create journal entries
create_journal = False

## Proxy Sync
# Set to true to enable removal of proxy's under hosts. Use with caution and make sure that you specified
# all the required proxy's in the device config context before enabeling this option.
# With this option disabled proxy's will only be added and modified for Zabbix hosts.
full_proxy_sync = False

## Netbox to Zabbix device state convertion
zabbix_device_removal = ["Decommissioning", "Inventory","Deployed"]
zabbix_device_disable = ["Offline", "Planned", "Staged", "Failed"]

## Hostgroup mapping
# Available choices: dev_location, dev_role, manufacturer, region, site, site_group, tenant, tenant_group
# You can also use CF (custom field) names under the device. The CF content will be used for the hostgroup generation.
#
# When using region in the group name, the default behaviour is to use name of the directly assigned region.
# By setting traverse_regions to True the full path of all parent regions will be used in the hostgroup, e.g.:
#
# 'Global/Europe/Netherlands/Amsterdam' instead of just 'Amsterdam'.
#
# traverse_site_groups controls the same behaviour for any assigned site_groups.   
hostgroup_format = "site/manufacturer/dev_role"
traverse_regions = False
traverse_site_groups = False

## Filtering
# Custom device filter, variable must be present but can be left empty with no filtering.
# A couple of examples:
#  nb_device_filter = {} #No filter
#  nb_device_filter = {"tag": "zabbix"} #Use a tag
#  nb_device_filter = {"site": "HQ-AMS"} #Use a site name
#  nb_device_filter = {"site": ["HQ-AMS", "HQ-FRA"]} #Device must be in either one of these sites
#  nb_device_filter = {"site": "HQ-AMS", "tag": "zabbix", "role__n": ["PDU", "console-server"]} #Device must be in site HQ-AMS, have the tag zabbix and must not be part of the PDU or console-server role

# Default device filter, only get devices which have a name in Netbox:
nb_device_filter = {"name__n": "null"}

## Inventory
# To allow syncing of NetBox device properties, set inventory_sync to True
inventory_sync = True

# Set inventory_automatic to False to use manual inventory, True for automatic
# See https://www.zabbix.com/documentation/current/en/manual/config/hosts/inventory#building-inventory 
inventory_automatic = True

# inventory_map is used to map NetBox properties to Zabbix Inventory fields.
# For nested properties, you can use the '/' seperator.
# For example, the following map will assign the custom field 'mycustomfield' to the 'alias' Zabbix inventory field:
#
# inventory_map = { "custom_fields/mycustomfield/name": "alias"}
#
# The following map should provide some nice defaults:
inventory_map = { "asset_tag": "asset_tag",
                  "virtual_chassis/name": "chassis",
                  "status/label": "deployment_status",
                  "location/name": "location",
                  "latitude": "location_lat",
                  "longitude": "location_lon",
                  "comments": "notes",
                  "name": "name",
                  "rack/name": "site_rack",
                  "serial": "serialno_a",
                  "device_type/model": "type",
                  "device_type/manufacturer/name": "vendor",
                  "oob_ip/address": "oob_ip" }

### HCP Configuration ###
# Set to true to enable HCP

netbox_secret_path = 'netbox'
zabbix_secret_path = 'zabbix'
use_hcp_vault = True