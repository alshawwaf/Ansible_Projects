
* Each Playbook is a full example for a Check Point Gaia Ansible Module

> Example inventory (hosts) file:
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

* Notes mainly for macOS Users
- Host machine needs to have sshpass installed
    # brew install hudochenkov/sshpass/sshpass

- if the target machine SSH fingerprint, you will not be able to connect. 
    # add the lines below to the ansible.cfg
  ```
    [defaults]
    host_key_checking = false
  ```
  
- Install the Gaia collection
    # ansible-galaxy collection install check_point.gaia

- Added security on MacOS for restricted multithreading causes this error:
    [WARNING]: Removed restricted key from module data: ansible_facts
    objc[73408]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was called.
    objc[73408]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was called. We cannot safely call it or ignore it in the fork() child process. Crashing instead. Set a breakpoint on objc_initializeAfterForkError to debug.

    #  To fix, Open a terminal:
```
        Running MAC and z-shell and in my .zshrc-file I had to add:
        export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
        and then in the command line:
        source ~/.zshrc
```
