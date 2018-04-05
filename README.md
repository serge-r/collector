# Collector API

Its a simple Django App for extend API Netbox(https://github.com/digitalocean/netbox/)
This app allows to add inventory and interface (is design) items into Devices objects in netbox.

Concept - processing an raw command output (like a **dmidecode**, **ip a**, etc ) , parse it and save into Netbox.
For parsing data using a **clitable** functional from TextFSM (https://github.com/google/textfsm)

Now implemented only next command parse:

* Cisco IOS:
	**show inventory**
* Linux:
	**dmidecode**
	**lsblk -d** (with or without --output NAME,SIZE,MODEL,SERIAL)

## Installation

* Clone into netbox/ folder:

```
git clone https://github.com/serge-r/collector

```

* Add an app into **netbox/netbox/settings.py** file:

```python
# Installed applications
INSTALLED_APPS = (
    'django.contrib.admin',
 ....
    'virtualization',
    'collector', # <- it's here
)
```

* Add an app url in **netbox/netbox/urls.py** file:

```python
    # Admin
    url(r'^admin/', admin.site.urls),
    # Collector is here
    url(r'^api/collector/', include('collector.urls')),
```

## API Format

API allow only a simple JSON POST into url **/api/collector/**. :

```
{"Hostname": "MyHostName",
"Command": "doSomething",
"Data": "CommandOutputData"}
```

* Hostname - its a Netbox device name
* Command - its a command string, defined into clitable index file
* Data  - its a raw command output

Also will be need setup a two headers:
* **Content-Type: application/json**
* **Authorization: Token tokenbigstring**

Possible to make a queries via curl utility:

```
curl -H "Content-Type: appliction/json" -H "Authorization: Token token1234567890token123456" -d '{"Hostname": "TestHost", "Command": "lsblk", "Data": "sda    8:0    0 300G  0 disk" }' -X POST https://netbox.tld/api/collector/

{"result":true,"detail":"Device TestHost synced succesfully"}
```

But for simply working wih JSON - I wrote a **utils/client.py** file with same functions.

## Templates and commands

Command definition store in **cli_templates** folder.
```*.template ``` files - its a TextFSM-defined templates for process command output
```index``` file - bind a command string with a template


Still updated!
