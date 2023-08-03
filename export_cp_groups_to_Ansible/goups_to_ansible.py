#!/usr/bin/env python3

"""
Pull the groups and export them to Ansible playbooks 
Install required packages:

python -m pip install PyYAML
python -m pip install cp-mgmt-api-sdk

"""

import sys
import yaml
from cpapi import APIClient, APIClientArgs


def main():
    api_server = "203.0.113.120"
    username = "admin"
    password = "Cpwins!1"
    domain = ""

    client_args = APIClientArgs(server=api_server)
    with APIClient(client_args) as client:
        login = client.login(username, password, domain=domain)
        if not login.success:
            print(login.error_message)
            sys.exit(1)

        ################################
        ### Finding all groups objects ###
        ################################
        groups_list = []
        existing_groups = client.api_call(
            "show-groups", payload={"show-membership": True, "details-level": "full"}
        ).data["objects"]

        # create ansible tasks
        for group in existing_groups:
            # convert members IDS to names
            member_names = []
            member_ids = group.get("members")

            for member_uid in member_ids:
                member_objet = client.api_call(
                    "show-object", payload={"uid": member_uid}
                ).data["object"]
                print(
                    f"replacing group member id {member_uid} with name {member_objet['name']}"
                )
                member_names.append(member_objet["name"])

            # ansible task template
            group_template = {
                "name": f"task for group {group['name']}",
                "check_point.mgmt.cp_mgmt_group": {
                    "name": group.get("name"),
                    "members": member_names,
                    "comments": group.get("comments"),
                    "color": group.get("color"),
                    "tags": [item["name"] for item in group.get("tags")],
                },
            }

            inner_groups = []
            if group.get("groups"):
                [
                    [inner_groups.append(v) for k, v in item.items() if k == "uid"]
                    for item in group["groups"]
                ]
                group_template["check_point.mgmt.cp_mgmt_group"][
                    "groups"
                ] = inner_groups
            groups_list.append(group_template)

        ###########################################
        ###    exporting groups as yaml          ###
        ###########################################

        f = open("cp_groups.yaml", "w")
        f.write(yaml.dump(groups_list, sort_keys=False))
        f.close()

        print("Groups Exported Successfully")


if __name__ == "__main__":
    main()
