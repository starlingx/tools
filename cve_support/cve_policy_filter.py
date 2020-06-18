#
# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2019 Intel Corporation
#

"""
Implement policy based on
https://wiki.openstack.org/wiki/StarlingX/Security/CVE_Support_Policy
Create documentation as pydoc -w cve_policy_filter
"""
import json
import sys
import os
from lp import find_lp_assigned

cves_valid = []
cves_to_fix = []
cves_to_fix_lp = []
cves_to_track = []
cves_w_errors = []
cves_wont_fix = []
cves_to_omit = []
cves_report = {}


def print_html_report(cves_report, title):
    """
    Print the html report
    """
    import jinja2

    template_loader = jinja2.FileSystemLoader(searchpath="./")
    template_env = jinja2.Environment(loader=template_loader)
    if CVSS_VER == "cvssv3":
        template_file = "template_v3.txt"
        heads = ["cve_id", "status", "cvss3Score", "av", "ac", "ui","a"]
    else:
        template_file = "template.txt"
        heads = ["cve_id", "status", "cvss2Score", "av", "ac", "au", "ai"]

    template = template_env.get_template(template_file)
    output_text = template.render(cves_to_fix=cves_report["cves_to_fix"],\
        cves_to_fix_lp=cves_report["cves_to_fix_lp"],\
        cves_to_track=cves_report["cves_to_track"],\
        cves_wont_fix=cves_report["cves_wont_fix"],\
        cves_w_errors=cves_report["cves_w_errors"],\
        cves_to_omit=cves_report["cves_to_omit"],\
        heads=heads,\
        title=title)
    report_title = 'report_%s.html' % (title)
    html_file = open(report_title, 'w')
    html_file.write(output_text)
    html_file.close()

def print_report(cves_report, title):
    """
    Print the txt STDOUT report
    """
    print("\n%s report:" % (title))
    print("\nCVEs to fix w/o a launchpad assigned: %d\n" \
        % (len(cves_report["cves_to_fix"])))
    for cve in cves_report["cves_to_fix"]:
        print("\n")
        print(cve["id"])
        print("status : " + cve["status"])
        if CVSS_VER == "cvssv3":
            print("cvss3Score : " + str(cve["cvss3Score"]))
        else:
            print("cvss2Score : " + str(cve["cvss2Score"]))
        print("Attack Vector: " + cve["av"])
        print("Access Complexity : " + cve["ac"])
        if CVSS_VER == "cvssv3":
            print("User Interaction: " + cve["ui"])
        else:
            print("Authentication: " + cve["au"])
        print("Availability Impact :" + cve["ai"])
        print("Affected packages:")
        print(cve["affectedpackages"])
        print(cve["summary"])
        if cve["sourcelink"]:
            print(cve["sourcelink"])

    print("\nCVEs to fix w/ a launchpad assigned: %d \n" \
        % (len(cves_report["cves_to_fix_lp"])))
    for cve in cves_report["cves_to_fix_lp"]:
        cve_line = []
        for key, value in cve.items():
            if key != "summary":
                cve_line.append(key + ":" + str(value))
        print(cve_line)

    print("\nCVEs to track for incoming fix: %d \n" \
        % (len(cves_report["cves_to_track"])))
    for cve in cves_report["cves_to_track"]:
        cve_line = []
        for key, value in cve.items():
            if key != "summary":
                cve_line.append(key + ":" + str(value))
        print(cve_line)

    print("\nCVEs with no plans to fix (Won't Fix or Invalid): %d \n" \
        % (len(cves_report["cves_wont_fix"])))
    for cve in cves_report["cves_wont_fix"]:
        cve_line = []
        for key, value in cve.items():
            if key != "summary":
                cve_line.append(key + ":" + str(value))
        print(cve_line)


    if CVSS_VER == "cvssv3":
        print("\nERROR: CVEs that have no cvss3Score or cvss3Vector: %d \n" \
          % (len(cves_report["cves_w_errors"])))
    else:
        print("\nERROR: CVEs that have no cvss2Score or cvss2Vector: %d \n" \
          % (len(cves_report["cves_w_errors"])))
    for cve in cves_report["cves_w_errors"]:
        print(cve)

