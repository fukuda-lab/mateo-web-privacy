import json
import os
import random
import signal
import sqlite3
import sys
import time
from pathlib import Path
from typing import Literal, TypedDict

from bannerclick.config import *
from oba.enums import (
    IAB_CATEGORIES,
    CustomPagesParams,
    GenericQueries,
    TrancoPagesParams,
)
from oba.oba_commands_sequences import (
    control_site_visit_sequence,
    get_cookie_banner_visit_sequences,
    individual_training_visit_sequence,
    training_visits_sequence,
)
from oba.training_pages_handler import TrainingPagesHandler
from openwpm.config import BrowserParams, ManagerParams
from openwpm.storage.sql_provider import SQLiteStorageProvider
from openwpm.task_manager import TaskManager

# from bannerclick.config import WATCHDOG, OFFSET_ACCEPT, OFFSET_REJECT

# COMMAND: nohup python oba_crawler.py > {experiment_name}.log 2>&1 &
# COMMAND: nohup python oba_crawler.py > logs/fashion_uk_accept_cookies.log 2>&1 &

LATEST_CATEGORIZED_TRANCO_LIST_ID = "V929N"
DEFAULT_N_PAGES = 10000
# LATEST_CATEGORIZED_TRANCO_LIST_ID = "N7WQW" #Previous
# DEFAULT_N_PAGES = 5000 # Previous

