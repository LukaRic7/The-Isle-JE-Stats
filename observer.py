import requests, json, sys, os, time
from collections import deque
from bs4 import BeautifulSoup
import loggerric as lr

class Config:
    """
    **Read/Write to a JSON file, compilation safe.**
    
    *Methods*:
    - `read() -> dict`: Read the file.
    - `write(data) -> None`: Write to the file.
    """

    def __init__(self, path:str):
        """
        **Initializer.**
        
        *Parameters*:
        - `path` (str): Path to the file.
        """

        # Check if the script is compiled
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            exe_dir   = os.path.dirname(sys.executable)
            self.path = os.path.join(exe_dir, path)
        # Script is not compiled
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.path  = os.path.join(script_dir, path)

    def read(self) -> dict:
        """
        **Read contents of the file.**
        
        *Returns*:
        - (dict): The parsed file content.
        """

        with open(self.path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def write(self, data:dict):
        """
        **Write data to the file.**
        
        *Parameters*:
        - `data` (dict): The data to be written.
        """

        with open(self.path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)

class Client:
    """
    **Communicate with a web endpoint.**
    
    Passes cookies and user agent in the headers.
    
    *Methods*:
    - `fetch(path) -> BeautifulSoup`: Parsed HTML response from the endpoint.
    """

    def __init__(self, base_url:str, cookie:str, user_agent:str):
        """
        **Initializer.**
        
        *Parameters*:
        - `base_url` (str): Base URL of domain.
        - `cookie` (str): Cookie to pass in the headers.
        - `user_agent` (str): User agent to pass in the headers.
        """

        self.base_url = base_url
        self.headers  = { 'User-Agent': user_agent, 'Cookie': cookie }

        lr.Log.info('Initialized fetching client!')

    def fetch(self, path:str='') -> BeautifulSoup:
        """
        **Fetch from the endpoint.**
        
        *Parameters*:
        - `path` (str): URL path after the base URL.
        
        *Returns*:
        - (BeautifulSoup): Parsed HTML response from the endpoint.
        """

        url = self.base_url + path

        # Fetch URL
        response = requests.get(url, headers=self.headers)
        status = response.status_code
        reason = response.reason

        # URL did not return OK
        if not response.ok:
            lr.Log.error('"{}" Failed! [{}]: {}'.format(url, status, reason))
            return

        lr.Log.debug('"{}" Succeeded! [{}]: {}'.format(url, status, reason))

        return BeautifulSoup(response.text, 'lxml')

class Observer:
    """
    **Observes webpage data, parses it and writes to an output file.**
    
    Repeatedly requests new data from the URL endpoint, then parses it
    calculating deltas and time estimations in the process, writing it all
    to an output JSON file.
    
    *Methods*:
    - `record(info) -> None`: Add information to the history.
    - `calculate_deltas() -> dict`: Calculate delta values from history.
    - `estimate_time_to_target(info, deltas) -> dict`: Calculate EST minutes
    until the target value is hit.
    - `extract_info(soup) -> dict`: Extract information from parsed HTML soup.
    - `mainloop() -> None`: Enter the mainloop, uses while true.
    """

    def __init__(self):
        """
        **Initializer.**
        """

        config_data = Config('./fetching.json').read()

        self.ConfigOut = Config('./output.json')
        
        self.Client = Client(
            base_url=config_data.get('url'),
            cookie=config_data.get('cookie'),
            user_agent=config_data.get('user-agent')
        )

        self.FETCH_INTERVAL = 10

        self.history = deque(maxlen=(5*60) // self.FETCH_INTERVAL)
    
    def record(self, info:dict):
        """
        **Add information to the history.**
        
        *Parameters*:
        - `info` (dict): Information to be added.
        """

        self.history.append({ 'time': time.time(), 'info': info })
    
    def calculate_deltas(self) -> dict:
        """
        **Calculate delta values from history.**
        
        *Returns*:
        - (dict): Calculated deltas.
        """

        # Ensure more than 2 datapoints
        if len(self.history) < 2: return

        first = self.history[0]
        last  = self.history[-1]

        # Ensure theres a non-zero delta time
        delta_time_s = last['time'] - first['time']
        if delta_time_s == 0: return

        # Calculate the delta
        deltas = {}
        for key in last['info']:
            change      = last['info'][key] - first['info'].get(key, 0)
            deltas[key] = change / (delta_time_s / 60)
        
        return deltas

    def estimate_time_to_target(self, info:dict, deltas:dict) -> dict:
        """
        **Calculate EST minutes until the target value is hit.**
        
        *Parameters*:
        - `info` (dict): Freshly fetched information.
        - `deltas` (dict): Calculated deltas from history.
        
        *Returns*:
        - (dict): EST minutes until targets are reached.
        """

        # Define lookup table from keys to targets
        TARGETS = { 'Growth': 1.0, 'Health': 1.0, 'Hunger': 0.0, 'Thirst': 0.0 }

        # Iterate targets
        estimates = {}
        for key, target in TARGETS.items():
            # Ensure the key exists in deltas
            if key not in info or key not in deltas: continue

            delta   = deltas[key]
            current = info[key]

            # Ensure the delta is non-zero to avoid zero division error
            if delta == 0:
                estimates[key] = 0
            else:
                # Calculate estimated target and ensure positive number
                time_to_target = (target - current) / delta
                estimates[key] = max(0, time_to_target)
        
        # If no estimates, return None instead of empty dict
        return estimates if len(estimates) > 0 else None

    def extract_info(self, soup:BeautifulSoup) -> dict:
        """
        **Extract information from parsed HTML soup.**
        
        *Parameters*:
        - `soup` (BeautifulSoup): Parsed HTML to extract from.
        
        *Returns*:
        - (dict): Extracted information.
        """

        # Grab the div that holds the information
        ingame_info = soup.find(
            name='div',
            class_='grid grid-cols-1 md:grid-cols-2 gap-5'
        )

        # Iterate the div's children
        extracted_info = {}
        for row in ingame_info.children:
            # Extract the rows label and percent, both HTML
            label = row.find_next(
                name='div',
                class_='text-xs uppercase tracking-wide text-gray-300/80'
            )
            percent = row.find_next(
                name='div',
                class_='mt-1 text-base font-medium'
            )

            VALID = ['Growth', 'Health', 'Hunger', 'Thirst']

            # Only grab valid results
            if label and percent and label.text in VALID:
                # Extract the percentage and format it
                pct = float(percent.text[0:-1]) / 100
                extracted_info[label.text] = pct

        return extracted_info

    def mainloop(self):
        """
        **Enter the mainloop, uses while true.**
        """

        # Infinite loop!
        while True:
            # Ensure the server is not spammed, and CPU is not wasted
            time.sleep(self.FETCH_INTERVAL)

            # Ensure the fetch was valid
            soup = self.Client.fetch('player')
            if not soup: continue

            # Extract info and record it
            info = self.extract_info(soup)
            self.record(info)

            lr.Log.debug(f'Captured data: {info}')

            deltas    = self.calculate_deltas()
            estimates = self.estimate_time_to_target(info, deltas or {})

            # Write to the output file
            self.ConfigOut.write({
                'current': info,
                'delta_per_min': deltas,
                'est_time_min': estimates
            })

def main():
    """
    **Main entrypoint.**
    """

    # Set the timestamp format
    lr.Timestamp.set_format('{HH}:{MI}:{SS} T+{DM}:{DS}')

    # Perform mainloop in try catch
    try:
        observer = Observer()
        observer.mainloop()
    # Catch user exiting, don't throw error
    except KeyboardInterrupt:
        lr.Log.info('User interrupted, qutting!')
        exit()
    # Catch unexpected errors
    except Exception as e:
        lr.Log.error(f'Unknown exception occurred: {e}')

# Ensure script is not being imported
if __name__ == '__main__':
    main()