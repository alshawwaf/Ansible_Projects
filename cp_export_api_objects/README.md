# Export the Check Point Security Policies, Rules and Objects to Ansible Playbook

This tool can be used to export existing rules and objects using a Check Point management API. 

The Existing resources will be saved in an Ansible Role structure and can be used to recreate the resources with Ansible.



## Install the Requirements

The [requirements.txt](./requirements.txt) has the following packages:

```
beautifulsoup4==4.11.1
certifi==2022.9.24
charset-normalizer==2.1.1
idna==3.4
PyYAML==6.0
requests==2.28.1
soupsieve==2.3.2.post1
urllib3==1.26.12
```

### Install the requirements using you preferred tool

- python -m pip install requirements.txt
  

### Known Limitations


```

Unsupported fields in TCP Services
    - delayed_sync_value, 
    - enable_tcp_resource, 
    - use_delayed_sync

Unsupported fields in cp_mgmt_application_site
    - primary_category_id
    
The objects ['access-role', 'simple-gateway', 'simple-cluster', 'vpn-community-meshed', 'vpn-community-star'] are exported with limited fields.

The API show remote-access-client and ansible expects remote-access-clients plural

Access rules:
    - VPN and content settings are not exported
    - Existing clean up rules are not exported. Default rule is created with layer creation.
        - The commands to show the policy layers do not include the option add_default_rule which is needed since we are getting those rules from the source machine
        - if the policy layer, the ansible code will try to use the set-access-layer command instead of add. This dies not support "add_default_rule".
        - When trying to update the cleanup rule, equals crashes
    - having a rule with the name "Management" will break the ansible code execusion.    
    - If the rules contain updatable objects, make sure your smartconsole on the target management has internet connection and that you opened the updatable objects view which will update the database to make sure the object used in the rule exists on the management. 

        * fatal: [203.0.113.100]: FAILED! => {"changed": false, "msg": "Checkpoint device returned error 404 with message {'code': 'generic_err_object_not_found', 'message': 'Requested object [Office365 Services] not found'} Unpublished changes were discarded"}


Note: if you need to import the tasks in ansible in order, use loop to import the taks and don't import them individually. 

```