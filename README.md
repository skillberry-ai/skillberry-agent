# blueberry-tools-agent

**This is a work in progress repository DO NOT USE IT UNTIL FURTHER NOTICE**

# Quickstart

## 1. Prerequisites

define the `RITS_API_KEY` environment variable

```bash
export RITS_API_KEY=********************************
```

set the service with the ipaddress of tools service

update `config/config_structure.py` with correct `tools_repo_base_url` key. 

_note:_ above step is temp until resolved

set virtual environment

```bash
python3 -m venv ~/virtual/blueberry-tools-agent
```

## 2. Installation

```bash
cd ~
git clone git@github.ibm.com:Blueberry/blueberry-tools-agent.git
cd blueberry-tools-agent
source ~/virtual/blueberry-tools-agent/bin/activate
pip install -r requirements.txt
```

## 3. Start the service

```bash
make run
```
