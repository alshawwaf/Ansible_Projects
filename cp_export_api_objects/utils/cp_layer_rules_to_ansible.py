""" Fetch the rules and export them to ansible playbooks """
import json
import yaml
from pathlib import Path
from utils.api_client import API_client as api_client
from .logger_main import log
from .file_ops import read_config_file, write_file
# read the config file and create the required folders
config = read_config_file('./config/exporter_config.json')
output_dir = Path(config['output_folder_name']) / Path(config['objects_folder_name'])


sections_list = []
rules_list = []

class AnsibleIndent(yaml.Dumper):
    """[Set proper YAML indentation for Ansible]
    """
    def increase_indent(self, flow=False, indentless=False):
        return super(AnsibleIndent, self).increase_indent(flow, False)
    
def parse_section(entry: str, layer: str):
    """[Parse Section]
      Parse and append section.
      Check if rulebase key is available and if yes,
      check first item type to determine if it's an
      access-rule.    Args:
          entry (str): [Dict item]
          layer (str): [Current Rule layer]
    """
    global sections_list
    ############################
    ### Finding sections ###
    ############################
    sections_list.append({
        "name": f"set-access-section on top of {entry['name']}",
        "cp_mgmt_access_section": {
            "layer": layer,
            "name": entry['name'],
            "position": entry['from'],
            "state": "present"
        }
    })
    if 'rulebase' in entry:
        rulebase_type = entry['rulebase'][0]['type']
        if rulebase_type == "access-rule":
            parse_rule(entry['rulebase'], layer)
        # TODO: Nested Sections needs to be added
    return

def parse_rule(entry: list, layer):
    global rules_list
    ############################
    ### Finding all rules ###
    ############################
    for rule in entry:
        rule_template = {"name": f"task for rule number: {rule['rule-number']}, Name: {rule['name']}",
                         "cp_mgmt_access_rule": {
                             "layer": layer,
                             # "name": rule.get(rule['name'], f"rule # {rule['rule-number']}"),
                             "name": rule['name'] if rule.get('name') else f"rule # {rule['rule-number']}",
                             "position": rule['rule-number'],
                             # Source Field
                             "source": [item["name"] for item in rule['source']],
                             "source_negate": rule['source-negate'],
                             # Destination Field
                             "destination": [item["name"] for item in rule['destination']],
                             "destination_negate": rule['destination-negate'],
                             # service Field
                             "service": [item["name"] for item in rule['service']],
                             "service_negate": rule['service-negate'],
                             # content Field
                             # tracking options Field
                             # only the type is a string
                             "track": {k.replace('-', '_'): (v if k != "type" else v["name"]) for k, v in rule['track'].items()},
                             # action options Field
                             "action": rule['action']["name"] if rule['action']["name"] != 'Inner Layer' else "Apply Layer",
                             "time": [item['name'] for item in rule['time']],
                             "comments": rule['comments'],
                             "custom_fields": {k.replace('-', '_'): v for k, v in rule['custom-fields'].items()},
                             "enabled": rule['enabled'],
                             "install_on": [item["name"] for item in rule['install-on']],
                         }
                         }
        
        # service and content format
        if rule.get('service'):
            objects = [item['name'] for item in rule.get('service')]
            if objects == ["Any"]:
                rule_template["cp_mgmt_access_rule"]["service"] = "Any"
            else:
                rule_template["cp_mgmt_access_rule"]["service"] = objects

                    
        # we have to provide the inline layer name but only when it exists otherwise it will fail with an error
        if rule.get('inline-layer'):
            rule_template["cp_mgmt_access_rule"]["inline_layer"] = rule["inline-layer"]['name']
        if rule.get('action-settings') and rule.get('action')['name'] != "Inner Layer":
            rule_template["cp_mgmt_access_rule"]['action_settings'] = {k.replace(
                '-', '_'): (v if k != "limit" else v["name"]) for k, v in rule['action-settings'].items()}
        # same for above but for user check
        if rule.get('user-check'):
            rule_template["cp_mgmt_access_rule"]['user_check'] = {k: (
                v["name"] if k == "interaction" else v) for k, v in rule['user-check'].items()}
        """add the rule template to the list so we can export it in yaml. We will not add the cleanup rule because it will mess up the order
            it will also be created by default in any layer. Users can add the rule in the ansible playbook manually.
        """
        ignore_cleanup_rules = ["Cleanup rule", "Cleanup"]
        if rule_template["cp_mgmt_access_rule"]['name'] not in ignore_cleanup_rules :
            rules_list.append(rule_template)
        if rule.get('inline-layer'):
            new_layer = rule["inline-layer"]['name']
            response = api_get_rulebase(new_layer)
            parse_rulebase(response['rulebase'], new_layer)
    return

def parse_rulebase(rulebase: list, layer):
    ##################################
    ### Parse through the rulebase ###
    ##################################
    for entry in rulebase:
        # If this is a section, the rule will be inside "rulebase" object
        if entry['type'] == "access-section":
            parse_section(entry, layer)
        elif entry['type'] == "access-rule":
            parse_rule([entry], layer)
        else:
            log.info("Unknown Entry.The object is neither a rule or a section.")
    return

def api_get_rulebase(layer: str) -> json:
    response = client.run_command(
        "show-access-rulebase",
        payload={"name": layer, "use-object-dictionary": False})
    return response

def export_layer_rules_to_ansible(instance_client: api_client, layer: str):
    global client
    client = instance_client
    rulebase_response = api_get_rulebase(layer)
    parse_rulebase(rulebase_response['rulebase'], layer)
    ########################################
    ### creating rulebase sections tasks ###
    ########################################
    if sections_list:
        sections_output_file = output_dir / "policy-rules-sections.yml"
        content = yaml.dump(sections_list,
                            Dumper=AnsibleIndent,
                            sort_keys=False,
                            default_flow_style=False)
        write_file(sections_output_file,
                   mode='w',
                   content=content)

    ########################################
    ###         creating rules tasks     ###
    ########################################
    rules_output_file = output_dir / "policy-rules.yml" 
    content = yaml.dump(rules_list,
                        Dumper=AnsibleIndent,
                        sort_keys=False,
                        default_flow_style=False)
    
    # write rules to the output file
    write_file(rules_output_file,
               mode="w",
               content=content)