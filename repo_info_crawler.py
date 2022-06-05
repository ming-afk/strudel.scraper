
import pandas as pd
import requests

import stscraper.base
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

def save_without_remove(all_repo_df, path):
    try:
        # existing = pd.read_csv(path, index=False)
        existing = pd.read_csv(path)

        updated = pd.concat([existing, all_repo_df], ignore_index=True)
        # updated.to_csv(path, index=False)
        updated.to_csv(path)

    except:
        # all_repo_df.to_csv(path, index=False)
        all_repo_df.to_csv(path,index=False)


def get_updated_pushed_topic_star_fork_issue_count(all_repo, api):
    '''
    single repo version
    '''

    start = time.time()
    req_num = 0
    count = 0

    save_repo = pd.DataFrame({key: [] for key in ['repository', 'topic', 'open_issues_count', 'open_issues', \
                                                  'pushed_at', 'updated_at', 'created_at', 'fork_count',
                                                  'stargazer_count', 'description', 'fork', 'language']})

    repos = all_repo['repository']

    for i in repos:
        print('searching: ', i)

        time_to_hour = 3600 - (time.time() - start)
        if req_num > 4990:
            print(time_to_hour)
            for i in range(5):
                print('Reached token limit, sleep remaining time:', time_to_hour * (5 - i) / 5, ' with ', type(time_to_hour),' time')
                time.sleep(time_to_hour / 5)
            time.sleep(10)  # extra sleep time avoiding erros
            start = time.time()
            req_num = 0

        # if token did not expire in one hour
        if time_to_hour <= 0:
            req_num = 0
            start = time.time()

        req_num += 1

        # try:
        # res = self.request(query)
        # token = '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'
        # headers = {'Authorization': f'token {token}'}

        # print(query)

        try:
            res = api.repo_info(i)
            # print(res)

            # ================= for use by old query ================ #
            # item = res['items'][0]
            # item_df = pd.DataFrame({'repository':i, 'topic':[item['topics']], 'open_issues_count':item['open_issues_count'],\
            #                         'open_issues':item['open_issues'],'pushed_at':item['pushed_at'],'updated_at':item['updated_at'],\
            #                         'created_at':item['created_at'], 'fork_count':item['forks_count'], 'stargazer_count':item['stargazers_count'],\
            #                         'description':item['description'],'fork':item['fork'], 'language':item['language']})
            # # print(item_df)
            item_df = pd.DataFrame(
                {'repository': i, 'topic': [res['topics']], 'open_issues_count': res['open_issues_count'], \
                 'open_issues': res['open_issues'], 'pushed_at': res['pushed_at'], 'updated_at': res['updated_at'], \
                 'created_at': res['created_at'], 'fork_count': res['forks_count'],
                 'stargazer_count': res['stargazers_count'], \
                 'description': res['description'], 'fork': res['fork'], 'language': res['language']})
            # print(item_df)
            save_repo = pd.concat([save_repo, item_df])

        # except:
        #     print("exception reached ... ...")
        #     item_df = pd.DataFrame({'repository':i, 'topic':[None], 'open_issues_count':[None],\
        #                             'open_issues':[None],'pushed_at':[None],'updated_at':[None],\
        #                             'created_at':[None], 'fork_count':[None], 'stargazer_count':[None],\
        #                             'description':[None],'fork':[None], 'language':[None]})
        #     save_repo = pd.concat([save_repo, item_df])
        except stscraper.base.RepoDoesNotExist as error:
            print("exception reached ... ...")
            item_df = pd.DataFrame({'repository':i, 'topic':[None], 'open_issues_count':[None],\
                                    'open_issues':[None],'pushed_at':[None],'updated_at':[None],\
                                    'created_at':[None], 'fork_count':[None], 'stargazer_count':[None],\
                                    'description':[None],'fork':[None], 'language':[None]})
            save_repo = pd.concat([save_repo, item_df])
        except requests.exceptions.HTTPError as error:
            time.sleep(10)
            clean = False
            while not clean:
                try:
                    res = api.repo_info(i)
                    clean = True
                except:
                    print('HTTP authorization error, sleeping... ...')
                    time.sleep(10)
                    pass

            item_df = pd.DataFrame(
                {'repository': i, 'topic': [res['topics']], 'open_issues_count': res['open_issues_count'], \
                 'open_issues': res['open_issues'], 'pushed_at': res['pushed_at'], 'updated_at': res['updated_at'], \
                 'created_at': res['created_at'], 'fork_count': res['forks_count'],
                 'stargazer_count': res['stargazers_count'], \
                 'description': res['description'], 'fork': res['fork'], 'language': res['language']})
            save_repo = pd.concat([save_repo, item_df])

        count += 1
        if not count % 100:
            save_repo = save_repo[
                ['repository', 'topic', 'open_issues_count', 'open_issues', 'pushed_at', 'updated_at', \
                 'created_at', 'fork_count', 'stargazer_count', 'description', 'fork', 'language']]
            # =+==================== saving ===================
            save_without_remove(save_repo, 'data/new_api_expanded_repos_8.csv')

            save_repo = pd.DataFrame({key: [] for key in ['repository', 'topic', 'open_issues_count', 'open_issues', \
                                                          'pushed_at', 'updated_at', 'created_at', 'fork_count',
                                                          'stargazer_count', 'description', 'fork', 'language']})
            print('saved')
    print(save_repo)

    # =+==================== saving ===================
    save_without_remove(save_repo, 'data/api_expanded_repos_8.csv')
    return