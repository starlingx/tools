# StarlingX Application Generation Tool

The purpose of this tool is to generate StarlingX user applications in an easy
way without stx build environment and armada manifest schema knowledge.

## Pre-requisite

1. Helm2 installed
2. python3.5+
3. pyyaml>=5.0.0 package

`$ pip3 install pyyaml==5.1.2`

## 3 Steps to create a starlingx user app

#### 1. Prepare a helm chart(s)

##### What is helm and helm chart?

Helm is a Kubernetes package and operations manager. A Helm chart can contain
any number of Kubernetes objects, all of which are deployed as part of the
chart.

A list of official Helm Charts locates [here](https://github.com/helm/charts)

##### How to develop a helm chart?

Refer to official [helm doc](https://helm.sh/docs/)

#### 2. Create an app manifest

A few essential fields needed to create the app, simplest one could be:

```
appName: stx-app
namespace: stx-app
version: 1.0-1
chart:
- name: chart1
  path: /path/to/chart1
chartGroup:
- name: chartgroup1
  description: "This is the first chartgroup"
  sequenced: true
  chart_group:
  - chart1
manifest:
  name: stx-app-manifest
  releasePrefix: myprefix
  chart_groups:
  - chartgroup1
```
For more details, please refer to example.yaml

#### 3. Run app-gen.py

`$ python3 app-gen.py -i app_manifest.yaml [-o ./output] [--overwrite]`

The application will be generated automatically along with the tarball located
in the folder of your application name.
