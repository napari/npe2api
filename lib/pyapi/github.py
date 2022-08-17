import datetime as dt
import json
import os
import re
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import Literal, Optional, Tuple, TypedDict

import requests
from dateutil.parser import parse
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from humanize import naturaltime

from .core import active_plugins, pypi_info

GITHUB_RE = re.compile(r"https://github\.com/([^/]+)/([^/#@]+)")
PluginName = str


class CommitInfo(TypedDict):
    date: str
    message: str
    author_name: str
    author_login: str
    human_timedelta: str


class GithubActivity(TypedDict):
    default_branch: str
    open_issues: int
    pull_requests: int
    last_commit: CommitInfo
    forks: int
    stars: int
    watchers: int


class CoverageInfo(TypedDict):
    hits: int
    lines: int
    ratio: float
    commit: str
    date: str
    branch: str


class RepoSummary(TypedDict):
    url: str
    activity: GithubActivity
    coverage: Optional[CoverageInfo]


query_activity = gql(
    """
query repoActivity($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    stargazerCount
    forkCount
    watchers(first: 1) { totalCount }
    pullRequests(states: OPEN, first: 1) { totalCount }
    issues(states: OPEN) { totalCount }
    defaultBranchRef {
      name
      target {
        ... on Commit {
          history(first: 1) {
            nodes {
              message
              committedDate
              authoredDate
              author {
                name
                user {
                  login
                }
              }
            }
          }
        }
      }
    }
  }
}
"""
)


def activity(name: PluginName) -> GithubActivity:
    """Return github graphql data."""

    if not (result := org_repo(name)):
        return {}

    headers = {}
    if GH_API_TOKEN := os.environ.get("GH_API_TOKEN"):
        headers["Authorization"] = f"bearer {GH_API_TOKEN}"
    transport = RequestsHTTPTransport("https://api.github.com/graphql", headers)
    gql_client = Client(transport=transport, fetch_schema_from_transport=False)

    owner, name = result
    variables = {"owner": owner, "name": name}
    data = gql_client.execute(query_activity, variables)["repository"]
    last_commit_node = data["defaultBranchRef"]["target"]["history"]["nodes"][0]
    user = last_commit_node["author"].get("user") or {}
    date = last_commit_node["committedDate"]
    commit_dt = parse(date)
    last_commit = CommitInfo(
        date=date,
        message=last_commit_node["message"].split("\n")[0],
        author_name=last_commit_node["author"]["name"],
        author_login=user.get("login", ""),
        human_timedelta=naturaltime(dt.datetime.now(commit_dt.tzinfo) - commit_dt),
    )

    return GithubActivity(
        default_branch=data["defaultBranchRef"]["name"],
        open_issues=data["issues"]["totalCount"],
        pull_requests=data["pullRequests"]["totalCount"],
        forks=data["forkCount"],
        stars=data["stargazerCount"],
        watchers=data["watchers"]["totalCount"],
        last_commit=last_commit,
    )


def codecov(name: PluginName) -> Optional[CoverageInfo]:
    """Return coverage using codecov api."""
    if not (result := org_repo(name)):
        return None

    headers = {}
    if CODECOV_API_TOKEN := os.environ.get("CODECOV_API_TOKEN"):
        headers["Authorization"] = CODECOV_API_TOKEN

    url = "https://codecov.io/api/gh/{}/{}".format(*result)
    data = requests.get(url, headers=headers).json()
    commit: dict = data.get("commit")
    if not commit:
        commit = next((c for c in data.get("commits", []) if c.get("merged")), {})
    if not commit or not (totals := commit.get("totals")):
        return None

    return CoverageInfo(
        hits=totals["h"],
        lines=totals["n"],
        ratio=float(totals["c"]),
        commit=commit["commitid"],
        date=commit["timestamp"],
        branch=commit["branch"],
    )


@lru_cache
def org_repo(name: PluginName) -> Optional[Tuple[str, str]]:
    """Return the link to the public repo."""
    try:
        info: dict = pypi_info(name)["info"]
    except KeyError:
        return None

    for link in chain(
        [info.get("home_page"), info.get("package_url"), info.get("project_url")],
        (info.get("project_urls") or {}).values(),
    ):
        if match := GITHUB_RE.match(link):
            org, repo = match.groups()
            if repo.endswith(".git"):
                repo = repo[:-4]
            return org, repo
    return None


GITHUB_ENDPOINTS = Literal[
    "assignees",
    "branches",
    "commits",
    "commits/HEAD",
    "contents",
    "contributors",
    "forks",
    "events",
    "issues",
    "languages",
    "license",
    "pulls",
    "readme",
    "releases",
    "stargazers",
    "subscribers",
    "tags",
    "teams",
]


def github_info(name: PluginName, endpoint: str = "") -> dict:
    """Fetch information from github api."""
    if not (github_info := org_repo(name)):
        raise ValueError(f"No github repo for {name}")

    endpoint = f"/{endpoint}" if endpoint else ""
    url = "https://api.github.com/repos/{}/{}{}".format(*github_info, endpoint)
    headers = {"Accept": "application/vnd.github+json"}
    if GH_API_TOKEN := os.environ.get("GH_API_TOKEN"):
        headers["Authorization"] = f"token {GH_API_TOKEN}"
    return requests.get(url, headers=headers).json()


def repo_summary(name: PluginName) -> RepoSummary:
    """Return github repo summary."""
    if not (result := org_repo(name)):
        raise ValueError(f"No github repo found for {name!r}")
    url = "https://github.com/{}/{}".format(*result)
    return RepoSummary(url=url, activity=activity(name), coverage=codecov(name))


def _try_fetch_and_store_github_info(name: PluginName):
    try:
        summary = repo_summary(name)
        print(f"✅ gh: {name}")
    except Exception as e:
        print(f"❌  Failed to fetch github info for {name}: {e}")
        return

    GITHUB_DIR = Path(__file__).parent.parent.parent / "public" / "github"
    GITHUB_DIR.mkdir(exist_ok=True, parents=True)
    with open(GITHUB_DIR / f"{name}.json", "w") as f:
        json.dump(summary, f, indent=2)


def fetch_all_github_info() -> None:
    """Fetch all github info."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(_try_fetch_and_store_github_info, active_plugins())
