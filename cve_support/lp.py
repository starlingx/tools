#
# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2019 Intel Corporation
#

"""
Implement system to detect if CVEs has launchpad assigned
"""
import json
import os
from os import path
from launchpadlib.launchpad import Launchpad

# Filter the open bugs
STATUSES = [
    'New',
    'Incomplete',
    'Confirmed',
    'Triaged',
    'In Progress',
    'Fix Committed',
    'Fix Released',
    "Invalid",
    "Won't Fix",
]

CACHEDIR = path.join('/tmp', os.environ['USER'], '.launchpadlib/cache')
CVES_FILE = path.join(CACHEDIR, 'cves_open.json')
DATA = []


def search_upstrem_lps():
    """
    Search for launchpads open with CVE or cve in title
    """
    launchpad = Launchpad.login_anonymously\
        ('lplib.cookbook.json_fetcher', 'production',
         CACHEDIR, version='devel')
    project = launchpad.projects['starlingx']
    tasks = project.searchTasks(status=STATUSES, has_cve=True)
    for task in tasks:
        bug = task.bug
        if ("cve" in bug.title.lower()):
            bug_dic = {}
            bug_dic['id'] = bug.id
            bug_dic['status'] = task.status
            bug_dic['title'] = bug.title
            bug_dic['link'] = bug.self_link
            DATA.append(bug_dic)

    with open(CVES_FILE, 'w') as outfile:
        json.dump(DATA, outfile)

def find_lp_assigned(cve_id):
    """
    Check if a launchpad for CVE exist in DATA
    DATA must came from file or from upstream launchpad DB
    """
    global DATA

    if not DATA:
        if path.isfile(CVES_FILE):
            DATA = json.load(open(CVES_FILE, "r"))
        else:
            search_upstrem_lps()

    for bug in DATA:
        if cve_id in bug["title"]:
            return bug

    return None

def main():

    """
    Sanity test
    """
    cve_ids = ["CVE-2019-0160",\
        "CVE-2018-7536",\
        "CVE-2019-11810",\
        "CVE-2019-11811",\
        "CVE-2018-15686",\
        "CVE-2019-10126"]

    for cve_id in cve_ids:
        bug = find_lp_assigned(cve_id)
        if bug:
            print("\n")
            print(bug)
        else:
            print("\n%s has no LP assigned\n" % (cve_id))

if __name__ == "__main__":
    main()
