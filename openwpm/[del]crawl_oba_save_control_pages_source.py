import argparse
from pathlib import Path

import tranco

from openwpm.command_sequence import CommandSequence
import time
# from openwpm.command_sequence import DumpProfileCommand
from openwpm.command_sequence import ScreenshotFullPageCommand
from openwpm.command_sequence import RecursiveDumpPageSourceCommand
from openwpm.commands.browser_commands import GetCommand
from openwpm.config import BrowserParams, ManagerParams
from openwpm.storage.sql_provider import SQLiteStorageProvider
from openwpm.task_manager import TaskManager

parser = argparse.ArgumentParser()
parser.add_argument("--tranco", action="store_true", default=False),
args = parser.parse_args()

try:
    start_time = time.time()
    search_sites = [
        "https://www.google.com/search?q=cheap+flights+to+madrid",
        # "https://www.bing.com/search?q=cheap+flights+to+madrid",
        "https://search.yahoo.com/search?p=cheap+flights+to+madrid",
        # "https://duckduckgo.com/?q=cheap+flights+to+madrid",
        # "https://yandex.com/search/?text=cheap+flights+to+madrid",
        # "https://www.baidu.com/s?wd=cheap+flights+to+madrid",
        "https://search.naver.com/search.naver?query=cheap+flights+to+madrid",
        "https://search.seznam.cz/?q=cheap+flights+to+madrid",
        # "https://www.qwant.com/?q=cheap+flights+to+madrid",
        # "https://search.aol.com/aol/search?q=cheap+flights+to+madrid",
        "https://www.ask.com/web?q=cheap+flights+to+madrid",
        # "https://www.ecosia.org/search?q=cheap+flights+to+madrid",
        "https://www.startpage.com/do/dsearch?query=cheap+flights+to+madrid",
        "https://www.sogou.com/web?query=cheap+flights+to+madrid",
        # "https://swisscows.com/web?query=cheap+flights+to+madrid",
    ]
    # control_sites = [
    #     # "http://cnn.com",
    #     # "http://bbc.com",
    #     # "http://washingtonpost.com",
    #     "http://reuters.com",
    #     # "http://wsj.com",
    #     "http://npr.org",
    #     # "http://apnews.com",
        # "http://newyorker.com",
    #     "http://cbsnews.com",
    #     "http://usatoday.com",
    # ]
    control_sites = [
        # "http://accuweather.com",
        # "http://wunderground.com",
        "http://myforecast.com",
        "http://newyorker.com",
        "http://cnn.com",
        "http://npr.org",
    ]
    EXPERIMENT_NAME = "flights-mixed-control-experiment"

    # Loads the default ManagerParams
    # and NUM_BROWSERS copies of the default BrowserParams
    NUM_BROWSERS = len(control_sites) + 1
    manager_params = ManagerParams(num_browsers=NUM_BROWSERS)
    browser_params = [BrowserParams(display_mode="headless") for _ in range(NUM_BROWSERS)]

    # Update browser configuration (use this for per-browser settings)
    for browser_param in browser_params:
        # Record HTTP Requests and Responses
        browser_param.http_instrument = True
        # Record cookie changes
        browser_param.cookie_instrument = True
        # Record Navigations
        browser_param.navigation_instrument = True
        # Record JS Web API calls
        browser_param.js_instrument = True
        # Record the callstack of all WebRequests made
        browser_param.callstack_instrument = True
        # Record DNS resolution
        browser_param.dns_instrument = True


    # Update TaskManager configuration (use this for crawl-wide settings)
    manager_params.data_directory = Path("./datadir/")
    manager_params.log_path = Path("./datadir/openwpm.log")

    # memory_watchdog and process_watchdog are useful for large scale cloud crawls.
    # Please refer to docs/Configuration.md#platform-configuration-options for more information
    # manager_params.memory_watchdog = True
    # manager_params.process_watchdog = True


    # Commands time out by default after 60 seconds
    with TaskManager(
        manager_params,
        browser_params,
        # SQLiteStorageProvider(Path("./datadir/crawl-data.sqlite")),
        SQLiteStorageProvider(Path(f"./datadir/{EXPERIMENT_NAME}.sqlite")),
        None,
        experiment_name_for_path=f"{EXPERIMENT_NAME}"
    ) as manager:
        
        # First we run on browser 0 a control_sites control run, to get the non-oba ads for each control_site.
        for control_site in control_sites:
            def control_sites_callback(success: bool, val: str = control_site) -> None:
                print(
                    f"CommandSequence for control run site: {val} ran {'successfully' if success else 'unsuccessfully'}"
                )
            control_sites_command_sequence = CommandSequence(
                control_site,
                # For the way we are looking at the jsons, site_rank will always be 0 as the run to check "non oba" ads
                site_rank=0,
                callback=control_sites_callback
            )
            
            control_sites_command_sequence.append_command(GetCommand(control_site, sleep=10), timeout= 120)
            control_sites_command_sequence.append_command(RecursiveDumpPageSourceCommand("_"), timeout = 120)
            
            manager.execute_command_sequence(control_sites_command_sequence, 0)
            
        
        # Now, in independant browsers (index = c_i + 1) we can do the search engines search to get the OBA happen, and end the browser run with one control_site check
        for c_i, control_site in enumerate(control_sites):
            # We get a copy of the search_sites for each control_page and we append one control_page to the end of the sites to run
            sites = search_sites.copy()
            sites.append(control_site)
            
            for index, site in enumerate(sites):
                def search_sites_callback(success: bool, val: str = site) -> None:
                    print(
                        f"CommandSequence for search run site: {val} ran {'successfully' if success else 'unsuccessfully'}"
                    )
                    
                # Parallelize sites over all number of browsers set above.
                command_sequence = CommandSequence(
                    site,
                    # The run 0 for the corresponding control_site, is the run in the control sites browser (0)
                    site_rank=index + 1,
                    callback=search_sites_callback,
                )
                
                # Wait time should be longer if it is the search_engines to give time for OBA to happen
                sleep_time = 10 if site in control_sites else 120
                command_sequence.append_command(GetCommand(url=site, sleep=sleep_time), timeout=180)
                
                if index == len(sites) - 1:
                    # For the last site (control site)
                    command_sequence.append_command(ScreenshotFullPageCommand("_"), timeout = 120)
                    command_sequence.append_command(RecursiveDumpPageSourceCommand("_"), timeout = 120)
                    
                # We will use a second clear browser to first go to make the searches, wait and then check the ads.
                # As it should be a clear browser for each control_page in the first instance (just to look for OBA),
                # We will need one browser per each control_page used.
                manager.execute_command_sequence(command_sequence, c_i + 1)
                

    # Close the TaskManager after all sites have been visited
    # This logs an ERROR
    manager.close()
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    print(f"Finished run after {int(minutes)}:{seconds:.2f} minutes")
    with open("all_sites_crawling_ok.txt", "w") as f:
        f.write("Hello, World! :)")
        
except:
    # Write to file that crawling was unsuccessful
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    print(f"Error on run after {int(minutes)}:{seconds:.2f} minutes")
    with open("all_sites_crawling_error.txt", "w") as f:
        f.write("Hello, World! :(")