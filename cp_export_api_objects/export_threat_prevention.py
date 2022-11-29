""" Fetch the threat policy and export them to ansible playbooks """

import argparse
import yaml
from pathlib import Path
from utils.api_client import API_client as api_client
from utils.logger_main import log
from utils.file_ops import read_config_file, write_file

# read the config file and create the required folders
config = read_config_file('./config/exporter_config.json')
output_dir = Path(config['output_folder_name']) / Path(config['objects_folder_name'])

class AnsibleIndent(yaml.Dumper):
    """[Set proper YAML indentation for Ansible]
    """
    def increase_indent(self, flow=False, indentless=False):
        return super(AnsibleIndent, self).increase_indent(flow, False)
    
def export_threat_layers(client):
    # get a list of all threat layers 
    threat_layers = client.run_command(
        "show-threat-layers", payload={"details-level": "full"})['threat-layers']
    
    threat_layers_list = []
    for layer in threat_layers:     
        threat_layer_module =  { "name" : f"Task for Threat Layer: {layer['name']}" ,
                "cp_mgmt_threat_layer": {
                    "name": layer['name'],
                    "comments": layer['comments'],
                    "color": layer['color'],
                    "tags": [],
                    "state": '{{state}}',
                    "add_default_rule": False,
                    "ignore_warnings": False,
                    "ignore_errors": False,
                    "wait_for_task": True,
                    "wait_for_task_timeout": '30',
                },
            }
        threat_layers_list.append(threat_layer_module)

    rules_output_file = output_dir / "threat-layer.yml" 
    content = yaml.dump(threat_layers_list,
                        Dumper=AnsibleIndent,
                        sort_keys=False,
                        default_flow_style=False)
    
    # write rules to the output file
    write_file(rules_output_file,
               mode="w",
               content=content)

def export_threat_profiles(client):
        # get a list of all access-profile names
    threat_profiles = client.run_command(
        "show-threat-profiles", payload={"details-level": "full"})['profiles']
    
    threat_profiles_list = []
    
    for profile in threat_profiles: 
        if profile['meta-info']['last-modifier'] != "System":
            log.info(f"Exporting the profile: {profile['name']}")  
            threat_profile_module =  { "name" : f"Task for Threat profile: {profile['name']}" ,
            "cp_mgmt_threat_profile": {
                "state": '{{state}}',
                "ignore_warnings": False,
                "ignore_errors": False,
                "wait_for_task": True,
                "wait_for_task_timeout": '30',
            },
        }  
            ignored_fields = ["uid", "domain", "type", "icon", "meta-info", "available-actions", "read-only", "extended-attributes-to-activate", "extended-attributes-to-deactivate", "scan-malicious-links", "threat-extraction", "zero-phishing"]
            for k, v in profile.items():
                if k not in ignored_fields:  
                    threat_profile_module['cp_mgmt_threat_profile'][k] = v 
            threat_profile_module_formatted = convert_dashes_in_keys(threat_profile_module)
            threat_profiles_list.append(threat_profile_module_formatted)
   
    profiles_output_file = output_dir / "threat-profile.yml" 
    content = yaml.dump(threat_profiles_list,
                        Dumper=AnsibleIndent,
                        sort_keys=False,
                        default_flow_style=False)
    
    # write rules to the output file
    log.info(f"Writing the profile to {profiles_output_file}")  
    write_file(profiles_output_file,
               mode="w",
               content=content)

def export_threat_rules(client):
    # get a list of all threat layers 
    threat_layers = client.run_command(
        "show-threat-layers", payload={"details-level": "full"})['threat-layers']
    
    threat_rules_list = []
    for layer in threat_layers: 
        if layer['meta-info']['last-modifier'] != "System":
            log.info(f"Exporting Threat Rules from the layer: {layer['name']}") 
             
            threat_rules = client.run_command(
            "show-threat-rulebase", payload={"name": f"{layer['name']}","details-level": "full"})['rulebase']  
            
            for threat_rule in threat_rules:
                if threat_rule['available-actions']['delete'] != "false":
                    log.info(f"Exporting Threat Rule number {threat_rule.get('rule-number')}")
                    threat_rule_module =  { "name" : f"Task for Threat rule number {threat_rule.get('rule-number')}" ,
                        "cp_mgmt_threat_rule": {
                            "name": (threat_rule.get('name') if threat_rule.get('name') is not None else threat_rule['rule-number']),
                            "position": threat_rule['rule-number'],
                            "layer": layer['name'],
                            "enabled": threat_rule['enabled'],
                            "action": convert_ids_to_names(client, threat_rule['action']),
                            "source": convert_ids_to_names(client, threat_rule['source']),
                            "source_negate": threat_rule['source-negate'],
                            "destination": convert_ids_to_names(client, threat_rule['destination']),
                            "destination_negate": threat_rule['destination-negate'],
                            "service": convert_ids_to_names(client, threat_rule['service']),
                            "service_negate": threat_rule['service-negate'],
                            "protected_scope": convert_ids_to_names(client, threat_rule['protected-scope']),
                            "protected_scope_negate": threat_rule['protected-scope-negate'],
                            "track": convert_ids_to_names(client, threat_rule['track']),
                            "track_settings": convert_dashes_in_keys(threat_rule['track-settings']),
                            "comments": threat_rule['comments'],
                            "install_on": convert_ids_to_names(client, threat_rule['install-on']),
                            "state": '{{state}}',
                            "ignore_warnings": False,
                            "ignore_errors": False,
                            "wait_for_task": True,
                            "wait_for_task_timeout": '30',
                        },
                    }
                    threat_rules_list.append(threat_rule_module)
   
    rules_output_file = output_dir / "threat-rule.yml" 
    content = yaml.dump(threat_rules_list,
                        Dumper=AnsibleIndent,
                        sort_keys=False,
                        default_flow_style=False)
    
    # write rules to the output file
    write_file(rules_output_file,
               mode="w",
               content=content) 

