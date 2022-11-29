
import argparse
import sys
import yaml
from pathlib import Path
from utils.logger_main import log
from utils.api_client import API_client as api_client
from utils.cp_layer_rules_to_ansible import export_layer_rules_to_ansible
from utils.cpobject_exporter import cp_object_exporter
from utils.generate_mgmt_api_commands import export_api_commands
from utils.get_ansible_supported_modules import generate_ansible_supported_modules
from utils.file_ops import read_config_file, create_required_folders, write_file
from itertools import chain


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", default="admin")
    parser.add_argument("-p", "--password", default="demo123")
    parser.add_argument("-m", "--management", default="54.183.186.224")
    parser.add_argument("-d", "--domain", default="")
    parser.add_argument("-v", "--api_version", default="1.8")
    parser.add_argument("--update_apis", action="store_true")

    parsed_args = parser.parse_args()

    client = api_client(parsed_args.management, parsed_args.user,
                        parsed_args.password, parsed_args.domain if parsed_args.domain else None)

    # read the config file
    config = read_config_file('./config/exporter_config.json')
    # create the required folders
    create_required_folders(config['required_folders'])

    # generate the API commands if the flag is set
    if parsed_args.update_apis:
        try:
            api_version = parsed_args.api_version
            export_api_commands(api_version)
            log.info("Generated the API commands")
        except TimeoutError as exc:
            log.fatal("Timeout error: {}".format(exc))
        except Exception as e:
            log.error("Failed to generate the API commands")
            raise e

        # get the Ansible module names from the Check Point collection repository on GitHub
        try:
            generate_ansible_supported_modules()
            log.info("Generated the Ansible module names")
        except TimeoutError as exc:
            log.fatal("Timeout error: {}".format(exc))
        except Exception as e:
            log.error("Failed to generate the Ansible module names: {}".format(e))
            sys.exit(1)

    # login to the management API
    client.login()

    try:
        # create the exporter objects
        cp_object_exporter(client)
        log.info('Objects exported successfully')
    except Exception as exc:
        log.exception(exc)
        sys.exit(1)

    try:
        # get a list of all access-layer names
        access_layers = client.run_command(
        "show-access-layers", payload={})['access-layers']
        for layer_obj in access_layers:
            layer = layer_obj['name']
            # create the exporter objects
            export_layer_rules_to_ansible(client, layer)
            log.info(f'Exporting {layer} Layer')
        log.info('Rulebase exported successfully')
        
    except Exception as exc:
        log.exception(exc)
        sys.exit(1)

    #################################################################################
    ###         this is the main playbook to create the rules and the sections    ###
    #################################################################################

    cwd = Path(__file__).parent.relative_to(Path.cwd())
    objects_folder = cwd / config['output_folder_name'] / config['objects_folder_name']

    # write the playbook to a file
    playbook_file_name = config['playbook_file_name']
    playbook_file = cwd / playbook_file_name
    
    log.info("Writing the playbook to %s", playbook_file)

    exported_modules = [path.relative_to(cwd / config['output_folder_name']).as_posix()
                        for path in chain(objects_folder.iterdir())]

    object_priority = {'access-layer': 1, 'access-role': 1, 'threat-layer': 1, 'group': 1, "application-site-group": 2,
                                                                                "group-with-exclusion": 2, 'application-site-category': -1,  "simple-gateway": -1, "policy-rules": 3, "policy-rules-sections": 4 }
    priority_list = {(Path(config['objects_folder_name']) / (k + ".yml")).as_posix(): v for k, v in object_priority.items()}

    ordered_list = sorted(
        exported_modules, key=lambda k: priority_list.get(k, 0))
    playbook = [{
                "name": "Playbook for rules and objects exported to Ansible from the Check Point API",
                "connection": "httpapi",
                "hosts": "checkpoint_mgmt",
                "gather_facts": False,
                "collections": ['check_point.mgmt'],
                "vars": {"state":"present"},
                "tasks": [{"include_tasks": "{{item}}", "loop": [ module for module in ordered_list ]}]
                }]
    content = yaml.dump(playbook, sort_keys=False)
    write_file(playbook_file, mode='w', content=content)

    log.info('Playbook created successfully')

    # logout
    client.logout()


if __name__ == "__main__":
    main()
