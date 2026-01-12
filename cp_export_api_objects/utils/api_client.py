import requests
requests.packages.urllib3.disable_warnings() # Disable warning messages since our API certificate is self signed
from .logger_main import log


class API_client:

    api_server: str
    api_server_url: str
    user: str
    password: str
    domain: str
    policy_layer: str

    def __init__(self, api_server: str, user: str, password: str, domain=None, api_key=None ) -> None:
        self.user = user
        self.password = password
        self.api_key = api_key
        self.domain = domain if domain else None
        self.headers = {'Content-Type': 'application/json'}
        self.api_server_url = f"https://{api_server}/web_api/"
        
    # Create login instance    
    def login(self) -> None:
        
        payload = {"user": self.user, "password": self.password}
        if self.domain is not None:
            payload['domain'] = self.domain
        if self.api_key is not None:
            payload['api-key'] = self.api_key
            del payload['user']
            del payload['password'] 
             
        login_response = requests.request("POST", self.api_server_url + "login", headers=self.headers, json=payload, verify=False)

        if login_response.status_code != 200:
            log.critical(f"Login failed:{login_response.text}")
            exit(1)
        else:
            sid = login_response.json()['sid']
            self.headers['X-chkp-sid'] = sid
            log.info(f"Login successful, SID: {sid}")
            return sid

    def logout(self) -> None:
        logout_response = requests.request(
            "POST", self.api_server_url + "logout", headers=self.headers, json={}, verify=False)
        if logout_response.status_code != 200:
            log.critical(f"Logout failed:{logout_response.text}")
            exit(1)
        else:
            log.info(f"Logout successful")
            return


    def publish(self) -> None:
        # Create publish instance
        payload = {}
        publish_response = requests.request(
            "POST", self.api_server_url + "publish", headers=self.headers, json=payload, verify=False)
        log.info(f"Publish response: {publish_response}")
        return

    def run_command(self, command: str, payload: dict) -> None:
        # Create run command instance
        run_command_response = requests.request(
            "POST", self.api_server_url + command, headers=self.headers, json=payload, verify=False)
        #log.info(f"Run command response: {run_command_response.text}")
        return run_command_response.json()