def get_summary(data, cve_id):
    """
    return: nvd summary
    """
    try:
        summary = data["scannedCves"][cve_id]["cveContents"]["nvd"]["summary"]
    except KeyError:
        summary = None
    return summary

def get_source_link(data, cve_id):
    """
    return: web link to the nvd report
    """
    try:
        source_link = data["scannedCves"][cve_id]["cveContents"]["nvd"]["sourceLink"]
    except KeyError:
        source_link = None
    return source_link

def get_affectedpackages(data, cve_id):
    """
    return: affected packages by the CVE and fix/unfix status of each package
    """
    affectedpackages_list = []
    allfixed = "fixed"
    try:
        affectedpackages = data["scannedCves"][cve_id]["affectedPackages"]
    except KeyError:
        affectedpackages = None
    else:
        for pkg in affectedpackages:
            affectedpackages_list.append(pkg["name"])
            if 'notFixedYet' in pkg and pkg["notFixedYet"] is True:
                allfixed = "unfixed"
    return affectedpackages_list, allfixed

def update_report():
    cves_report["cves_to_fix"] = cves_to_fix
    cves_report["cves_to_fix_lp"] = cves_to_fix_lp
    cves_report["cves_to_track"] = cves_to_track
    cves_report["cves_w_errors"] = cves_w_errors
    cves_report["cves_wont_fix"] = cves_wont_fix
    cves_report["cves_to_omit"] = cves_to_omit

def cvssv3_pb_alg():
    """
    Patchback algo for CVSSV3 report
    """
    for cve in cves_valid:
        if (cve["cvss3Score"] >= 7.8
                and cve["av"] == "N"
                and cve["ac"] == "L"
                and cve["ui"] == "R"
                and cve["ai"] != "N"):
                if cve["status"] == "fixed":
                    bug = find_lp_assigned(cve["id"])
                    if (bug):
                        print(bug["status"])
                        if (bug["status"] == "Invalid" or bug["status"] == "Won't Fix"):
                            cves_wont_fix.append(cve)
                        else:
                            cves_to_fix_lp.append(cve)
                    else:
                        cves_to_fix.append(cve)
                else:
                    cves_to_track.append(cve)
        else:
            cves_to_omit.append(cve)

    update_report()


def cvssv2_pb_alg():
    """
    Patchback algo for CVSSV2 report
    """
    for cve in cves_valid:
        if (cve["cvss2Score"] >= 7.0
                and cve["av"] == "N"
                and cve["ac"] == "L"
                and ("N" in cve["au"] or "S" in cve["au"])
                and ("P" in cve["ai"] or "C" in cve["ai"])):
            if cve["status"] == "fixed":
                bug = find_lp_assigned(cve["id"])
                if (bug):
                    print(bug["status"])
                    if (bug["status"] == "Invalid" or bug["status"] == "Won't Fix"):
                        cves_wont_fix.append(cve)
                    else:
                        cves_to_fix_lp.append(cve)
                else:
                    cves_to_fix.append(cve)
            else:
                cves_to_track.append(cve)
        else:
            cves_to_omit.append(cve)

    update_report()

