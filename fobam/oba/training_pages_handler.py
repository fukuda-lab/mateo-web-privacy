import asyncio
import os
import random
import sqlite3
import sys
from pathlib import Path

import aiohttp
from tqdm import tqdm
from tranco import Tranco

from .categorizer import Categorizer
from .enums import IAB_CATEGORIES
from .oba_commands_sequences import get_cookie_banner_visit_sequences

# sys.path.append("../openwpm")
# from bannerclick.config import WATCHDOG

# from fobam.openwpm.config import BrowserParams, ManagerParams
# from fobam.openwpm.storage.sql_provider import SQLiteStorageProvider
# from fobam.openwpm.task_manager import TaskManager  # docs: https://pypi.org/project/tranco/


# from datetime import datetime
# today_date = datetime.today().strftime('%Y-%m-%d')
DEFAULT_N_PAGES = 10000


class TrainingPagesHandler:
    # TODO: Discuss confidence level for WebShrinker categorization, wether we should use only confident categories for pages (reducing the amount of "usable" pages collected "automatically", but making sure they fit the category) or if we should use all the categories (increasing the amount of "usable" pages collected "automatically", but making sure they fit the category)
    """Handler for the Training Pages generation, processing and reading logic. The name for the db is 'list_id-n_pages'"""

    def __init__(
        self,
        list_id: str = "",
        categorize: bool = False,
        webshrinker_credentials: dict[str, str] = None,
        n_pages: int = DEFAULT_N_PAGES,
        updated_tranco: bool = False,
        custom_list: bool = False,
        custom_pages_list: list = [],
    ):
        if categorize and (
            not webshrinker_credentials
            or webshrinker_credentials.keys() != {"api_key", "secret_key"}
        ):
            raise ValueError(
                "When using the categorization feature, valid credentials for Webshrinker need to be provided"
            )
        self.n_pages = n_pages
        if webshrinker_credentials:
            self.categorizer = Categorizer(**webshrinker_credentials)
        else:
            self.categorizer = None
        self.custom_list = custom_list

        # Case specific training pages are provided by the user
        if custom_list:
            if not custom_pages_list or not list_id:
                raise ValueError(
                    "For custom training pages lists, an id for the list and a value for the list of url strings must be provided"
                )
            self.training_pages_list = custom_pages_list
            self.list_id = f"custom-{list_id}"

        # Cases using tranco
        else:
            # if list_id:
            self.tranco = TrainingPagesHandler.retrieve_tranco_top_list(
                list_id=list_id, updated=updated_tranco
            )
            # elif list_date:
            # self.tranco = TrainingPagesHandler.retrieve_tranco_top_list(list_date=list_date)
            # else:
            # If neither list_id and list_date are given, we will use the list and db included in the repository
            # self.tranco = TrainingPagesHandler.retrieve_tranco_top_list(list_id='X53KN')

            self.training_pages_list = self.tranco.top(n_pages)
            self.list_id = self.tranco.list_id

        # This way we make sure that we never create the exact same database two times for a given list with a fixed number of pages
        self.sqlite_db_name = (
            f"{self.list_id}-{str(len(self.training_pages_list))}.sqlite"
        )
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(
            script_dir, "datadir_training_pages", self.sqlite_db_name
        )
        self._create_db_if_not_exists()

    @staticmethod
    def retrieve_tranco_top_list(
        list_id: str = "",
        updated: bool = False,
        # list_date : str = '',
    ):
        """Call Tranco library list and get the pages either from cache or up-to-date.
        Returns a TrancoList object with method top(n_pages) and attributes list_id and date.
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tranco_cache_path = os.path.join(script_dir, "tranco_lists")

        t = Tranco(cache=True, cache_dir=tranco_cache_path)
        if updated == True:
            # Get latest
            tranco_list = t.list()
        if updated == False:
            # if not list_id and not list_date: # Missing info
            #     raise ValueError('A value for list_date or list_id arguments (only one of them) is required when getting a non updated version of the list')
            # elif not list_id and list_date: # Date provided
            #     tranco_list = t.list(date=list_date)
            # elif list_id and not list_date: # list_id provided
            #     tranco_list = t.list(list_id=list_id)
            # else:
            # try:
            tranco_list = t.list(list_id=list_id)
            # except:
            # tranco_list = t.list(date=list_date)

        return tranco_list

    def _create_db_if_not_exists(self):
        """Creates the database for the training_pages related data, and insert the training pages in the TrainingPages table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS TrainingPages (
            id INTEGER PRIMARY KEY,
            page_url TEXT UNIQUE,
            tranco_rank INTEGER DEFAULT NULL,
            cookie_banner_found BOOLEAN DEFAULT NULL,
        )
        """
        )

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS RetrievedCategories (
            id INTEGER PRIMARY KEY,
            training_page_id INTEGER,
            training_page_url INTEGER,
            category TEXT,
            taxonomy TEXT,
            taxonomy_tier INTEGER,
            taxonomy_id TEXT,
            confident BOOLEAN,
            FOREIGN KEY(training_page_id) REFERENCES TrainingPages(id)
        )
        """
        )

        for index, page in enumerate(self.training_pages_list):
            if self.custom_list:
                print(
                    "Remember that custom pages must include http protocol in the string"
                )
                # If it is a custom list, we cannot add the tranco_rank to the training page entry
                try:
                    cursor.execute(
                        "INSERT INTO TrainingPages (page_url) VALUES (?)", (page)
                    )
                except sqlite3.IntegrityError:
                    print(
                        "[DUPLICATE ERROR] Possible that page_url: {page} already exists"
                    )
                    pass
            else:
                url = "http://" + page
                try:
                    cursor.execute(
                        "INSERT INTO TrainingPages (page_url, tranco_rank) VALUES (?, ?)",
                        (url, index + 1),
                    )
                except sqlite3.IntegrityError:
                    print(
                        "[DUPLICATE ERROR] Possible that page_url: {url} already exists"
                    )
                    pass

        conn.commit()
        conn.close()
        return

    def categorize_training_pages(self, request_rate: int = 1, taxonomy: str = "iabv1"):
        """Initializes a new or existing SQLite database with the training_pages list, and starts/resumes the categorization of the list"""

        def _get_uncategorized_pages(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Query to retrieve the list of TrainingPages without categories
            cursor.execute(
                """
                SELECT TrainingPages.page_url
                FROM TrainingPages
                LEFT JOIN RetrievedCategories ON TrainingPages.id = RetrievedCategories.training_page_id
                WHERE RetrievedCategories.id IS NULL
            """
            )
            result = cursor.fetchall()
            page_urls_without_categories = [row[0] for row in result]

            print(f"{len(page_urls_without_categories)} pages yet to be categorized...")
            return page_urls_without_categories

        async def _async_categorize(db_path, request_rate, urls_to_categorize):
            """Categorize a list of URLs asyncronously given a request rate"""
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            async with aiohttp.ClientSession() as session:
                progress = tqdm(total=len(urls_to_categorize), desc="Categorizing")
                sem = asyncio.Semaphore(request_rate)

                async def fetch_and_store(url):
                    async with sem:
                        # TODO: Ask about limiting the number of retries
                        # retries = 3  # Number of retries
                        delay = 1  # Initial delay in seconds
                        while True:
                            response = await self.categorizer.categorize(
                                session, url, taxonomy=taxonomy
                            )
                            if response["status_code"] == 200:
                                # TODO: check case where we would need more than one "top_level_category"
                                # Poblate RetrievedCategories with all the categories received (max 3 per url in case of normal sites url with WebShrinker taxonomy)
                                for result in response["categories_response"]:
                                    cursor.execute(
                                        "SELECT id FROM TrainingPages WHERE page_url=?",
                                        (url,),
                                    )
                                    page_id = cursor.fetchone()[0]
                                    cursor.execute(
                                        "INSERT INTO RetrievedCategories (training_page_id, training_page_url, category, taxonomy, taxonomy_tier, taxonomy_id, confident) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                        (
                                            page_id,
                                            url,
                                            result["category"],
                                            result["taxonomy"],
                                            result["taxonomy_tier"],
                                            result["taxonomy_id"],
                                            result["confident"],
                                        ),
                                    )
                                progress.update(1)
                                print(f"[SUCCESS] Fetched categories for {url}")
                                break
                            elif response["status_code"] == 429:
                                print(
                                    f"[WARNING] Rate limit exceeded for {url}. Retrying in {delay} seconds..."
                                )
                                await asyncio.sleep(delay)
                                if delay < 4:
                                    delay *= 2  # Double the delay for each retry
                                else:
                                    delay += (
                                        1  # Add only one second after for 4 seconds
                                    )

                            else:
                                print(f"[ERROR] {response}")
                                break

                tasks = [fetch_and_store(url) for url in urls_to_categorize]
                await asyncio.gather(*tasks)

                conn.commit()
                conn.close()

        self._create_db_if_not_exists()

        # Only categorize missing training_pages so we can just resume in case of errors or large scale lists
        uncategorized_training_pages = _get_uncategorized_pages(self.db_path)
        if len(uncategorized_training_pages) == 0:
            print(
                "All training pages are already categorized or the list_id + number of pages is incorrect (db_name error)"
            )
            return
        asyncio.run(
            _async_categorize(self.db_path, request_rate, uncategorized_training_pages)
        )

    def get_training_pages_by_category(
        self, category: str, taxonomy_type: str = "iabv1"
    ):
        # Check for valid taxonomy type
        if taxonomy_type not in ["iabv1", "webshrinker"]:
            raise ValueError(
                "Invalid taxonomy type. Accepted values are 'iabv1' or 'webshrinker'"
            )

        # Check for valid category given the taxonomy
        matched = False
        if taxonomy_type == "iabv1":
            for iabv1_dict in IAB_CATEGORIES.values():
                # The name of the tier_1 categories are stored in a value with a key with the same id but nested
                for tier_2_category_name in iabv1_dict.values():
                    if category == tier_2_category_name:
                        matched = True
                        break
        elif taxonomy_type == "webshrinker":
            for taxonomy_value in IAB_CATEGORIES.values():
                if category == taxonomy_value:
                    matched = True
                    break
        if matched == False:
            raise ValueError(
                "Invalid category. Check https://docs.webshrinker.com/v3/iab-website-categories.html#tier-1-and-tier-2-categories"
            )

        print(self.db_path)
        # START FETCH
        # Create a connection and cursor
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Fetch the URLs based on category and taxonomy type
        cursor.execute(
            """
        SELECT training_page_url 
        FROM RetrievedCategories 
        WHERE category = ? AND taxonomy = ?
        """,
            (category, taxonomy_type),
        )

        # Fetch all rows
        rows = cursor.fetchall()

        # Close connection
        conn.close()

        # Extract URLs from rows
        urls = [row[0] for row in rows]

        return urls

    def get_most_popular_pages_by_category(
        self, k: int = 10, confident: bool = False, cookie_banner_found: bool = False
    ):
        """Returns at most the k most popular pages by category in the database (by id). Can be filtered by confident and cookie_banner_found"""
        # CONNECT TO DATABASE
        confident = 1 if confident else 0
        cookie_banner_found = 1 if cookie_banner_found else 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # FETCH
        cursor.execute(
            """
            WITH FilteredPages AS (
                SELECT 
                    RC.category,
                    TP.id,
                    TP.page_url,
                    ROW_NUMBER() OVER (PARTITION BY RC.category ORDER BY TP.id ASC) as rn
                FROM 
                    RetrievedCategories RC
                JOIN 
                    TrainingPages TP ON RC.training_page_id = TP.id
                WHERE 
                    RC.confident = :confident
                AND
                    TP.cookie_banner_found = :cookie_banner_found
            )
            SELECT 
                category,
                SUM(CASE WHEN rn <= :k THEN 1 ELSE 0 END) AS top_lowest_id_pages,
                GROUP_CONCAT(CASE WHEN rn <= :k THEN page_url END, ', ') AS top_page_urls,
                COUNT(id) AS total_pages
            FROM 
                FilteredPages
            WHERE 
                rn <= :k
            GROUP BY 
                category
            ORDER BY
                COUNT(id) DESC;
            """,
            {
                "confident": confident,
                "k": k,
                "cookie_banner_found": cookie_banner_found,
            },
        )
        rows = cursor.fetchall()
        # Close connection
        conn.close()

        # Build dict with key = category, value = dict with keys = category, top_lowest_id_pages, top_page_urls, total_pages
        categories_dict = {}
        for row in rows:
            categories_dict[row[0]] = {
                "page_urls": row[2].strip().split(", "),
                "page_ids": row[1],
            }

        return categories_dict

    def generate_training_pages_summary(self):

        # Connect to the SQLite database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Fetch the total number of training pages
        cursor.execute("SELECT COUNT(*) FROM TrainingPages")
        total_training_pages = cursor.fetchone()[0]
        print(f"Total training pages: {total_training_pages}")

        # Fetch the number of categorized training pages
        cursor.execute(
            """
        SELECT COUNT(DISTINCT training_page_id)
        FROM RetrievedCategories
        """
        )
        total_categorized_pages = cursor.fetchone()[0]
        print(f"Total categorized training pages: {total_categorized_pages}")

        # Fetch a few categorized pages as samples
        cursor.execute(
            """
        SELECT id, training_page_url, category, 
            taxonomy, taxonomy_tier, taxonomy_id,
            confident, training_page_id
        FROM RetrievedCategories
        ORDER BY category
        """
        )
        samples = cursor.fetchall()

        print("\nSample categorized pages:")
        for sample in samples:
            print(
                f"ID: {sample[0]}\nURL: {sample[1]}\nCategory: {sample[2]}\nTaxonomy: {sample[3]}\nTaxonomy Tier: {sample[4]}\n"
            )

        # Close the connection
        conn.close()


# API_KEY = 'GhU39K7bdfvdxRlcnEkT'
# SECRET_KEY = 'ZwnCzHIpw08DF10Fmz5c'
# # Example usage
# credentials = {
#     'api_key': API_KEY,
#     'secret_key': SECRET_KEY
# }
# # Custom list usage
# # training_pages_list = ['google.com', 'facebook.com']
# # pages_handler = TrainingPagesHandler(credentials, custom_list=True, list_id = 'test1', custom_pages_list=training_pages_list)

# # Tranco list usage
# pages_handler = TrainingPagesHandler(credentials, 'X53KN', n_pages = 10)
# pages_handler.categorize_training_pages()
# # print_db_summary(pages_handler.sqlite_db_name)

# test_category_pages = pages_handler.get_training_pages_by_category('iabv1', 'Technology & Computing')
# print(test_category_pages)
