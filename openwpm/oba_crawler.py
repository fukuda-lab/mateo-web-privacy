import json
import os
import random
import signal
import sqlite3
import sys
import time
from pathlib import Path

from bannerclick.config import *
from oba import (
    GenericQueries,
    control_site_visit_sequence,
    individual_training_visit_sequence,
    training_visits_sequence,
)
from oba.enums import IAB_CATEGORIES
from oba.training_pages_handler import TrainingPagesHandler
from openwpm.config import BrowserParams, ManagerParams
from openwpm.storage.sql_provider import SQLiteStorageProvider
from openwpm.task_manager import TaskManager

# from bannerclick.config import WATCHDOG, OFFSET_ACCEPT, OFFSET_REJECT

# COMMAND: nohup python oba_crawler.py > {experiment_name}.log 2>&1 &
# COMMAND: nohup python oba_crawler.py > logs/fashion_uk_accept_cookies.log 2>&1 &

LATEST_CATEGORIZED_TRANCO_LIST_ID = "N7WQWCOPY"
DEFAULT_N_PAGES = 5000

# TODO: implement init with prints


class OBAMeasurementExperiment:
    def __init__(
        self,
        experiment_name: str,
        fresh_experiment: bool,
        use_custom_pages: bool = False,
        # 0 do nothing, 1 accept, 2 reject
        cookie_banner_action: int = 0,
        tranco_pages_params: dict[str, str] = None,
        custom_pages_params: dict[str, str] = None,
        webshrinker_credentials: dict[str, str] = None,
    ):

        self.start_time = time.time()

        # Setup transversal values
        if fresh_experiment and not use_custom_pages and not tranco_pages_params:
            # default case for tranco_pages_params
            tranco_pages_params = {
                "updated": False,
            }
        self.experiment_name = experiment_name
        self.data_dir = f"./datadir/{self.experiment_name}/"
        self.fresh_experiment = fresh_experiment
        self.use_custom_pages = use_custom_pages
        self.cookie_banner_action = cookie_banner_action

        # Sites where ads could be captured from
        # TODO: provide the option of a custom_list of control_pages
        self.control_pages = [
            # "http://www.accuweather.com/",
            # "http://www.wunderground.com/",
            # "http://www.localconditions.com/",
            "http://myforecast.com/",
            "http://www.weatherbase.com/",
            # "http://cnn.com",
            # "http://usatoday.com",
            # # "http://accuweather.com",
            # # "http://wunderground.com",
            # # "http://myforecast.com",
            # "http://cbsnews.com",
            # "http://apnews.com",
            # "http://reuters.com"
            "https://www.theweathernetwork.com/",
            "https://weather.com/",
            "https://www.weather2umbrella.com/",
        ]

        # Browser profile validation
        experiment_browser_profile_path = Path(self.data_dir + "browser_profile.tar.gz")
        if fresh_experiment and experiment_browser_profile_path.exists():
            raise FileExistsError(
                "Experiment already exists: {}. Delete the tar.".format(
                    experiment_browser_profile_path
                )
            )

        if fresh_experiment:
            if use_custom_pages and not custom_pages_params:
                raise ValueError(
                    "When using custom training pages, values for the custom_pages_params argument must be included"
                )

            if (not use_custom_pages and tranco_pages_params["updated"]) or (
                use_custom_pages and custom_pages_params["categorize_pages"]
            ):
                if not webshrinker_credentials:
                    raise ValueError(
                        "Since categorization is necessary, valid WebShrinker API_KEY and SECRET_KEY are needed"
                    )

            # Get training pages to be used
            if use_custom_pages:
                if not custom_pages_params["custom_pages_list"]:
                    raise ValueError("Value for custom_pages_list invalid")

                if custom_pages_params["categorize_pages"]:
                    # Case categorization is needed before using
                    self.training_pages_handler = TrainingPagesHandler(
                        list_id=experiment_name,
                        categorize=True,
                        webshrinker_credentials=webshrinker_credentials,
                        custom_list=True,
                        custom_pages_list=custom_pages_params["custom_pages_list"],
                    )
                    # TODO: Add taxonomy and request_rate parameters.
                    print(
                        "Starting page categorization... this could take several minutes"
                    )
                    self.training_pages_handler.categorize_training_pages()
                    self.pages_categorized = True
                    self.training_pages = None

                else:
                    # Case categorization not needed with custom_pages
                    self.training_pages_handler = None
                    self.pages_categorized = False
                    self.training_pages = custom_pages_params["custom_pages_list"]

            else:
                if tranco_pages_params["updated"]:
                    # Case new pages must be retrieved and categorized
                    # TODO: print that in case of unhandled error or cut of the runtime, the categorization would resume from the stopping point
                    # No list_id since it will have updated=True
                    self.training_pages_handler = TrainingPagesHandler(
                        updated_tranco=True,
                        categorize=True,
                        webshrinker_credentials=webshrinker_credentials,
                        n_pages=tranco_pages_params["size"]
                        if "size" in tranco_pages_params.keys()
                        and tranco_pages_params["size"]
                        else DEFAULT_N_PAGES,
                    )
                    print(
                        "Starting page categorization... this could take several minutes"
                    )
                    self.training_pages_handler.categorize_training_pages()
                    self.pages_categorized = True
                    self.training_pages = None

                else:
                    # Case cached pages already categorized are used
                    # The size of the training pages cannot be managed by the framework since it would break the name of the db, so the user is expected to handle the size of the list at his will after returned, the list will be ordered by descending rank in the tranco ranking.
                    self.training_pages_handler = TrainingPagesHandler(
                        LATEST_CATEGORIZED_TRANCO_LIST_ID
                    )
                    print("Training pages already categorized")
                    self.pages_categorized = True
                    self.training_pages = None
            # for _task_manager_config
            save_or_load_profile = "save"
            print("Remember to set the training pages accordingly")
        else:
            # Case fresh_experiment == False
            # Load everything according to the {experiment_name}_config.json
            save_or_load_profile = "load"
            # TODO: Uncomment this and delete the one above
            experiment_json = self._read_experiment_config_json()
            self.pages_categorized = experiment_json["pages_categorized"]
            self.training_pages = experiment_json[
                "custom_pages_list"
            ]  # Reads None if doesn't use a custom_pages_list with categorization==False
            self.training_pages_handler = (
                TrainingPagesHandler(
                    list_id=experiment_json["training_pages_id"],
                    webshrinker_credentials=webshrinker_credentials,
                    n_pages=experiment_json["n_pages"],
                )
                if experiment_json["training_pages_id"]
                else None
            )

        # Create or connect browser profile
        self.NUM_BROWSERS = 2
        self.manager_params, self.browser_params = self._task_manager_config(
            save_or_load_profile
        )

        # Catch Signals
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def set_training_pages_by_category(self, category: str = ""):
        """ Sets the training pages for the experiment according to the category given. If no category is given, the user is prompted to pick one from the supported categories."""
        if not self.pages_categorized:
            # Case for custom_pages_list that was not categorized
            raise RuntimeError(
                "Pages must be categorized before setting training pages by category"
            )

        # TODO: extend supported_categories to every category and to webshrinker taxonomy
        supported_categories = []
        for iabv1_dict in IAB_CATEGORIES.values():
            for supported_category in iabv1_dict.values():
                supported_categories.append(supported_category)
        # supported_categories = [IAB_CATEGORIES[key][key] for key in IAB_CATEGORIES.keys()]
        if not category:
            category = input(f"Pick a category from {supported_categories} \n")
            while category not in supported_categories:
                category = input(
                    f"Invalid category, pick a category from {supported_categories} \n"
                )
        if category not in supported_categories:
            raise ValueError(f'Category "{category}" is not supported')

        # TODO: extend taxonomy
        self.training_pages = (
            self.training_pages_handler.get_training_pages_by_category(
                category, taxonomy_type="iabv1"
            )
        )
        print(f"Training pages set from {category}")
        return
    
    # TODO: add browser_mode as an experiment_config
    def start(self, hours: int = 0, minutes: int = 0, browser_mode = "headless"):
        """Main method of the class to run the experiment"""

        def get_amount_of_visits():
            """Get the amount of visits done to be used for the site_rank column of the site_visits table to keep chronological order of them (mainly for control_pages order)"""
            sqlite_db_path = self.data_dir + "crawl-data.sqlite"
            # We connect to the sqlite database to know how many site_visits we have (for the site_rank)
            conn = sqlite3.connect(sqlite_db_path)
            cursor = conn.cursor()
            cursor.execute(GenericQueries.GetAmountOfVisits)
            amount_of_visits = cursor.fetchone()[0]
            return amount_of_visits

        def fresh_experiment_setup_and_clean_run(manager: TaskManager):
            # TODO: separate in two functions, one for dirs setup and other for clean_run?
            """
            Sets up the experiment with the given name creating the necessary directories and files. Also run
            the clean_sequence with an independant browser for each control_site to then gather all the contextual and static ads

            - Folders: '{experiment_name}/static_ads/' '{experiment_name}/oba_ads/' in 'datadir/'
                # TODO: consider doing it also for 'results'
            - Files: file for profile of the OBA browser, to be able to resume the crawling with the same profile.
                    source pages of static ads.
            """

            # Create folders
            os.makedirs(self.data_dir + "sources", exist_ok=True)
            os.makedirs(self.data_dir + "screenshots", exist_ok=True)
            os.makedirs(
                self.data_dir + f"results/{self.experiment_name}", exist_ok=True
            )

            # Make clean runs
            # TODO: make it so the crawling can be run without the clean runs for easier testing when developing
            for control_site in self.control_pages:
                command_sequence = control_site_visit_sequence(
                    control_site, clean_run=True
                )
                manager.execute_command_sequence(command_sequence, 0)
            # JUST FOR TESTING, ONLY 1 CONTROL VISIT RUN
            # command_sequence = control_site_visit_sequence(self.control_pages[0], clean_run=True)
            manager.execute_command_sequence(command_sequence, 0)

            # Create browser profile
            # This command sequence needs that the profile_archive_dir is set in the browser parameters. (_task_manager_config)
            browser_creation = individual_training_visit_sequence(
                random.choice(self.training_pages), creation=True
            )
            manager.execute_command_sequence(browser_creation)

            print("EXPERIMENT DIRECTORIES SET UP")

        def get_and_create_experiment_config_json(manager: TaskManager):
            """Manages the file that saves the browser_id's used throughout the experiment for them to be used later in the data analysis (i.e know which browser_ids belong to oba browsers and which belongs to clear browsers)"""
            file_path = self.data_dir + f"{self.experiment_name}_config.json"
            try:
                experiment_json = self._read_experiment_config_json()
            except FileNotFoundError:
                # File doesn't exist, create a new JSON
                experiment_json = {
                    "experiment_name": self.experiment_name,
                    "pages_categorized": self.pages_categorized,  # If False, we use the custom_pages_list in stead of a TrainingPagesHandler with the 'training_pages_id' when loading
                    # Having self.training_pages_handler=None means that we are using custom_pages_list without categorization so it's the value for the boolean above when it corresponds
                    "custom_pages_list": self.training_pages
                    if not self.training_pages_handler
                    else [],
                    "training_pages_id": self.training_pages_handler.list_id
                    if self.training_pages_handler
                    else None,
                    # 0 do nothing, 1 accept, 2 reject
                    "cookie_banner_action": self.cookie_banner_action,
                    # Important only when using tranco
                    "n_pages": self.training_pages_handler.n_pages
                    if self.training_pages_handler
                    else None,
                    "browser_ids": {"oba": [], "clear": []},
                }
            # Append elements to the corresponding lists
            experiment_json["browser_ids"]["clear"].append(
                manager.browsers[0].browser_id
            )
            experiment_json["browser_ids"]["oba"].append(manager.browsers[1].browser_id)

            # Save the updated JSON
            with open(file_path, "w") as file:
                json.dump(experiment_json, file)
            print("JSON file updated successfully.")

        if not self.training_pages:
            raise RuntimeError("Experiment missing training_pages")

        try:
            # Manager context to start the experiment
            with TaskManager(
                self.manager_params,
                self.browser_params,
                SQLiteStorageProvider(Path(self.data_dir + "crawl-data.sqlite")),
                None,
            ) as manager:

                get_and_create_experiment_config_json(manager)

                if self.fresh_experiment:
                    next_site_rank = 1
                    fresh_experiment_setup_and_clean_run(manager)
                else:
                    next_site_rank = get_amount_of_visits() + 1

                print("Launching OBA Crawler... \n")
                self.experiment_crawling(next_site_rank, manager, hours, minutes)

                # This logs an ERROR
                manager.close()

            successful_run_message = f"Successful run finished after "
            self._write_cleanup_message(successful_run_message)
        except:
            # TODO: Implement that if error is caught and the crawling has been running for long, save the profile before closing to not lose the data saved in SQLite of that run
            error_run_message = f"Error during run after "
            self._write_cleanup_message(error_run_message)

    @staticmethod
    def signal_handler(sig, frame):
        # Access the instance via the frame's local variables
        instance = frame.f_locals["self"]
        instance.signal_cleanup()
        sys.exit(0)

    def _write_cleanup_message(self, log_message_phrase):
        """ Private method to be called when the experiment is terminated writing the runtime to the runtime_log.txt file """
        runtime_seconds = time.time() - self.start_time
        hours, remainder = divmod(runtime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        runtime_string = f"{int(hours)}:{int(minutes)}:{int(seconds)}"
        log_message = f"{log_message_phrase} {runtime_string}.\n"
        with open(self.data_dir + "runtime_log.txt", "a") as f:
            f.write(log_message)

    def signal_cleanup(self):
        log_message = f"Terminating signal received after "
        self._write_cleanup_message(log_message)
        print("Runtime logfile updated.")

    def _task_manager_config(
        self, save_or_load_profile: str, browser_display_mode="headless"
    ):
        """Builds the browser_params and manager_params according to the configuration to be used either to load an existing profile or save a new one."""
        # Loads the default ManagerParams
        # and NUM_BROWSERS copies of the default BrowserParams
        manager_params = ManagerParams(num_browsers=self.NUM_BROWSERS)
        browsers_params = [
            BrowserParams(display_mode=browser_display_mode)
            for _ in range(self.NUM_BROWSERS)
        ]

        # Update browser configuration (use this for per-browser settings)
        for browser_params in browsers_params:
            # Record HTTP Requests and Responses
            browser_params.http_instrument = False
            # Record cookie changes
            browser_params.cookie_instrument = False
            # Record Navigations
            browser_params.navigation_instrument = True
            # Record JS Web API calls
            browser_params.js_instrument = False
            # Record the callstack of all WebRequests made
            browser_params.callstack_instrument = False
            # Record DNS resolution
            browser_params.dns_instrument = False

            browser_params.bot_mitigation = True

        # Update TaskManager configuration (use this for crawl-wide settings)
        manager_params.data_directory = Path(self.data_dir)
        manager_params.log_path = Path(self.data_dir + "openwpm.log")

        manager_params.memory_watchdog = WATCHDOG
        manager_params.process_watchdog = WATCHDOG

        # Allow for many consecutive failures
        # The default is 2 x the number of browsers plus 10 (2x20+10 = 50)
        manager_params.failure_limit = 100000

        # Save or Load the browser profile
        experiment_profile_dir = manager_params.data_directory
        if save_or_load_profile == "save":
            browsers_params[1].profile_archive_dir = experiment_profile_dir
        elif save_or_load_profile == "load":
            browsers_params[1].seed_tar = experiment_profile_dir / "profile.tar.gz"

        return manager_params, browsers_params

    def experiment_crawling(
        self, next_site_rank: int, manager: TaskManager, hours: int, minutes: int = 0
    ):
        """Requires fresh_experiment_setup_and_clean_run() to have been run once. Main function that manages the dices, the control and
        training sites (shrinking the lists). Calls command sequences functions returned by the oba_command_sequence.py
        """

        # Start with one second ahead
        run_start_time = time.time() + 1

        _hours_in_seconds = 60 * 60
        _minutes_in_seconds = 60

        hours = hours * _hours_in_seconds
        minutes = minutes * _minutes_in_seconds
        while time.time() - run_start_time < hours + minutes:
            print(f"TIME ELAPSED: {time.time() - run_start_time}")
            training_or_control_dice = random.randint(1, 10)
            if training_or_control_dice > 2:
                # TESTING
                # if False:
                # TRAINING
                amount_of_pages = random.randint(1, 3)
                training_sample = random.sample(self.training_pages, amount_of_pages)
                sequence_list = training_visits_sequence(
                    training_sample,
                    next_site_rank,
                    cookie_banner_action=self.cookie_banner_action,
                )
            else:
                # CONTROL
                # If we start having more than one control visit sequence in this list, we must fix next_site_rank
                sequence_list = [
                    control_site_visit_sequence(
                        random.choice(self.control_pages),
                        next_site_rank,
                        cookie_banner_action=self.cookie_banner_action,
                    )
                ]
            next_site_rank += len(sequence_list)
            for command_sequence in sequence_list:
                manager.execute_command_sequence(command_sequence, 1)

    def _read_experiment_config_json(self):
        """Opens and reads the json file with the configuration for the experiment"""
        file_path = self.data_dir + f"{self.experiment_name}_config.json"
        # Check if the file exists
        if os.path.isfile(file_path):
            # File exists, load the existing JSON
            with open(file_path, "r") as file:
                experiment_json = json.load(file)
            return experiment_json
        else:
            raise FileNotFoundError(
                f"Trying to read file in relative path {file_path} which does not exist."
            )




# # TODO: create a folder to add the logs that are saved whenever nohup is run with filename {exp_name}.log
