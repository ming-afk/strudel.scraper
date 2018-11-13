
from __future__ import print_function

import datetime
import json
import os
import warnings

from xml.etree import ElementTree

from .base import *
import stutils


class GitHubAPIToken(APIToken):
    api_url = "https://api.github.com/"
    api_classes = ('core', 'search')
    status_too_many_requests = (403,)

    _user = None  # cache user
    # dictionaries are mutable. Don't put default headers dict here
    # or it will be shared by all class instances
    _headers = None

    def __init__(self, token=None, timeout=None):
        super(GitHubAPIToken, self).__init__(token, timeout)
        # mercy-preview: repo topics
        # squirrel-girl-preview: issue reactions
        # starfox-preview: issue events
        self._headers = {
            "Accept": "application/vnd.github.mercy-preview+json,"
                      "application/vnd.github.squirrel-girl-preview,"
                      "application/vnd.github.starfox-preview+json"}
        if token is not None:
            self.token = token
            self._headers["Authorization"] = "token " + token

    @property
    def user(self):
        if self._user is None:
            try:
                r = self('user')
            except TokenNotReady:
                pass
            else:
                self._user = r.json().get('login', '')
        return self._user

    def check_limits(self):
        # regular limits will be updated automatically upon request
        # we only need to take care about search limit
        try:
            stats = self('rate_limit').json()['resources']
        except TokenNotReady:
            stats = {}

        for cls in self.api_classes:
            self.limits[cls] = json_map({
                'remaining': 'remaining',
                'reset': 'reset',
                'limit': 'limit',
            }, stats.get(cls, {}))

        return self.limits

    @staticmethod
    def api_class(url):
        return 'search' if url.startswith('search') else 'core'

    def legit(self):
        """ Check if this is a legit key"""
        if self.limits['core']['limit'] is None:
            self.check_limits()
        return self.limits['core']['limit'] < 100

    def when(self, url):
        key = self.api_class(url)
        if self.limits[key]['remaining'] != 0:
            return 0
        return self.limits[key]['reset']

    def _update_limits(self, response, url):
        if 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            self.limits[self.api_class(url)] = {
                'remaining': remaining,
                'reset': int(response.headers['X-RateLimit-Reset']),
                'limit': int(response.headers['X-RateLimit-Limit'])
            }

            if response.status_code == 403 and remaining == 0:
                raise TokenNotReady


