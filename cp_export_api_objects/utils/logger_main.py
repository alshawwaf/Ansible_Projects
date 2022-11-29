import logging
from pathlib import Path

try:
    Path(f"check_point_policy/logs").mkdir(parents=True, exist_ok=True)
    print(f"Created the logsfolder")
except Exception as exception:
    print(f"failed to create the logs folder with exception: {exception}")


logging.basicConfig(level=logging.DEBUG, filename='./check_point_policy/logs/export_cp_to_ansible.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
log = logging.getLogger(__name__)
log.addHandler(console)
log.info('Logger created')