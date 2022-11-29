import json
import yaml
from pathlib import Path
from .file_ops import read_config_file, write_file
from .logger_main import log


class ParseObjects:
    def __init__(self, client, formatted_cp_ansible_module_names):
        self.client = client
        self.config = read_config_file('./config/exporter_config.json')
        self.config_folder_name = self.config['config_folder_name']
        self.formatted_cp_ansible_module_names = formatted_cp_ansible_module_names
        self.db_objects = self.get_objects()

    def get_objects(self):

        for cp_ansible_command in self.formatted_cp_ansible_module_names:
            db_objects = []
            done = False
            offset = 0
            while not done:
                get_objects = self.client.run_command(
                    "show-objects", payload={'type': cp_ansible_command, 'details-level': 'full', "limit": "500", "offset": offset})

                if get_objects['total'] == 0:
                    done = True
                    log.info(f"No {cp_ansible_command} objects found")
                    break
                if get_objects['total'] > get_objects['to']:

                    offset = int(get_objects['to'])
                    from_position = int(get_objects['from'])
                    total = get_objects['total']

                    log.info(
                        f"Parsing {cp_ansible_command} objects from {from_position} to {offset} out of {total}")

                else:
                    done = True

                for cp_object in get_objects['objects']:
                    if cp_object['type'] != cp_ansible_command:
                        log.error(
                            f" {cp_object['name']} with type: {cp_object['type']} found while parsing {cp_ansible_command} objects")
                    else:
                        db_objects.append(cp_object)

            # write_file('./objects/' + cp_ansible_command +'.json', mode = 'w', content=json.dumps(db_objects))
            self.parse_objects(db_objects, cp_ansible_command)

    def parse_objects(self, db_objects, cp_ansible_command):

        exported_objects = []
        # we need to match the fields from the DB and the fields from the API reference
        for db_object in db_objects:
            log.debug(db_object)
            if db_object['meta-info']['last-modifier'] != "System":

                # TODO create documentations (json export) for handling objects with API/Ansible limitations
                docs_objects = ['access-role', 'simple-gateway',
                                'simple-cluster', 'vpn-community-meshed', 'vpn-community-star']
                if db_object['type'] in docs_objects:
                    write_file(
                        './check_point_policy/docs/' + db_object['type'] + '.json', mode='a', content=json.dumps(db_object))

                # delete the fields that are not needed in the Ansible playbook
                db_object_fields_deleted = self.delete_object_fields(db_object)

                # format the object fields
                db_object_fields_formatted = self.format_object_fields(
                    db_object_fields_deleted)

                # add common fields for all objects
                db_object_fields_added = self.add_object_common_fields(
                    db_object_fields_formatted)

                # create the Ansible playbook object
                # log.error(db_object_fields_added["type"])
                command_module = self.create_ansible_module_object(
                    cp_ansible_command, db_object_fields_added)

                exported_objects.append(command_module)

        # we publish after creating 30 objects for better performance
        module_len = len(exported_objects)
        for item in range(30, module_len, 30):
            log.info(f"Inserting publisher at position {item}")
            exported_objects.insert(
                item, {'name': 'Publish Current Changes', 'cp_mgmt_publish': ''})

        # write the Ansible code to a file
        # write_file('./objects/' + cp_ansible_command +'.json', json.dumps(exported_objects))
        objects_folder = Path('check_point_policy/objects/')
        output_file_path = str(Path.joinpath(
            objects_folder, cp_ansible_command))
        if exported_objects:
            content = yaml.dump(exported_objects, sort_keys=False)
            write_file(output_file_path + '.yml', mode='w', content=content)

        else:
            log.info(f"No objects found for {cp_ansible_command}")

    # adding common fields for all objects

    def add_object_common_fields(self, db_object):

        db_object['state'] = "{{state}}"
        db_object['ignore_warnings'] = self.config.get('ignore_warnings')
        db_object['ignore_errors'] = self.config.get('ignore_errors')
        db_object['wait_for_task'] = self.config.get('wait_for_task')
        db_object['wait_for_task_timeout'] = self.config.get(
            'wait_for_task_timeout')

        if db_object['type'] == 'simple-gateway' or db_object['type'] == 'simple-cluster':
            del db_object['ignore_errors']
            
        # we need to use this option since we are exporing the cleanup rule from tbhe source machine  
        # This is not supported since the module uses a set-access-rule command   
        #if db_object['type'] == 'access-layer':
        #    db_object['add_default_rule'] = False

        return db_object

    # format the object fields

    def format_object_fields(self, db_object):

        # TODO we will need the customer to create the GW and estalish SIC. We need to create documentations for this
        if db_object['type'] == 'simple-gateway' or db_object['type'] == 'simple-cluster':
            return {"name": db_object['name'], "type": db_object['type'], "ipv4_address": db_object['ipv4-address']}

        # TODO we will need the customer to configure the vpn community settings
        if db_object['type'] == 'vpn-community-meshed' or db_object['type'] == 'vpn-community-star':
            return {"name": db_object['name'], "type": db_object['type']}

        db_object['tags'] = [item['name'] for item in db_object.get('tags')]              
            

        if db_object.get('nat-settings'):
            db_object['nat_settings'] = {
                k.replace('-', '_'): v for k, v in db_object['nat-settings'].items()}

        if db_object.get('host-servers'):
            db_object["host_servers"] = {k.replace('-', '_'): (v if k != 'web-server-config' else {k2.replace('-', '_'): v2 for k2, v2 in db_object['host-servers']
                                                                                                   ['web-server-config'].items() if k2 != "standard-port-number"}) for k, v in db_object['host-servers'].items()}
        # format the interfaces field for host objects
        interfaces_ignored_fields = [
            'domain', 'uid', 'icon', 'type', 'tags', 'subnet-mask']
        if db_object.get('interfaces'):
            db_object['interfaces'] = [{k.replace('-', '_'): v for k, v in interface.items(
            ) if k not in interfaces_ignored_fields and v} for interface in db_object['interfaces']]

        # members field is not supported in the Ansible module
        if db_object.get('type') == 'application-site':
            if db_object.get('members'):
                del db_object['members']
                log.info(
                    f"members field is not supported in the Ansible module for {db_object['type']}")

        # format the group-with-exclusion objects
        format_fields = ['include', 'except']
        if db_object['type'] == 'group-with-exclusion':
            for key, value in db_object.items():
                if key in format_fields:
                    db_object[key] = value['name']

        # format access-roles
        if db_object.get('type') == 'access-role':
            fields = [ 'networks', 'users', 'machines', 'remote-access-client' ]
            # workaround to create teh object. Access Role are not yet supported
            for item in fields:
                try:
                 del db_object[item]
                except Exception as e:
                    log.error(e)

            """
            for k, v in db_object.items():
                if k in fields:
                    if type(v) == list:
                        print("ist")
                        db_object[k] = [item['name'] for item in v]
                    elif type(v) == dict:
                        print("dict")
                        print(k, v)
                        for key, value in v.items():
                            if key == 'name':
                                db_object[k] = value
                                
                    # TODO for now only any or all identified is supported (Khalid @ 2021-12-30). fix when API is fixed.
                    # remote-access-client value provided by the API is anot the client names but the allowd client object
                    #if k == 'remote-access-client' or k == 'users':
                    #    db_object[k] = 'all identified'
                    #else:
                    #    db_object[k] = v
            """        

        # format policy packages
        if db_object['type'] == 'package':
            db_object = self.parse_packages(db_object)

        # format group objects to replace members ids with names
        group_types = ['group', 'application-site-group', 'service-group']
        if db_object['type'] in group_types:
            db_object = self.convert_group_member_ids_to_names(db_object)

        # remove dashes from the object field names
        db_object = self.convert_dashes_in_keys(db_object)
        return db_object
        
    def convert_dashes_in_keys(self, obj):
        if obj is not None:
            if type(obj) in [str, int, bool]:
                return obj
            if type(obj) == list:
                return [self.convert_dashes_in_keys(v) for v in obj]
            if type(obj) == dict:
                return {k.replace('-', '_'): self.convert_dashes_in_keys(v) for k, v in obj.items()}
            raise ValueError(f"Unknown type: {obj}")
        return obj

    def parse_packages(self, package):

        db_object = {
            "name": package['name'],
            "type": package['type'],
            "access": package['access'],
            "threat_prevention": package['threat-prevention'],
            "desktop_security": package['desktop-security'],
            "qos": package['qos'],
            "color": package.get('color'),
            "comments": package.get('comments'),
            "installation_targets":  package['installation-targets'] if type(package['installation-targets']) == str else [item['name'] for item in package['installation-targets']],
            "qos_policy_type": package['qos-policy-type'],
            "tags": package['tags'],
            "vpn_traditional_mode": package['vpn-traditional-mode'],
        }

        return db_object

    # delete the fields that are not needed in the Ansible playbook

    def delete_object_fields(self, db_object):
        fields_to_delete = ["uid", "meta-info", "icon",
                            "parent-layer", "read-only", "domain", "mask-length4", 'ips-layer', 'application-id', 'risk', 'user-defined', 'available-actions', 'delayed-sync-value', 'enable-tcp-resource', 'use-delayed-sync', "primary-category-id"]
        
        # delete application-site members
        if db_object['type'] == 'application-site':
            fields_to_delete.append('members')
        
        # if use-default-timeout  is true, we cannot deine the timeout manually under agressive aging
        if db_object['type'] == 'service-tcp':
            if  db_object['aggressive-aging']['use-default-timeout']:
                del db_object['aggressive-aging']['timeout']
        
        return {k: v for k, v in db_object.items() if k not in fields_to_delete}

    # Object type is needed for processing but in the parser bbut must be removed before exporting the object
    def delete_object_type(self, db_object):
        del db_object['type']
        return db_object

    # convert grpup member ids into names:
    def convert_group_member_ids_to_names(self, db_object):
        member_names = []
        for member_uid in db_object['members']:
            member_name = self.client.run_command(
                "show-object", payload={"uid": member_uid})['object']['name']
            log.info(
                f"replacing group member id {member_uid} with name {member_name}")

            member_names.append(member_name)
        db_object['members'] = member_names
        return db_object

    # create the Ansible playbook object

    def create_ansible_module_object(self, cp_ansible_command, db_object):
        try:
            log.info(f"Exporting object: {db_object['name']}, Type: {db_object['name']}")
            command_module = {}
            command_module['name'] = 'Task for ' + db_object['name']
            module_name = 'cp_mgmt_' + cp_ansible_command.replace('-', '_')

            # delete the object type
            self.delete_object_type(db_object)
            command_module[module_name] = db_object
            return command_module
        except Exception as e:
            log.error(f"Error exporting object {db_object['name']}")
            log.error(e)
