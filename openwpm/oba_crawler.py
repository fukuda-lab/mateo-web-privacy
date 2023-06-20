from pathlib import Path
import os
import time
from openwpm.command_sequence import CommandSequence
from openwpm.commands.browser_commands import GetCommand, RecursiveDumpPageSourceCommand
from openwpm.config import BrowserParams, ManagerParams
from openwpm.storage.sql_provider import SQLiteStorageProvider
from openwpm.task_manager import TaskManager
from oba import control_site_visit_sequence, individual_training_visit_sequence, training_visits_sequence, GenericQueries
from typing import List
import json
import sqlite3
import random

EXPERIMENT_NAME = "fashion"
# script_dir = os.path.dirname(os.path.abspath(__file__))

def _task_manager_config(experiment_name: str, save_or_load_profile: str):
    # Loads the default ManagerParams
    # and NUM_BROWSERS copies of the default BrowserParams
    NUM_BROWSERS = 2
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
    
    # Save or Load the browser profile
    experiment_profile_dir = manager_params.data_directory / 'browser_profiles' / f'{experiment_name}'
    if save_or_load_profile == 'save':
        browser_params[1].profile_archive_dir = experiment_profile_dir
    elif save_or_load_profile == 'load':
        browser_params[1].seed_tar = experiment_profile_dir / 'profile.tar.gz'

    return manager_params, browser_params

def experiment_setup(training_sites: List[str], control_sites: List[str], experiment_name: str, manager: TaskManager):
    """
    Sets up the experiment with the given name creating the necessary directories and files. Also run
    the clean_sequence with an independant browser for each control_site to then gather all the contextual and static ads
    
    - Folders: '{experiment_name}/static_ads/' '{experiment_name}/oba_ads/' in 'datadir/sources/'
        # TODO: consider doing it also for 'results'
    - Files: file for profile of the OBA browser, to be able to resume the crawling with the same profile.
             source pages of static ads.
    """
    # Create folders
    os.makedirs(f"./datadir/sources/{experiment_name}", exist_ok=True)
    os.makedirs(f"./datadir/screenshots/{experiment_name}", exist_ok=True)
    os.makedirs(f"./oba/results/{experiment_name}", exist_ok=True)
    
    # Make clean runs
    for control_site in control_sites:
        command_sequence = control_site_visit_sequence(control_site, clean_run=True)
        manager.execute_command_sequence(command_sequence, 0)
        
    # Create browser profile
    # This command sequence needs that the profile_archive_dir is set in the browser parameters. (_task_manager_config)
    browser_creation = individual_training_visit_sequence(random.choice(training_sites), creation=True)
    manager.execute_command_sequence(browser_creation)
    
    print("EXPERIMENT SET UP")

def run_experiment(control_sites: List[str], training_sites:List[str], next_site_rank: int, manager: TaskManager):
    """ Requires experiment_setup() to have been run once. Main function that manages the dices, the control and 
        training sites (shrinking the lists). Calls command sequences functions returned by the oba_command_sequence.py
    """
    
    run_start_time = time.time()
    
    while time.time() - run_start_time < 8 * 60 * 60:
    # For now, for testing only 
    # while time.time() - run_start_time < 30 * 60:
        training_or_control_dice = random.randint(1, 10)
        if training_or_control_dice > 3:
            # TRAINING
            amount_of_pages = random.randint(1, 3)
            # For now, for testing only 
            # amount_of_pages = 1
            training_sample = random.sample(training_sites, amount_of_pages)
            sequence_list = training_visits_sequence(training_sample)
        else:
            # CONTROL
            # If we start having more than one control visit sequence in this list, we must fix next_site_rank
            sequence_list = [control_site_visit_sequence(random.choice(control_sites), next_site_rank)]
        next_site_rank += len(sequence_list)
        for command_sequence in sequence_list:
            manager.execute_command_sequence(command_sequence, 1)
            
def check_and_set_browser_ids(experiment_name: str, manager: TaskManager):
    file_path = f"oba/browsers/{experiment_name}_browser_ids.json"
    # Check if the file exists
    if os.path.isfile(file_path):
        # File exists, load the existing JSON
        with open(file_path, "r") as file:
            data = json.load(file)
    else:
        # File doesn't exist, create a new JSON
        data = {
            "clear": [],
            "oba": [],
        }
    # Append elements to the corresponding lists
    data["clear"].append(manager.browsers[0].browser_id)
    data["oba"].append(manager.browsers[1].browser_id)
    # Save the updated JSON
    with open(file_path, "w") as file:
        json.dump(data, file)
    print("JSON file updated successfully.")
    