# convert uids into names:
def convert_ids_to_names(client, uid):
    if uid is not None:
        if type(uid) in [str, int, bool]:
            object_name = client.run_command("show-object", payload={"uid": uid})['object']['name']
            log.info(f"replacing object id {uid} with name {object_name}")
            return object_name
        elif type(uid) == list:
            names_list = []
            for item in uid:
                object_name = client.run_command("show-object", payload={"uid": item})['object']['name']
                log.info(f"replacing object id {item} with name {object_name}")
                # Policy Target should be returned as a string not a list
                if object_name == "Policy Targets":
                    return object_name
                names_list.append(object_name) 
            return names_list

def convert_dashes_in_keys(obj):
    if obj is not None:
        if type(obj) in [str, int, bool]:
            return obj
        if type(obj) == list:
            return [convert_dashes_in_keys(v) for v in obj]
        if type(obj) == dict:
            return {k.replace('-', '_'): convert_dashes_in_keys(v) for k, v in obj.items() if k != "exclude-protection-with-performance-impact-mode"}
        raise ValueError(f"Unknown type: {obj}")
    return obj

def export_threat_exceptions(client):
    # get a list of all threat layers 
    threat_layers = client.run_command(
        "show-threat-layers", payload={"details-level": "full"})['threat-layers']
    
    threat_exception_list = []
    for layer in threat_layers: 
        if layer['meta-info']['last-modifier'] != "System":
            log.info(f"Exporting Threat-Exception rules from the layer: {layer['name']}") 
             
            threat_exceptions = client.run_command(
            "show-threat-rule-exception-rulebase", payload={"name": f"{layer['name']}", "rule-number": "3","details-level": "full", "use-object-dictionary": "false"})['rulebase'][0]['rulebase']
                
            for exception_rule in threat_exceptions:
                    log.info(f"Exporting Threat Rule number {exception_rule}")
                    threat_exception_module =  { "name" : f"Task for Threat rule number {exception_rule.get('exception-number')}" ,
                        "cp_mgmt_threat_rule": {
                            "name": (exception_rule.get('name') if exception_rule.get('name') is not None else exception_rule['exception-number']),
                            "position": exception_rule['exception-number'],
                            "layer": layer['name'],
                            #"rule_name": exception_rule['rule-name'],
                            "protection_or_site": exception_rule['protection-or-site'],
                            "enabled": exception_rule['enabled'],
                            "action": convert_ids_to_names(client, exception_rule['action']),
                            "source": convert_ids_to_names(client, exception_rule['source']),
                            "source_negate": exception_rule['source-negate'],
                            "destination": convert_ids_to_names(client, exception_rule['destination']),
                            "destination_negate": exception_rule['destination-negate'],
                            "service": convert_ids_to_names(client, exception_rule['service']),
                            "service_negate": exception_rule['service-negate'],
                            "protected_scope": convert_ids_to_names(client, exception_rule['protected-scope']),
                            "protected_scope_negate": exception_rule['protected-scope-negate'],
                            "track": convert_ids_to_names(client, exception_rule['track']),
                            "track_settings": convert_dashes_in_keys(exception_rule['track-settings']),
                            "comments": exception_rule['comments'],
                            "install_on": convert_ids_to_names(client, exception_rule['install-on']),
                            "state": '{{state}}',
                            "ignore_warnings": False,
                            "ignore_errors": False,
                            "wait_for_task": True,
                            "wait_for_task_timeout": '30',
                        },
                    }
                    threat_exception_list.append(threat_exception_module)

    rules_output_file = output_dir / "threat-exception.yml" 
    content = yaml.dump(threat_exception_list,
                        Dumper=AnsibleIndent,
                        sort_keys=False,
                        default_flow_style=False)
    
    # write rules to the output file
    write_file(rules_output_file,
               mode="w",
               content=content) 
    
        
def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", default="admin")
    parser.add_argument("-p", "--password", default="demo123")
    parser.add_argument("-m", "--management", default="54.183.186.224")
    parser.add_argument("-d", "--domain", default="")
    parser.add_argument("-v", "--api_version", default="1.8")
    parser.add_argument("--update_apis", action="store_true")

    parsed_args = parser.parse_args()
    client = api_client (parsed_args.management, parsed_args.user,
                        parsed_args.password, parsed_args.domain if parsed_args.domain else None)

    client.login()

    export_threat_layers(client)
    
    export_threat_profiles(client)
    
    #export_threat_rules(client)
    
    #export_threat_exceptions(client)
   
if __name__ == "__main__":
    main()