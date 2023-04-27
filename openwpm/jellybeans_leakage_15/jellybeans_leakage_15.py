import sqlite3
import pandas as pd
import urllib.parse
import base64

# Connect to the SQLite database
conn = sqlite3.connect("../datadir/jellybeans_leakage_15_crawl.sqlite")

# Define the query
query = """
SELECT sv.visit_id,
       sv.site_url,
       hr.request_id,
       hr.url,
       hr.top_level_url,
       hr.method,
       hr.referrer,
       hr.headers,
       hr.post_body,
       hr.post_body_raw,
       js.value AS js_value,
       jsc.name AS cookie_name,
       jsc.path AS cookie_path,
       jsc.value AS cookie_value
FROM site_visits sv
LEFT JOIN http_requests hr ON sv.visit_id = hr.visit_id
LEFT JOIN javascript js ON sv.visit_id = js.visit_id
LEFT JOIN javascript_cookies jsc ON sv.visit_id = jsc.visit_id;
"""

# Read the data into a pandas DataFrame
data = pd.read_sql_query(query, conn)

# Close the database connection
conn.close()

# Prepare the search terms
keyword = "JELLYBEANS"
url_encoded_keyword = urllib.parse.quote(keyword)
base64_encoded_keyword = base64.b64encode(keyword.encode()).decode()

search_terms = [keyword, url_encoded_keyword, base64_encoded_keyword]

# Function to search for leakage
def search_leakage(column, output):
    for term in search_terms:
        leakage = data[data[column].str.contains(term, na=False, case=False)]
        if not leakage.empty:
            output.write(f"Leakage found in {column} with search term: {term}\n")
            output.write(f"{leakage}\n")


# Search for leakage in relevant columns
columns_to_search = [
    "site_url",
    "url",
    "top_level_url",
    "method",
    "referrer",
    "headers",
    "post_body",
    "post_body_raw",
    "js_value",
    "cookie_name",
    "cookie_path",
    "cookie_value",
]

with open("jellybeans_leakage_output.txt", "w") as output:
    for column in columns_to_search:
        search_leakage(column, output)
