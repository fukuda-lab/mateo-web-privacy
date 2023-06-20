# mateo-web-privacy

## Search Engine Leakage
This repository is part of a larger project focused on analyzing and understanding the phenomenon of Search Engine Leakage. Specifically, it aims to investigate how user queries and interactions with search engines could inadvertently lead to the disclosure of sensitive information to third parties, such as advertising networks. The repository contains automated browsing scripts that simulate user behavior on search engines. It employs a SQLite database to log site URLs and associated metadata. The critical aspect involves monitoring the network traffic, particularly targeting the communication between search engines and advertising servers. By processing and analyzing this data, which is stored in JSON and text files, the project seeks to uncover patterns and instances where private user data might be exposed or shared unintentionally.

Also, the idea is to compare the behavior among different localizations, for which a VPN is used to run the experiments in Tokyo (Japan), Santiago (Chile) and Prague (Czech Republic).

The `main` branch is not used. The relevant aspects of this project are separated in two branches:

* ### *`crawler-server`*: data collection (crawling)
The `crawler-server` has all the data collection, based on OpenWPM repository, to crawl data from the following Search Engines
| Site URL                                               | Brief Description                   |
| ------------------------------------------------------ | ----------------------------------- |
| https://www.bing.com/search?q=JELLYBEANS               | Microsoft's                         |
| https://swisscows.com/web?query=JELLYBEANS             | Switzerland                         |
| https://www.baidu.com/s?wd=JELLYBEANS                  | China                               |
| https://www.sogou.com/web?query=JELLYBEANS             | China (Tencent)                     |
| https://search.naver.com/search.naver?query=JELLYBEANS | South Korea                         |
| https://www.ask.com/web?q=JELLYBEANS                   | American                            |
| https://yandex.com/search/?text=JELLYBEANS             | Russia and CIS                      |
| https://duckduckgo.com/?q=JELLYBEANS                   | privacy-focused                     |
| https://search.seznam.cz/?q=JELLYBEANS                 | Czech Republic                      |
| https://www.ecosia.org/search?q=JELLYBEANS             | Intentional advertising for ecology |
| https://www.startpage.com/do/dsearch?query=JELLYBEANS  | privacy-focused, powered by Google  |
| https://www.google.com/search?q=JELLYBEANS             | world's most popula                 |
| https://www.qwant.com/?q=JELLYBEANS                    | European, privacy                   |
| https://search.yahoo.com/search?p=JELLYBEANS           | powered by Bing                     |
| https://search.aol.com/aol/search?q=JELLYBEANS         | American                            |

* ### *`local-mateo`*: data processing and analysis
The `local-mateo` branch has all the data processing and further analysis of the crawled data.
The important part with the overall contributions and tasks with their corresponding scripts and results, can be found in the `openwpm/jellybeans_leakage` folder.

>#### &emsp; Clarification about folders with the same name along the branch
>&emsp; &emsp; - `*/sqlite` folders have the `.sqlite` files that are read by the scripts, with all the SQL data that is supposed to be used by the direct parent directory of each `sqlite` folder. They also include `enums.py` files with query string and helper classes to unclutter the scripts themselves, these are also supposed to be used in the direct parent directory, but some enums are coupled with other scripts. \
>&emsp; &emsp; - `*/results` folders are parallel to the `sqlite` folders and are used to gather the `.json` and `.txt` output files of the data processing. These are the folders that should be opened when looking for this information.


## Main Activities summaries and description

### Search Term Exact Leakage
The first experiment / activity / task, was trying to precisely identify leakages in http requests, javascripts and cookies, by directly looking for the search term string "JELLYBEANS" (case unsensitive, in 28 different encodings) in the columns of the collected data that could be being shared with third parties (defined as entities with a different domain name), all the relevant information can be found in the *`data_analysis/leakages`* folder.
The results of this experiment can be found in the `data_analysis/leakages/results` folder. Further data analysis is required in order to establish important conclusions.

### Matching with Adblock Plus' _blacklists_ and _whitelist_ (EasyList, EasyPrivacy and Exception List)
This is the second experiment, in which all the crawled data (not only the ones that included the Search Term) was filtered with the Third Party criteria, and then was matched against the EasyList, EasyPrivacy and Exception List of Adblock Plus, in order to get insights about http_requests and javascripts that would be blocked (or blocked and then allowed by default, thanks to the payed enrollment of the responsible entities of those resources in the case of the Exception List). This can be found in the *`data_analysis/third_party`* folder.
Two different matching tools were used for the in order to get more complete information:
* Python: [`Adblock Parser`](https://github.com/scrapinghub/adblockparser) 
* Rust (JS Binding): [`Adblock-Rust`](https://github.com/brave/adblock-rust) Brave Browser's native adblocker engine.

The results of this experiment can be found in the `data_analysis/third_party/results` folder. Again, further data analysis is required in order to establish important conclusions.
