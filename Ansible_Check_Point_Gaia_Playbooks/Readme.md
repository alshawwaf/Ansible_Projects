
* Each Playbook is a full example for a Check Point Gaia Ansible Module

** Example inventory (hosts) file:
```
[checkpoint:children]
mgmt_1
mgmt_2
gw_1
gw_2
gw_3

[mgmt:children]
mgmt_1
mgmt_2

[gw:children]
gw_1
gw_2

[mgmt_1]
203.0.113.120 ansible_user=admin ansible_password=Cpwins!1

[mgmt_2]
203.0.113.125 ansible_user=admin ansible_password=Cpwins!1

[se_1]
203.0.113.124 ansible_user=admin ansible_password=Cpwins!1

[gw_1]
203.0.113.121 ansible_user=admin ansible_password=Cpwins!1

[gw_2]
203.0.113.122 ansible_user=admin ansible_password=Cpwins!1

[gw_3]
203.0.113.144 ansible_user=admin ansible_password=Cpwins!1

[checkpoint:vars]
ansible_httpapi_use_ssl=True
ansible_httpapi_validate_certs=False
ansible_network_os=check_point.gaia.checkpoint
ansible_python_interpreter=/opt/CPsuite-R81.20/fw1/Python/bin/python3.7
```
