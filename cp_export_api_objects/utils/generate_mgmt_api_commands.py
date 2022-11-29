"""

This script will download the raw json file for commands in a specific version of the Check Point API.
The script will then parse the json file and generate a json file with the following format:
    {
    "command": "add-access-layer",
    "description": "Create new object.",
    "type": "add",
    "fields": {
        "key": null,
        "key": null,
    }

"""
import json
import sys
import requests
from pathlib import Path
from .file_ops import read_config_file, write_file
from .logger_main import log

config = read_config_file('./config/exporter_config.json')
config_folder = config.get("config_folder_name")
api_json_file = config.get("api_json_file_name")
api_version = config.get("api_version")


def download_api_json_file(api_json_file_url):
    response = requests.request('GET', api_json_file_url)
    log.info(f"Downloading API file from: {api_json_file_url}")
    if response.status_code == 200:
        log.info(f"Saving API file to: apis.json")
        write_file("./config/apis.json", mode='w', content=response.text)

    else:
        log.error(f"Error:{response.status_code}")
        sys.exit(1)


def parse_api_fields():
    # download the json file fro  URL and save it under the folder apis with the name apis.json
    api_json_file_url = f"https://sc1.checkpoint.com/documents/latest/APIs/data/v{api_version}/dynamic/apis.json"

    # read the json file
    download_api_json_file(api_json_file_url)
    data = json.loads("".join(
        [chr(x) for x in open("./config/apis.json", 'rb').read()]))

    api_commands = {k["name"]["web"]: k for k in data["commands"]}
    api_objects = {k["name"]: k for k in data["objects"]}
    commands = []
    for k, v in sorted(api_commands.items()):
        command = {}
        command["command"] = k
        command["description"] = v["description"]
        command["type"] = v["type"]
        fields = {}

        for field in api_objects[v["request"]]["fields"]:
            fields.update({field["name"]: None})

        for field in api_objects[v["request"]]["required-fields"]:
            fields.update({field["name"]: None})

        for field in api_objects[v["request"]]["under-more-fields"]:
            fields.update({field["name"]: None})

        command["fields"] = fields

        # we only save the show and add commands since we are trying to find which fields can be used
        if command["type"] == "show" or command["type"] == "add":
            commands.append(command)

    # # save the commands object to a json file named api_commands.json
    content = json.dumps(commands)
    write_file('./config/api_commands.json', mode='w', content=content)


def export_api_commands(api_version):
    parse_api_fields()  # sys.argv[1]


if __name__ == "__main__":
    export_api_commands()
