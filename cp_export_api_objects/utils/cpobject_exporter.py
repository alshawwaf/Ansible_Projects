import sys
import json
from pathlib import Path
from utils.logger_main import log
from utils.cpobject_parser import ParseObjects
from utils.file_ops import read_file, read_config_file


def cp_object_exporter(client):

    # read the config file and create the required folders
    config = read_config_file('./config/exporter_config.json')

    config_folder_path = Path(config['config_folder_name'])
    supported_ansible_modules_file_name = config['supported_ansible_modules_file_name']
    ignored_ansible_modules_file_name = config['ignored_ansible_modules_file_name']
    suppoted_ansible_modules_file = Path.joinpath(
        config_folder_path, supported_ansible_modules_file_name)
    ignored_ansible_modules_file = Path.joinpath(
        config_folder_path, ignored_ansible_modules_file_name)
    #api_json_file = Path.joinpath(config_folder_path, config['api_json_file_name'])

    # Get the list of supported ansible modules from the config file ./supported_ansible_modules.json
    log.info(
        f'Reading supported ansible modules from file: { suppoted_ansible_modules_file }')
    supported_modules_list = json.loads(
        read_file(suppoted_ansible_modules_file))

    # read the list of API ommands from the  file ./api_commands/api_commands.json
    add_commands = []
    log.info('Reading api commands from file')
    all_api_commands = json.loads(read_file('./config/apis.json'))

    for command in all_api_commands["commands"]:
        if command['type'] == 'add':
            add_commands.append(command)
        else:
            log.debug(f"API command: {command}, not needed")

    # Get the list of ignored modules from the config file ./config/ignore_modules.json
    log.info(
        f'Reading ignored ansible modules from file: {ignored_ansible_modules_file}')
    ignored_modules_list = json.loads(read_file(ignored_ansible_modules_file))

    # if the module in the supported list and not in the ignored list, then create the ansible module object
    formatted_cp_ansible_module_names = []
    for cp_ansible_module in list(set(supported_modules_list) - set(ignored_modules_list)):
        formatted_cp_ansible_module_names.append(
            cp_ansible_module.replace('cp_mgmt_', '').replace('_', '-'))

    try:
        # create the exporter objects
        log.info('Parsing the object fields')
        ParseObjects(client, formatted_cp_ansible_module_names)
    except TimeoutError as exc:
        log.fatal("Timeout error: {}".format(exc))    
    except Exception as exc:
        log.exception(exc)
        sys.exit(1)