class GitHubAPI(VCSAPI):
    """ This is a convenience class to pool GitHub API keys and update their
    limits after every request. Actual work is done by outside classes, such
    as _IssueIterator and _CommitIterator
    """
    tokens = None
    token_class = GitHubAPIToken
    base_url = 'https://github.com'

    def __init__(self, tokens=None, timeout=30):
        # Where to look for tokens:
        # strudel config variables
        if not tokens:
            stconfig_tokens = stutils.get_config("GITHUB_API_TOKENS")
            if stconfig_tokens:
                tokens = [token.strip()
                          for token in stconfig_tokens.split(",")
                          if len(token.strip()) == 40]

        # hub configuration: https://hub.github.com/hub.1.html
        if not tokens:
            token = stutils.get_config("GITHUB_TOKEN")
            if not token and os.path.isfile("~/.config/hub"):
                token = open("~/.config/hub", 'r').read(64)
            if token and len(token.strip()) == 40:
                tokens = [token.strip()]

        if not tokens:
            tokens = [None]
            warnings.warn("No tokens provided. GitHub API will be limited to "
                          "60 requests an hour", Warning)

        super(GitHubAPI, self).__init__(tokens, timeout)

    def has_next_page(self, response):
        for rel in response.headers.get("Link", "").split(","):
            if rel.rsplit(";", 1)[-1].strip() == 'rel="next"':
                return True
        return False

    # ===================================
    #           API methods
    # ===================================
    @api('users', paginate=True)
    def all_users(self):
        # https://developer.github.com/v3/users/#get-all-users
        return ()

    @api('repositories', paginate=True)
    def all_repos(self):
        # https://developer.github.com/v3/repos/#list-all-public-repositories
        return ()

    @api_filter(lambda issue: 'pull_request' not in issue)
    @api('repos/%s/issues', paginate=True, state='all')
    def repo_issues(self, repo_name):
        # type: (Union[str, unicode]) -> Iterable[dict]
        # https://developer.github.com/v3/issues/#list-issues-for-a-repository
        return repo_name

    @api('repos/%s/issues/comments', paginate=True)
    def repo_issue_comments(self, repo_name):
        # type: (Union[str, unicode]) -> Iterable[dict]
        """ Get all comments in all issues and pull requests,
        both open and closed.
        """
        # https://developer.github.com/v3/issues/comments/#list-comments-in-a-repository
        return repo_name

    @api('repos/%s/issues/events', paginate=True)
    def repo_issue_events(self, repo_name):
        # type: (Union[str, unicode]) -> Iterable[dict]
        """ Get all events in all issues and pull requests,
        both open and closed.
        """
        # https://developer.github.com/v3/issues/events/#list-events-for-a-repository
        return repo_name

    @api('repos/%s/commits', paginate=True)
    def repo_commits(self, repo_name):
        # type: (Union[str, unicode]) -> Iterable[dict]
        # https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository
        return repo_name

    @api('repos/%s/pulls', paginate=True, state='all')
    def repo_pulls(self, repo_name):
        # type: (Union[str, unicode]) -> Iterable[dict]
        # https://developer.github.com/v3/pulls/#list-pull-requests
        return repo_name

    def repo_topics(self, repo_name):
        return tuple(
            next(self.request('repos/%s/topics' % repo_name)).get('names'))

    def repo_labels(self, repo_name):
        return tuple(label['name'] for label in
                     self.request('repos/%s/labels' % repo_name, paginate=True))

    @api('repos/%s/pulls/%d/commits', paginate=True, state='all')
    def pull_request_commits(self, repo, pr_id):
        # https://developer.github.com/v3/issues/comments/#list-comments-on-an-issue
        return repo, pr_id

    @api('repos/%s/issues/%s/comments', paginate=True, state='all')
    def issue_comments(self, repo, issue_id):
        """ Return comments on an issue or a pull request
        Note that for pull requests this method will return only general
        comments to the pull request, but not review comments related to
        some code. Use review_comments() to get those instead

        :param repo: str 'owner/repo'
        :param issue_id: int, either an issue or a Pull Request id
        """
        # https://developer.github.com/v3/issues/comments/#list-comments-on-an-issue
        return repo, issue_id

    @api('repos/%s/pulls/%s/comments', paginate=True, state='all')
    def review_comments(self, repo, pr_id):
        """ Pull request comments attached to some code
        See also issue_comments()
        """
        # https://developer.github.com/v3/pulls/comments/
        return repo, pr_id

    @api('users/%s')
    def user_info(self, username):
        # Docs: https://developer.github.com/v3/users/#response
        return username

    @api('users/%s/repos', paginate=True)
    def user_repos(self, username):
        """Get list of user repositories"""
        # https://developer.github.com/v3/repos/#list-user-repositories
        return username

    @api('users/%s/orgs', paginate=True)
    def user_orgs(self, username):
        # https://developer.github.com/v3/orgs/#list-user-organizations
        return username

    @api('orgs/%s/members', paginate=True)
    def org_members(self, org):
        # https://developer.github.com/v3/orgs/members/#members-list
        return org

    @api('orgs/%s/repos', paginate=True)
    def org_repos(self, org):
        return org

    @api('repos/%s/issues/%d/events', paginate=True)
    def issue_events(self, repo, issue_no):
        return repo, issue_no

    # ===================================
    #        Non-API methods
    # ===================================
    @staticmethod
    def project_exists(repo_name):
        return bool(requests.head("https://github.com/" + repo_name))

    @staticmethod
    def canonical_url(project_url):
        # type: (str) -> str
        """ Normalize URL
        - remove trailing .git  (IMPORTANT)
        - lowercase (API is insensitive to case, but will allow to deduplicate)
        - prepend "github.com"

        :param project_url: str, user_name/repo_name
        :return: github.com/user_name/repo_name with both names normalized

        >>> GitHubAPI.canonical_url("pandas-DEV/pandas")
        'github.com/pandas-dev/pandas'
        >>> GitHubAPI.canonical_url("http://github.com/django/django.git")
        'github.com/django/django'
        >>> GitHubAPI.canonical_url("https://github.com/A/B/")
        'github.com/a/b/'
        """
        url = project_url.lower()
        for chunk in ("http://", "https://", "github.com"):
            if url.startswith(chunk):
                url = url[len(chunk):]
        if url.endswith("/"):
            url = url[:-1]
        while url.endswith(".git"):
            url = url[:-4]
        return "github.com/" + url

    user_cookies = None  # cookies for non-API URLs
    user_headers = {   # browser headers for non-API URLs
        'X-Requested-With': 'XMLHttpRequest',
        'Accept-Encoding': "gzip,deflate,br",
        'Accept': "*/*",
        'Origin': base_url,
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:60.0) "
                      "Gecko/20100101 Firefox/60.0",
        "Host": 'github.com',
        "Referer": base_url,
        "DNT": "1",
        "Accept-Language": 'en-US,en;q=0.5',
        "Connection": "keep-alive",
        "Cache-Control": 'max-age=0',
    }

    def user_request(self, url, headers=None):
        """ Make a non-API request
        (it is used to get user activity and repo contributors)
        """
        headers = headers or self.user_headers

        if self.user_cookies is None:
            self.user_cookies = requests.get("https://github.com").cookies

        r = requests.get(url, cookies=self.user_cookies, headers=headers)
        r.raise_for_status()
        return r

    def project_activity(self, repo_name):
        # type: (str) -> dict
        """Get top 100 contributors commit stats by week (non-API method)"""
        return self.user_request(
            "%s/%s/graphs/contributors-data" % (self.base_url, repo_name)
        ).json()

    def contributions(self, user, year):
        # type: (str, int) -> dict
        """ Get daily user contribution stats (non-API method)"""
        url = "%s/users/%s/contributions?" \
              "from=%d-12-01&to=%d-12-31&full_graph=1" % \
              (self.base_url, user, year, year)
        tree = ElementTree.fromstring(self.user_request(url).text)

        return {rect.attrib.get('data-date'): int(rect.attrib.get('data-count'))
                for rect in tree.iter('rect')
                if rect.attrib.get('class') == 'day'}

    def user_activity(self, user):
        """ Get user events as a 2-tuple generator: (date, link).

        Events include: commits, issues and refs creation (tags/branches).
        This call is not subject to API rate limit.

        Unfortunately, only few last months data are available.
        """
        import feedparser
        import pandas as pd

        def extract_links(text):
            tree = ElementTree.fromstring(text)

            date = None
            for span in tree.iter('span'):
                if 'f6' not in span.attrib.get('class', '').split(" "):
                    continue
                try:
                    date = pd.to_datetime(span.text.strip())
                except ValueError:
                    continue
                break

            links = []
            for link in tree.iter('a'):
                href = link.attrib.get('href', '')
                chunks = href.split("/")
                # hrefs start with "/" so chunks[0] is an empty string
                # this is why 'commit/issue/tree' is chunks[3], not [2]
                if len(chunks) < 5 or \
                        chunks[3] not in ('commit', 'issue', 'tree'):
                    continue
                if href not in links:
                    links.append(href)
                    yield (date, href)

        page = None
        while True:
            r = requests.get('%s/%s' % (self.base_url, user),
                             params={'page': page},
                             headers={'Accept': 'application/atom+xml'})
            r.raise_for_status()
            page = 1 if page is None else page + 1

            activity_log = feedparser.parse(r.text).entries
            if not activity_log:
                return

            for record in activity_log:
                for chunk in record['content']:
                    for link in extract_links(chunk['value'].encode('utf8')):
                        yield link