# TODO: init with prints?
class OBAMeasurementExperiment:
    def __init__(
        self,
        experiment_name: str,
        fresh_experiment: bool,
        use_custom_pages: bool = False,
        # 0 do nothing, 1 accept, 2 reject
        cookie_banner_action: Literal[0, 1, 2] = 0,
        tranco_pages_params: TrancoPagesParams = None,
        custom_pages_params: CustomPagesParams = None,
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
        self.banner_results_filename = f"./datadir/cookie_banner_results.csv"

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
        if fresh_experiment and Path(self.data_dir).exists():
            raise FileExistsError(
                f"Experiment with that name already exists. Try a different name or delete the experiment folder in datadir/{experiment_name}"
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
            self.cookie_banner_action = experiment_json["cookie_banner_action"]
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
        if fresh_experiment and self.cookie_banner_action == 2:
            # If we are going to reject cookies, we need to use native mode for the experiment creation run to reject the cookies manually
            browser_display_mode = "native"
        else:
            browser_display_mode = "headless"

        self.manager_params, self.browser_params = self._task_manager_config(
            save_or_load_profile,
            browser_display_mode=browser_display_mode,
        )

        # Catch Signals
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def set_training_pages_by_category(self, category: str = ""):
        """Sets the training pages for the experiment according to the category given. If no category is given, the user is prompted to pick one from the supported categories."""
        if not self.pages_categorized:
            # Case for custom_pages_list that was not categorized
            raise RuntimeError(
                "Pages must be categorized before setting training pages by category"
            )

        # TODO: extend supported_categories to every category and to webshrinker taxonomy
        supported_categories = []
        tier_1_categories = []
        tier_2_categories = []
        for iabv1_tier_1_key_value in IAB_CATEGORIES.items():
            # look at IAB_CATEGORIES to understand this
            tier_1_category_key = iabv1_tier_1_key_value[0]
            tier_1_category_dict = iabv1_tier_1_key_value[1]
            tier_1_categories.append(tier_1_category_dict[tier_1_category_key])
            for supported_category in tier_1_category_dict.values():
                supported_categories.append(supported_category)
                if supported_category not in tier_1_categories:
                    tier_2_categories.append(supported_category)
        # supported_categories = [IAB_CATEGORIES[key][key] for key in IAB_CATEGORIES.keys()]
        if not category or category not in supported_categories:
            category_input_message = (
                f"Pick a category from the supported categories: \n \n"
                f"Tier 1 categories (general categories, which are more likely to have been confidently assigned to the pages and have more pages assigned to them): \n\n{tier_1_categories} \n \n"
                f"Tier 2 categories (more specific categories, set to a page only after it was set with a tier 1 category): \n\n{tier_2_categories})\n"
            )
            category = input(category_input_message)
            while category not in supported_categories:
                category = input(f"Invalid category. \n" + category_input_message)
        # if category not in supported_categories:
        #     raise ValueError(f'Category "{category}" is not supported')

        # TODO: extend taxonomy
        self.training_pages = (
            self.training_pages_handler.get_training_pages_by_category(
                category, taxonomy_type="iabv1"
            )
        )
        print(f"Training pages set from {category}")
        return

    def _fresh_experiment_setup_and_clean_run(
        self, manager: TaskManager, do_a_clean_run=True
    ):
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
        os.makedirs(self.data_dir + f"results/{self.experiment_name}", exist_ok=True)

        # Make clean runs
        if do_a_clean_run:
            for control_site in self.control_pages:
                command_sequence = control_site_visit_sequence(
                    control_site, clean_run=True
                )
                manager.execute_command_sequence(command_sequence, index=0)
            # [TESTING] JUST FOR TESTING, ONLY 1 CLEAN VISIT RUN
            # command_sequence = control_site_visit_sequence(self.control_pages[0], clean_run=True)
            # manager.execute_command_sequence(command_sequence, index=0)

        # Create the training browser profile
        # This command sequence needs that the profile_archive_dir is set in the browser parameters. (_task_manager_config)
        browser_creation = individual_training_visit_sequence(
            random.choice(self.training_pages), creation=True, sleep=5
        )
        manager.execute_command_sequence(browser_creation, index=1)

        print("EXPERIMENT DIRECTORIES SET UP")

    # TODO: add browser_mode as an experiment_config
    # TODO 2: Right now, the browser profile is only dumped after a manager failure or successfully closing the manager after it finishes a crawling,
    #         but if the process is killed, the profile is not dumped but all of the experiment data is already saved, so we could
    #         call DumpProfileCommand periodically so if a several-hour crawling process is just killed, the profile still matches most of the experiment data for later runs.
    #         (also could be called in the signal_handler and in the error handling of the experiment_crawling method)
    def start(self, hours: int = 0, minutes: int = 0, browser_mode="headless"):
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

                self._get_and_create_experiment_config_json(manager)

                if self.fresh_experiment:
                    next_site_rank = 1
                    self._fresh_experiment_setup_and_clean_run(manager)
                else:
                    next_site_rank = get_amount_of_visits() + 1

                print("Launching OBA Crawler... \n")
                self.experiment_crawling(next_site_rank, manager, hours, minutes)

                # This logs an ERROR
                manager.close()

            successful_run_message = f"Successful run finished after "
            self._write_cleanup_message(successful_run_message)
        except Exception as exc:
            # TODO: Implement that if error is caught and the crawling has been running for long, save the profile before closing to not lose the data saved in SQLite of that run
            error_run_message = f"Error during run after "
            self._write_cleanup_message(error_run_message, exception_message = exc)

    @staticmethod
    def signal_handler(sig, frame):
        # Access the instance via the frame's local variables
        instance = frame.f_locals["self"]
        instance.signal_cleanup()
        sys.exit(0)

    def _write_cleanup_message(self, log_message_phrase, exception_message = ""):
        """Private method to be called when the experiment is terminated writing the runtime to the runtime_log.txt file"""
        runtime_seconds = time.time() - self.start_time
        hours, remainder = divmod(runtime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        runtime_string = f"{int(hours)}:{int(minutes)}:{int(seconds)}"
        log_message = f"{log_message_phrase} {runtime_string}.\n"
        with open(self.data_dir + "runtime_log.txt", "a") as f:
            f.write(f"{log_message}\n{exception_message}")

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

        # We only care about the display mode of the OBA browser
        clear_browser_params = BrowserParams(display_mode="headless")
        oba_browser_params = BrowserParams(display_mode=browser_display_mode)
        browsers_params = [clear_browser_params, oba_browser_params]

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

    def _get_and_create_experiment_config_json(self, manager: TaskManager):
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

        # Append browser ids to the corresponding lists
        experiment_json["browser_ids"]["clear"].append(manager.browsers[0].browser_id)
        experiment_json["browser_ids"]["oba"].append(manager.browsers[1].browser_id)

        # Save the updated JSON
        with open(file_path, "w") as file:
            json.dump(experiment_json, file)
        print("JSON file updated successfully.")

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
                    result_csv_file_name=self.banner_results_filename,
                )
            else:
                # CONTROL
                # If we start having more than one control visit sequence in this list, we must fix next_site_rank
                sequence_list = [
                    control_site_visit_sequence(
                        random.choice(self.control_pages),
                        next_site_rank,
                        cookie_banner_action=self.cookie_banner_action,
                        result_csv_file_name=self.banner_results_filename,
                    )
                ]
            next_site_rank += len(sequence_list)
            for command_sequence in sequence_list:
                manager.execute_command_sequence(command_sequence, index=1)

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

    def crawl_to_reject_cookies_manually(self):
        """Crawl each training + control page once in native mode to manually reject the cookies and save the profile to be used in the experiment."""
        # Note: We will treat this starting the experiment (so it is not fresh anymore)

        if not self.fresh_experiment:
            raise RuntimeError(
                "Experiment must be fresh to crawl to reject cookies manually, it must be done before starting the experiment"
            )

        try:
            # Manager context to start the crawling
            with TaskManager(
                self.manager_params,
                self.browser_params,
                SQLiteStorageProvider(Path(self.data_dir + "crawl-data.sqlite")),
                None,
            ) as manager:

                self._get_and_create_experiment_config_json(manager)

                # It is a fresh experiment, so we need to create the folders and create the training browser profile
                self._fresh_experiment_setup_and_clean_run(
                    manager, do_a_clean_run=False
                )

                print(
                    f"Launching crawler expecting the user to manually reject cookies in the training + control pages... \n Pages to visit {len(self.training_pages) + len(self.control_pages)} \n"
                )
                # Get all the command sequences to crawl the training pages and control pages
                reject_cookies_command_sequences = get_cookie_banner_visit_sequences(
                    self.training_pages, self.control_pages
                )
                for command_sequence in reject_cookies_command_sequences:
                    # Crawl each page in the browser that is going to be the OBA one
                    manager.execute_command_sequence(command_sequence, index=1)

                # TODO: Close non-OBA browser (index=0) in case it was open

                # This logs an ERROR
                manager.close()

            successful_run_message = f"Successful run finished after "
            self._write_cleanup_message(successful_run_message)

        except:
            # TODO: Implement that if error is caught and the crawling has been running for long, save the profile before closing to not lose the data saved in SQLite of that run
            error_run_message = f"Error during run after "
            self._write_cleanup_message(error_run_message)

    def write_bannerclick_finding_on_pages(self, page_urls: str):
        """With an openWPM crawler, visits a set of pages from the training_pages_db selected and updates with the presence / abscence of cookie banner accordingly."""

        def _validate_urls_in_db(page_urls):
            # Fetch
            conn = sqlite3.connect(self.training_pages_handler.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    page_url 
                FROM 
                    TrainingPages
                """
            )
            rows = cursor.fetchall()
            conn.close()

            # Build list of URLs
            urls = [row[0] for row in rows]

            # Validate URLs are in the database
            for url in page_urls:
                if url not in urls:
                    raise ValueError(f"URL {url} not found in database")

        # Validate URLs are in the database
        _validate_urls_in_db(page_urls)

        # Create a connection and cursor
        conn = sqlite3.connect(self.training_pages_handler.db_path)
        cursor = conn.cursor()

        # Params for openWPM crawler
        manager_params = ManagerParams(num_browsers=1)
        browsers_params = [BrowserParams(display_mode="headless")]

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
        manager_params.data_directory = Path("./oba/datadir_training_pages/_crawls/")
        manager_params.log_path = Path(
            "./oba/datadir_training_pages/_crawls/" + "openwpm.log"
        )

        manager_params.memory_watchdog = WATCHDOG
        manager_params.process_watchdog = WATCHDOG

        # Allow for many consecutive failures
        # The default is 2 x the number of browsers plus 10 (2x20+10 = 50)
        manager_params.failure_limit = 100000

        # Get crawler_database path
        crawl_db_path = "./oba/datadir_training_pages/_crawls/crawl-data.sqlite"

        # Create csv file to save the results
        with open(self.banner_results_filename, "w") as f:
            f.write(f"site_url,cookie_banner\n")

        try:

            with TaskManager(
                manager_params,
                browsers_params,
                SQLiteStorageProvider(Path(crawl_db_path)),
                None,
            ) as manager:

                bannerclick_cookie_banner_command_sequences = (
                    get_cookie_banner_visit_sequences(
                        training_pages=page_urls,
                        banner_results_csv_name=self.banner_results_filename,
                    )
                )
                for command_sequence in bannerclick_cookie_banner_command_sequences:
                    manager.execute_command_sequence(command_sequence)

                manager.close()

            # Read csv file and update database
            with open(self.banner_results_filename, "r") as f:
                lines = f.readlines()
                for line in lines[1:]:
                    page_url, cookie_banner = line.split(",")
                    cursor.execute(
                        """
                        UPDATE 
                            TrainingPages
                        SET 
                            cookie_banner_found = :found
                        WHERE
                            page_url = :page_url
                        """,
                        {"found": int(cookie_banner), "page_url": page_url},
                    )
                    conn.commit()

        except:
            # Read csv file and update database
            with open(self.banner_results_filename, "r") as f:
                lines = f.readlines()
                for line in lines[1:]:
                    page_url, cookie_banner = line.split(",")
                    cursor.execute(
                        """
                        UPDATE 
                            TrainingPages
                        SET 
                            cookie_banner_found = :found
                        WHERE
                            page_url = :page_url
                        """,
                        {"found": int(cookie_banner), "page_url": page_url},
                    )
                    conn.commit()
            conn.close()

        conn.close()


# # TODO: create a folder to add the logs that are saved whenever nohup is run with filename {exp_name}.log