def cvssv3_parse_n_report(cves,title,data):
    """
    Parse and generate report for CVSSV3
    """
    for cve in cves:
        cve_id = cve["id"]
        affectedpackages_list = []
        allfixed = "fixed"
        try:
            nvd2_score = data["scannedCves"][cve_id]["cveContents"]["nvd"]["cvss3Score"]
            cvss3vector = data["scannedCves"][cve_id]["cveContents"]["nvd"]["cvss3Vector"]
        except KeyError:
            cves_w_errors.append(cve)
        else:
            cve["cvss3Score"] = nvd2_score
            for element in cvss3vector.split("/"):
                if "AV:" in element:
                    _av = element.split(":")[1]
                if "AC:" in element:
                    _ac = element.split(":")[1]
                if "A:" in element:
                    _ai = element.split(":")[1]
                if "UI:" in element:
                    _ui = element.split(":")[1]
            print(cve)
            cve["av"] = str(_av)
            cve["ac"] = str(_ac)
            cve["ai"] = str(_ai)
            cve["ui"] = str(_ui)
            cve["summary"] = get_summary(data, cve_id)
            cve["sourcelink"] = get_source_link(data, cve_id)
            affectedpackages_list, allfixed = get_affectedpackages(data, cve_id)
            cve["affectedpackages"] = affectedpackages_list
            cve["status"] = allfixed
            cves_valid.append(cve)
    cvssv3_pb_alg()
    print_report(cves_report, title)
    print_html_report(cves_report, title)

def cvssv2_parse_n_report(cves,title,data):
    """
    Parse and generate report for CVSSV2
    """
    for cve in cves:
        cve_id = cve["id"]
        affectedpackages_list = []
        allfixed = "fixed"
        try:
            nvd2_score = data["scannedCves"][cve_id]["cveContents"]["nvd"]["cvss2Score"]
            cvss2vector = data["scannedCves"][cve_id]["cveContents"]["nvd"]["cvss2Vector"]
        except KeyError:
            cves_w_errors.append(cve)
        else:
            cve["cvss2Score"] = nvd2_score
            for element in cvss2vector.split("/"):
                if "AV:" in element:
                    _av = element.split(":")[1]
                if "AC:" in element:
                    _ac = element.split(":")[1]
                if "Au:" in element:
                    _au = element.split(":")[1]
                if "A:" in element:
                    _ai = element.split(":")[1]
            cve["av"] = str(_av)
            cve["ac"] = str(_ac)
            cve["au"] = str(_au)
            cve["ai"] = str(_ai)
            cve["summary"] = get_summary(data, cve_id)
            cve["sourcelink"] = get_source_link(data, cve_id)
            affectedpackages_list, allfixed = get_affectedpackages(data, cve_id)
            cve["affectedpackages"] = affectedpackages_list
            cve["status"] = allfixed
            cves_valid.append(cve)
    cvssv2_pb_alg()
    print_report(cves_report, title)
    print_html_report(cves_report, title)

def main():
    """
    main function
    Rules to consider a CVE valid for STX from:
    https://wiki.openstack.org/wiki/StarlingX/Security/CVE_Support_Policy
    """
    data = {}
    cves = []


    if len(sys.argv) < 4:
        print("\nERROR : Missing arguments, the expected arguments are:")
        print("\n   %s <result.json> <title> [cvssv3|cvssv2]\n" % (sys.argv[0]))
        print("\n result.json = json file generated from: vuls report -format-json")
        print("\n")
        sys.exit(0)

    if os.path.isfile(sys.argv[1]):
        results_json = sys.argv[1]
    else:
        print("%s is not a file" % sys.argv[1])
        sys.exit(0)

    title = sys.argv[2]

    try:
        with open(results_json) as json_file:
            data = json.load(json_file)
    except ValueError as error:
        print(error)

    for element in data["scannedCves"]:
        cve = {}
        cve["id"] = str(element.strip())
        cves.append(cve)
    global CVSS_VER
    CVSS_VER=sys.argv[3].lower()
    if CVSS_VER =="cvssv3":
        cvssv3_parse_n_report(cves,title,data)
    elif CVSS_VER == "cvssv2":
        cvssv2_parse_n_report(cves,title,data)
    else:
        print("\n argument not matching \n enter [cvssv3|cvssv2] ")
        sys.exit(0)


if __name__ == "__main__":
    main()