class GitHubAPIv4(GitHubAPI):
    """ An example class using GraphQL API """
    def v4(self, query, **params):
        payload = json.dumps({"query": query, "variables": params})
        return self.request("graphql", 'post', data=payload)

    def repo_issues(self, repo_name, cursor=None):
        # type: (str, str) -> Iterable[dict]
        owner, repo = repo_name.split("/")
        query = """query ($owner: String!, $repo: String!, $cursor: String) {
        repository(name: $repo, owner: $owner) {
          hasIssuesEnabled
            issues (first: 100, after: $cursor,
              orderBy: {field:CREATED_AT, direction: ASC}) {
                nodes {author {login}, closed, createdAt,
                       updatedAt, number, title}
                pageInfo {endCursor, hasNextPage}
        }}}"""

        while True:
            data = self.v4(query, owner=owner, repo=repo, cursor=cursor
                           )['data']['repository']
            if not data:  # repository is empty, deleted or moved
                break

            for issue in data["issues"]:
                yield {
                    'author': issue['author']['login'],
                    'closed': issue['closed'],
                    'created_at': issue['createdAt'],
                    'updated_at': issue['updatedAt'],
                    'closed_at': None,
                    'number': issue['number'],
                    'title': issue['title']
                }

            cursor = data["issues"]["pageInfo"]["endCursor"]

            if not data["issues"]["pageInfo"]["hasNextPage"]:
                break

    def repo_commits(self, repo_name, cursor=None):
        # type: (str, str) -> Iterable[dict]
        """As of June 2017 GraphQL API does not allow to get commit parents
        Until this issue is fixed this method is only left for a reference
        Please use commits() instead"""
        owner, repo = repo_name.split("/")
        query = """query ($owner: String!, $repo: String!, $cursor: String) {
        repository(name: $repo, owner: $owner) {
          ref(qualifiedName: "master") {
            target { ... on Commit {
              history (first: 100, after: $cursor) {
                nodes {sha:oid, author {name, email, user{login}}
                       message, committedDate}
                pageInfo {endCursor, hasNextPage}
        }}}}}}"""

        while True:
            data = self.v4(query, owner=owner, repo=repo, cursor=cursor
                           )['data']['repository']
            if not data:
                break

            for commit in data["ref"]["target"]["history"]["nodes"]:
                yield {
                    'sha': commit['sha'],
                    'author': commit['author']['user']['login'],
                    'author_name': commit['author']['name'],
                    'author_email': commit['author']['email'],
                    'authored_date': None,
                    'message': commit['message'],
                    'committed_date': commit['committedDate'],
                    'parents': None,
                    'verified': None
                }

            cursor = data["ref"]["target"]["history"]["pageInfo"]["endCursor"]
            if not data["ref"]["target"]["history"]["pageInfo"]["hasNextPage"]:
                break


