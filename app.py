
from flask import Flask, request, jsonify
import subprocess
import json
import logging

# Initialize logging and file name 
logging.basicConfig(level=logging.DEBUG,format='%(lineno)d - %(asctime)s [%(levelname)s] - %(message)s')
logging.info("Starting webhook-app.py")  # Added logging

app = Flask(__name__)


def compare_snapshots(prechange, postchange):
    logging.info(f"prechange: {prechange}")
    logging.info(f"postchange: {postchange}")
    changes = {}
    #if prechange is None:
    #    prechange = {}
    for key in prechange.keys():
        pre_val = prechange.get(key)
        post_val = postchange.get(key)

        if pre_val != post_val:
            changes[key] = {'prechange': pre_val, 'postchange': post_val}
            logging.info(f"Changes detected: {changes}")
            
    return changes

@app.route('/', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        # Add your processing logic here
        # For example, logging the received data
        print("Received data:", data)
        

        snapshots = data.get('Snapshots', {})
        prechange = snapshots.get('Prechange', "{}")
        postchange = snapshots.get('Postchange', "{}")
        
        if not prechange:
            prechange = "{}"
        if not postchange:
            postchange = "{}"
        
        prechange = prechange.replace("None", "null")
        postchange = postchange.replace("None", "null")
        prechange = prechange.replace("'", '"')
        postchange = postchange.replace("'", '"')
        prechange_str = f"{prechange}"
        postchange_str = f"{postchange}"
        
        try:
            prechange_dict = json.loads(prechange_str)
        except json.JSONDecodeError:
            prechange_dict = {}
        try:
            postchange_dict = json.loads(postchange_str)
        except json.JSONDecodeError:
            postchange_dict = {}

        data_array = data.get('Data', [])
        netbox_id = data_array[0].get('ID', None) if len(data_array) > 0 else None
        logging.info(f"Debug Netbox_id: {netbox_id}")

        if netbox_id is None:
            return jsonify({'error': 'Netbox ID not found in webhook payload'}), 400
        
        changes = compare_snapshots(prechange_dict, postchange_dict)
        updatetags = any(key in changes for key in ['tenant', 'status', 'site', 'role', 'platform', 'device_type'])
        
        # Print or otherwise use the changes dictionary
        if changes:
            for key, value in changes.items():
                logging.info(f"Changed field: {key}")
                logging.info(f" - updatetags: {updatetags}")
                logging.info(f" - prechange: {value['prechange']}")
                logging.info(f" - postchange: {value['postchange']}")
        else:
            logging.info("No changes detected.")

        command = [
                "python3" ,
                "netbox_zabbix_sync.py",
                '-v',
                '-w',  # Webhook host ID (Netbox ID)
                str(netbox_id)
            ]

        if updatetags:
            command.extend(['-t'])

        logging.info(f"Executing command: {command}")    
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            logging.error("Failed to execute the script.")
            return {'error': 'Failed to execute script'}, 500
        
        ### Add sla-command

    #    if any('SLA' in tag for tag in postchange_dict.get('tags', [])):
    #        logging.info("SLA detected, running sla-command")
    #        sla_command = [
    #            "python3",
    #            "netbox_zabbix_sync_sla.py"
    #        ]
    #        try:
    #            subprocess.run(sla_command, check=True)
    #        except subprocess.CalledProcessError:
    #            logging.error("Failed to execute the SLA script")
    #            return {'error': 'Failed to execute SLA script'}, 500
    #        
    #        return {'message': 'Successfully executed SLA script'}, 200

    #    return {'message': 'Successfully executed script'}, 200

            # Return a success response
        return jsonify({"message": "Data received successfully"}), 200   
    except Exception as e:
        # Log the error and return an error response
        print(f"Error processing the request: {e}")
        return jsonify({"error": "Failed to process data"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)