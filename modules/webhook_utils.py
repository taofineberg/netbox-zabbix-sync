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
