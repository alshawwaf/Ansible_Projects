# create a class to read and write from different files in the class root directory
import json
from pathlib import Path
from .logger_main import log


def read_file(file_name):
    with open(file_name, 'r') as f:
        return f.read()


def write_file(file_name, mode, content):
    with open(file_name, mode=mode, encoding='utf-8') as f:
        f.write(content)


def read_config_file(file_name):
    with open(file_name, 'r') as f:
        return json.load(f)


def create_required_folders(required_folders):
    for folder in required_folders:
        try:
            Path(f"check_point_policy/{folder}").mkdir(parents=True, exist_ok=True)
            print(f"Created the {folder} folder")
        except Exception as exception:
            print(f"failed to create folder {folder} with exception: {exception}")