"""
This file is a modified version of the openwpm demo.py.
It is used to crawl the top 15 search engines for the query "JELLYBEANS" and store the results in a SQLite database:
"""

from pathlib import Path
from custom_command import LinkCountingCommand
from openwpm.command_sequence import CommandSequence
from openwpm.commands.browser_commands import GetCommand
from openwpm.config import BrowserParams, ManagerParams
from openwpm.storage.sql_provider import SQLiteStorageProvider
from openwpm.task_manager import TaskManager
import time

def jellybeans_crawl(num_runs):
    start_time = time.time()
    
    for i in range(1, num_runs + 1):
        print(f'Starting run {i}...')
        sites = [
            "https://www.google.com/search?q=JELLYBEANS",
            "https://www.bing.com/search?q=JELLYBEANS",
            "https://search.yahoo.com/search?p=JELLYBEANS",
            "https://duckduckgo.com/?q=JELLYBEANS",
            "https://yandex.com/search/?text=JELLYBEANS",
            "https://www.baidu.com/s?wd=JELLYBEANS",
            "https://search.naver.com/search.naver?query=JELLYBEANS",
            "https://search.seznam.cz/?q=JELLYBEANS",
            "https://www.qwant.com/?q=JELLYBEANS",
            "https://search.aol.com/aol/search?q=JELLYBEANS",
            "https://www.ask.com/web?q=JELLYBEANS",
            "https://www.ecosia.org/search?q=JELLYBEANS",
            "https://www.startpage.com/do/dsearch?query=JELLYBEANS",
            "https://www.sogou.com/web?query=JELLYBEANS",
            "https://swisscows.com/web?query=JELLYBEANS",
        ]
        # Loads the default ManagerParams
        # and NUM_BROWSERS copies of the default BrowserParams
        NUM_BROWSERS = 1
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

        # browser_params[1].blocklists = ["easylist_general_block.txt"]

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
            # Not sure if this will work correctly, but ideally this should save the .sqlite file to the experiment directory
            SQLiteStorageProvider(Path("./datadir/[vpn_czech]10_crawls_results.sqlite")),
            # SQLiteStorageProvider(Path("./datadir/[vpn_chile]jellybeans_10_crawls.sqlite")),
            None,
        ) as manager:
            # Visits the sites
            for index, site in enumerate(sites):

                def callback(success: bool, val: str = site) -> None:
                    print(
                        f"CommandSequence for {val} ran"
                        f" {'successfully' if success else 'unsuccessfully'}"
                    )

                # Parallelize sites over all number of browsers set above.
                command_sequence = CommandSequence(
                    site,
                    site_rank=index,
                    callback=callback,
                )

                # Start by visiting the page
                command_sequence.append_command(GetCommand(url=site, sleep=3), timeout=100)
                # Have a look at custom_command.py to see how to implement your own command
                command_sequence.append_command(LinkCountingCommand())

                # Run commands across all browsers (simple parallelization)
                manager.execute_command_sequence(command_sequence)
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        print(f"Finished run {i} after {int(minutes)}:{seconds:.2f} minutes")

try:
    jellybeans_crawl(10)
    # Write to file that crawling was successful
    with open("vpn_crawling_ok.txt", "w") as f:
        f.write("Hello, World!")

except:
    # Write to file that crawling was unsuccessful
    with open("vpn_crawling_error.txt", "w") as f:
        f.write("Hello, World!")