def get_amount_of_visits(experiment_name: str):
    sqlite_db_path = f"datadir/{experiment_name}.sqlite"
    # We connect to the sqlite database to know how many site_visits we have (for the site_rank)
    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()
    cursor.execute(GenericQueries.GetAmountOfVisits)
    amount_of_visits = cursor.fetchone()[0]
    return amount_of_visits


def get_search_engines_search_urls(search_terms: List[str]):
    " Given a search_term (separated by '+' in case it is more than one word), returns a list with the 15 search engines' search URL studied using that term "
    training_sites = []
    
    for search_term in search_terms:
        training_sites.append(f"https://www.google.com/search?q={search_term}")
        training_sites.append(f"https://www.bing.com/search?q={search_term}")
        training_sites.append(f"https://search.yahoo.com/search?p={search_term}")
        training_sites.append(f"https://duckduckgo.com/?q={search_term}")
        training_sites.append(f"https://yandex.com/search/?text={search_term}")
        training_sites.append(f"https://www.baidu.com/s?wd={search_term}")
        training_sites.append(f"https://search.naver.com/search.naver?query={search_term}")
        training_sites.append(f"https://search.seznam.cz/?q={search_term}")
        training_sites.append(f"https://www.qwant.com/?q={search_term}")
        training_sites.append(f"https://search.aol.com/aol/search?q={search_term}")
        training_sites.append(f"https://www.ask.com/web?q={search_term}")
        training_sites.append(f"https://www.ecosia.org/search?q={search_term}")
        training_sites.append(f"https://www.startpage.com/do/dsearch?query={search_term}")
        training_sites.append(f"https://www.sogou.com/web?query={search_term}")
        training_sites.append(f"https://swisscows.com/web?query={search_term}")
    return training_sites
    
        


def main_crawl(experiment_name: str, fresh_experiment: bool):
    # Validation
    experiment_browser_profile_path = Path(f"./datadir/browser_profiles/{experiment_name}/profile.tar.gz")
    if fresh_experiment and experiment_browser_profile_path.exists():
        raise FileExistsError("Experiment already exists: {}".format(experiment_browser_profile_path))
    
    # When running with nohup, I don't nee dthis
    # confirm = input(f'Confirm you are going to run experiment "{experiment_name}" as a {"fresh experiment" if fresh_experiment else "resume experiment"}? [y]')
    # if confirm != 'y':
    #     print("Check oba_crawler.py")
    #     return
    
    start_time = time.time()
    
    # Engines that have matches with abp blocklists
    search_terms = ['womens+clothes', '80s+fashion', 'fashion+designing', 'fashion+designer', 'fashion+blog', 'mens+fashion']
    training_sites = get_search_engines_search_urls(search_terms)
    
    # Sites where ads could be captured from
    control_sites = [
        "http://newyorker.com",
        "http://cnn.com",
        "http://bbc.com",
        "http://washingtonpost.com",
        "http://usatoday.com",
    ]
    
    # Load correct params with browser profile directories
    save_or_load_profile = 'save' if fresh_experiment else 'load'
    manager_params, browser_params = _task_manager_config(experiment_name, save_or_load_profile)

    # try:
    # Manager context to start the experiment
    with TaskManager(
        manager_params,
        browser_params,
        SQLiteStorageProvider(Path(f"./datadir/{experiment_name}.sqlite")),
        None,
        experiment_name_for_path=f"{experiment_name}"
    ) as manager:
        
        
        check_and_set_browser_ids(experiment_name, manager)
        
        if fresh_experiment:
            next_site_rank = 1
            experiment_setup(training_sites, control_sites, experiment_name, manager)
        else:
            next_site_rank = get_amount_of_visits(experiment_name) + 1 
        
        run_experiment(control_sites, training_sites, next_site_rank, manager)
                
        # This logs an ERROR
        manager.close()
    
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    print(f"Finished run after {int(minutes)}:{seconds:.2f} minutes")
    with open("finished_8_hours.txt", "w") as f:
        f.write("Hello, World! :)")
            
    # except Exception as e:
    # Write to file that crawling was unsuccessful
    # print(e)
    # elapsed_time = time.time() - start_time
    # minutes, seconds = divmod(elapsed_time, 60)
    # print(f"Error on run after {int(minutes)}:{seconds:.2f} minutes")
    # with open("error_before_8_hours.txt", "w") as f:
    #     f.write("Hello, World! :(")
            
            
main_crawl(EXPERIMENT_NAME, fresh_experiment=False)