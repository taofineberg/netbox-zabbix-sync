from flask import Flask, request, jsonify
import subprocess
import logging
from modules.webhook_utils import compare_snapshots, normalize_json  # Import functions from the new module
from update_macros import update_macros
import os
import atexit
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from update_macros import update_macros
from hcp_config import netbox_url, netbox_token, zabbix, itemid_uptime, itemid_error, itemid_update_true, itemid_update_false
from modules.webhook_utils import compare_snapshots, normalize_json  # Import functions from the new module


# Initialize logging
logging.basicConfig(level=logging.DEBUG, format='%(lineno)d - %(asctime)s [%(levelname)s] - %(message)s')
logging.info("Starting webhook-app.py")


app = Flask(__name__)

@app.route('/', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        logging.info("Received data: %s", data)

        snapshots = data.get('Snapshots', {})
        prechange = snapshots.get('Prechange', "{}")
        postchange = snapshots.get('Postchange', "{}")

        prechange_dict = normalize_json(prechange)
        postchange_dict = normalize_json(postchange)

        data_array = data.get('Data', [])
        netbox_id = data_array[0].get('ID', None) if data_array else None
        logging.info(f"Debug Netbox_id: {netbox_id}")

        if netbox_id is None:
            return jsonify({'error': 'Netbox ID not found in webhook payload'}), 400

        changes = compare_snapshots(prechange_dict, postchange_dict)
        updatetags = any(key in changes for key in ['tenant', 'status', 'site', 'role', 'platform', 'device_type'])

        if changes:
            for key, value in changes.items():
                logging.info(f"Changed field: {key}")
                logging.info(f" - updatetags: {updatetags}")
                logging.info(f" - prechange: {value['prechange']}")
                logging.info(f" - postchange: {value['postchange']}")
        else:
            logging.info("No changes detected.")
        
        # Run the update_macros function if the tag starts with 'HCP'
        if data['tag'].startswith('HCP'):
            logging.info("HCP tag detected, running HCP command")
            run_macro_update = update_macros(data, netbox_url, netbox_token, zabbix, itemid_update_true, itemid_update_false, itemid_error)

        if "error" in run_macro_updatemacro_update:
            return jsonify(run_macro_update), 400


        command = ["python3", "netbox_zabbix_sync.py", '-v', '-w', str(netbox_id)]
        logging.info(f"Executing command: {command}")

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            logging.error("Failed to execute the script.")
            return jsonify({'error': 'Failed to execute script'}, 500)
        
        
        # Uncomment and implement the SLA script execution if needed
        # if any('SLA' in tag for tag in postchange_dict.get('tags', [])):
        #     logging.info("SLA detected, running SLA command")
        #     sla_command = [
        #         "python3",
        #         "netbox_zabbix_sync_sla.py"
        #     ]
        #     try:
        #         subprocess.run(sla_command, check=True)
        #     except subprocess.CalledProcessError:
        #         logging.error("Failed to execute the SLA script")
        #         return jsonify({'error': 'Failed to execute SLA script'}, 500)
        #     return jsonify({'message': 'Successfully executed SLA script'}), 200

        return jsonify({"message": "Data received successfully"}), 200
    except Exception as e:
        logging.error(f"Error processing the request: {e}")
        return jsonify({"error": "Failed to process data"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
