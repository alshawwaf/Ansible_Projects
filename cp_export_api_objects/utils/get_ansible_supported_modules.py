"""
This scrpts will get the ansible supported modules from the official github repository.
The obslolete modules (start with checkpoint_) will be removed from the list.
The output will be a json file under a sub directory called "ansible_supported_modules"
"""
import requests
from bs4 import BeautifulSoup
import json
from .logger_main import log
from .file_ops import read_config_file, write_file


def generate_ansible_supported_modules():
    # read the config file
    config = read_config_file('./config/exporter_config.json')

    url = config.get("cp_ansible_collection_github_url",)
    response = requests.get(url)
    html = response.text

    soup = BeautifulSoup(html, 'html.parser')
    module_div = soup.find_all('code')
    modules = []
    for link in module_div:
        if 'cp_mgmt_' in link.text and '\n' not in link.text and '.' not in link.text and '*' not in link.text and '_facts' not in link.text:
            modules.append(link.text)
    content=json.dumps(modules)
    write_file("./config/supported_ansible_modules.json", mode='w', content=content)

   