def get_limits(tokens=None):
    """Get human-readable rate usage limit.

    Returns a generator of dictionaries with columns:

    """
    api = GitHubAPI(tokens)
    now = datetime.now()

    for i, token in enumerate(api.tokens):
        # if limit is exhausted there is no way to get username
        user = token.user or "<unknown%d>" % i
        values = {'user': user, 'key': token.token}
        token.check_limits()

        for api_class in token.limits:
            # geez, this code smells
            next_update = token.limits[api_class]['reset']
            if next_update is None:
                renew = 'never'
            else:
                tdiff = datetime.fromtimestamp(next_update) - now
                renew = "%dm%ds" % divmod(tdiff.seconds, 60)
            values[api_class + '_renews_in'] = renew
            values[api_class + '_limit'] = token.limits[api_class]['limit']
            values[api_class + '_remaining'] = token.limits[api_class]['remaining']

        yield values


def print_limits(argv=None):
    """Check remaining limits of registered GitHub API keys"""
    # import argparse
    # parser = argparse.ArgumentParser(
    #     description="Check remaining limits of registered GitHub API keys")
    # # two lines above are just to print help, so ignoring the output
    # _ = parser.parse_args()

    columns = ("user", "core_limit", "core_remaining", "core_renews_in",
               "search_limit", "search_remaining", "search_renews_in",
               "key")

    stats = list(get_limits())

    lens = {column: max(max(len(str(values[column])), len(column))
                        for values in stats)
            for column in columns}

    print(" ".join(c.ljust(lens[c] + 1, " ") for c in columns))
    for values in stats:
        print(" ".join(
            str(values[c]).ljust(lens[c] + 1, " ") for c in columns))
