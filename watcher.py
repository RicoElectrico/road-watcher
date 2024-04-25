import requests
import json
import gzip
import os
import time

def fetch_data_from_overpass_api(query):
    overpass_url = "http://overpass-api.de/api/interpreter"
    response = requests.get(overpass_url, params={"data": query}, timeout=600)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error fetching data from Overpass API:", response.status_code)
        return None

def save_data_to_gzip_file(data, filename):
    with gzip.open(filename, "wt") as f:
        json.dump(data, f)

def load_data_from_gzip_file(filename):
    with gzip.open(filename, "rt") as f:
        return json.load(f)

def extract_highway_data(json_data):
    highway_data = {}
    if "elements" in json_data:
        for element in json_data["elements"]:
            if element["type"] == "way" and "highway" in element["tags"]:
                data = {
                    "timestamp": element["timestamp"],
                    "changeset": element["changeset"],
                    "user": element["user"],
                    "highway": element["tags"]["highway"],
                }
                highway_data[element["id"]] = data
    return highway_data

def find_changed_highways(previous_data, current_data):
    changed_ways = {}
    for id, previous_way in previous_data.items():
        if current_data.get(id):
            current_way = current_data[id]
            if current_way["highway"] != previous_way["highway"]:
                changed_ways[id] = {
                    "previous_highway": previous_way["highway"],
                    "current_highway": current_way["highway"],
                    "changeset": current_way["changeset"],
                    "user": current_way["user"],
                    }
    return changed_ways

def changeset_link(id):
    return f"[{id}](http://osm.org/changeset/{id})"

def user_link(name):
    return f"[{name}](http://osm.org/user/{name})"

def way_link(id):
    return f"[{id}](http://osm.org/way/{id})"

def format_changeset(id, changeset):
    txt = f"**Changeset {changeset_link(id)} by {user_link(changeset['user'])}**\n"
    for tag_change, way_list in changeset['tag_changes'].items():
        # txt += f"{tag_change[0]} → {tag_change[1]}: {' '.join([way_link(i) for i in way_list])}\n"
        txt += f"{tag_change[0]} → {tag_change[1]}: {len(way_list)} way(s)\n"
    return txt

def send_webhook(url, message):
    headers = {'Content-Type': 'application/json'}
    data = {'content': message}
    response = requests.post(url, headers=headers, data=json.dumps(data), timeout=30)

    if response.status_code == 204:
        print("Webhook message sent successfully.")
    else:
        print(f"Failed to send webhook message. Status code: {response.status_code}")


def main():

    try:
        import config
    except ModuleNotFoundError:
        print("Error: The config.py file is missing. Please copy config.py.example and set your secrets there.")
        exit(1)

    if not config.skip_download:
        json_data = fetch_data_from_overpass_api(config.overpass_query)
        if not json_data:
            print("Error fetching data from Overpass API. Exiting.")
            return

        # Check if previous result file exists and rename it
        if os.path.exists("result.json.gz"):
            os.rename("result.json.gz", "previous_result.json.gz")
        # Save current data to result file
        save_data_to_gzip_file(json_data, "result.json.gz")

    # If no rename was done (i.e., no previous file), exit
    if not os.path.exists("previous_result.json.gz"):
        print("No previous result file exists. Exiting.")
        return


    previous_data = extract_highway_data(load_data_from_gzip_file("previous_result.json.gz"))
    current_data = extract_highway_data(load_data_from_gzip_file("result.json.gz"))

    changed_ways = find_changed_highways(previous_data, current_data)

    changesets = {}


    for id, way in changed_ways.items():
        changeset_id = way["changeset"]
        user = way["user"]
        tag_change = (way["previous_highway"], way["current_highway"])
        way_data = {"tag_change": tag_change, "id": id}
        changesets.setdefault(changeset_id, {"ways": [], "user": user})["ways"].append(way_data)

    for changeset_id, changeset in changesets.items():
        ways = changeset.pop("ways", None)
        tag_changes = {}
        for way in ways:
            tag_change = way["tag_change"]
            way_id = way["id"]
            tag_changes.setdefault(tag_change, []).append(way_id)
        changesets[changeset_id]["tag_changes"] = tag_changes

    for changeset_id, changeset in changesets.items():
        message = format_changeset(changeset_id, changeset)
        print(f"Sending changeset {changeset_id}: ", end="")
        send_webhook(config.webhook_url, message)
        time.sleep(2)

    if not changesets:
        print("No changes detected.")

if __name__ == "__main__":
    main()
