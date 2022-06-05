import stscraper.github as gh
import time
import calendar
from datetime import datetime
import json
from typing import Iterable
from random import randint
import os.path
import logging
import os.path
import pandas as pd
import datetime as dt
import math
import repo_info_crawler

if __name__ == "__main__":
    api = gh.GitHubAPI('abf38869614b92ddf8c21a38a78331c0c4159bed,\
6967cf2355f8e7f59f14c791f3572e129be6f993,\
ff5432b2601491b1675e2e2ffd3ed6d73da36339,\
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,\
f829bd1c2bf88ddc549eba2f44496baff087c9e8,\
d29e30994dd536ea72e08591f924bd20e2f2b1b3')

# ============= token checking ==============
#     token = gh.APIToken('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')
#     # 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
#     res = token.check_limits()
#     print(res)

    all_ = pd.read_csv('data/missed.csv')

    repo_info_crawler.get_updated_pushed_topic_star_fork_issue_count(all_, api)


    # res = api.repo_info('cpp-netlib/cpp-netlib')
    # print(res)
    # item_df = pd.DataFrame({'repository': i, 'topic': [res['topics']], 'open_issues_count': res['open_issues_count'], \
    #                         'open_issues': res['open_issues'], 'pushed_at': res['pushed_at'],
    #                         'updated_at': res['updated_at'], \
    #                         'created_at': res['created_at'], 'fork_count': res['forks_count'],
    #                         'stargazer_count': res['stargazers_count'], \
    #                         'description': res['description'], 'fork': res['fork'], 'language': res['language']})