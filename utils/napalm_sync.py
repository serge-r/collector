#!/usr/bin/env python3

import os
import sys
import django
import re
import getpass
import clitable
from napalm import get_network_driver
from dcim.constants import *

# Regex for determine virtual interfaces type
VIRTUAL_REGEX = '^([Vv]lan|[Dd]iler|[Vv]irtual).*|(.+\.\d+)'

# Regex for determine LAG interfaces type
PORTCHANNEL_REGEX = '^([Pp]ort).*'

TEMPLATES_DIRECTORY = "cli_templates"

def connectToDevice(device, login, password):
    ''' Connect to device using NAPALM drivers
    '''
    driver = device.platform.napalm_driver
    ip_addr = str(device.primary_ip.address.ip)

    driver = get_network_driver(driver)

    print("connecting to device {} User: {}".format(ip_addr, login))

    connection = driver(ip_addr, login, password)

    try:
        connection.open()
    except Exception as e:
        print("Cannot connect to device {}, error is {}".format(ip_addr, e))
        return 0
    else:
        return connection


def initParser():
    try:
        parser = clitable.CliTable('index', TEMPLATES_DIRECTORY)
    except Exception as e:
        print("Problem with parser init - check index file and templates directory. Error is {}".format(e))
        return None
    return parser


def getInterfaceType(if_name):
    ''' Determine iface type (simple) 
    '''
    v_regex = re.compile(VIRTUAL_REGEX)
    p_regex = re.compile(PORTCHANNEL_REGEX)
    if v_regex.match(if_name) == None:
        if p_regex.match(if_name) == None:
            return IFACE_FF_1GE_FIXED # no way how to determine now interface type =(
        else:
            return IFACE_FF_LAG
    else:
        return IFACE_FF_VIRTUAL


def compareInterfaces(src_iface, dst_iface):
    ''' This function compare shortest interface name
        with longest interface name.

        EXAMPLE:
        eth0/1 should match Ethernet0/1
    '''
    regex = '([a-z\-]+)([\d/\.]+)'
    regex = re.compile(regex, re.I)
    try:
        src_name, src_number = regex.match(src_iface).groups()
        dst_name, dst_number = regex.match(dst_iface).groups()
    except:
        return False

    nameMatch = src_name.lower().startswith(dst_name.lower())
    return ((src_number == dst_number) and nameMatch)


def syncInterfaces(device, connection, iface_regex):
    ''' Get interfaces from device and add|update it on netbox
    '''
    interfaces = connection.get_interfaces()

    print("Connection complete, number of interfaces {}".format(len(interfaces)))

    for if_name in interfaces.keys():
        # Cheking is interface matching regex
        if re.match(iface_regex, if_name):
            if_type = getInterfaceType(if_name)
            # and state (up/down)
            state = (interfaces[if_name]['is_enabled'] and interfaces[if_name]['is_up'])

            intf = device.interfaces.filter(name = if_name)

            # I cannot found now a way how to do it without two code block =\
            if intf.count() == 0:
                # if no interface present in device, create new
                print("Create new interface {}".format(if_name))
                iface = Interface(name = if_name)
                iface.description = interfaces[if_name]['description']
                iface.mac_address = interfaces[if_name]['mac_address']
                iface.enabled =  state
                iface.form_factor = if_type
                iface.device = device
                iface.save()
                # Try to connect interface by description
                connect_interface(iface)
            else:
                # or get current iface and update them
                print("Update interface {}".format(if_name))
                iface = intf[0]
                iface.description = interfaces[if_name]['description']
                iface.mac_address = interfaces[if_name]['mac_address']
                iface.enabled =  state
                #iface.form_factor = if_type
                iface.save()
                # Try to connect interface by description
                connect_interface(iface)
        else:
            pass
          # print("Interface {} not matched - pass".format(if_name))


def sync_inventory(device, conn, parser):
    ''' Get list of parsed inventory commands
        And add it into netbox device inventory
    '''
    command = {'Command': 'sh inventory'}
    output = conn.cli([command['Command']])
    output = output[command['Command']]

    # print("Output is {}".format(output))
    if output:
        parser.ParseCmd(output, command)
        result = [list(row) for row in parser]

        if result:
            for item in result:
                name = item[0]
                descr = item[1]
                pid = item[2]
                serial = item[4]

                # Check, if this item exists (by device, name and serial)
                item = InventoryItem.objects.filter(device = device, name = name, serial = serial)

                if item:
                    print("Device {} alredy have a item {}".format(device.name, name))
                    continue
                else:
                    print("Tries to add a item {} on device {}".format(device.name, name))
                    item = InventoryItem()
                    item.manufacturer = device.device_type.manufacturer
                    item.name = name.strip('"')
                    item.part_id = pid
                    item.serial = serial
                    item.description = descr.strip('"')
                    item.device = device
                    item.save()
        else:
            print("Cannot parse output of command")
    else:
        print("Cannot do a command {} on device".format(command))


def connect_interface(interface):
    ''' Get iface connection from iface description
        Description should be like "server|port"
    '''
    desc_regex = "^(.*)+\|(.*)+"
    desc_regex = re.compile(desc_regex)

    iface_descr = interface.description

    if desc_regex.match(iface_descr):
        asset_tag, server_port = iface_descr.split('|')

        server = Device.objects.filter(asset_tag = asset_tag)
        if server:
            server = server[0]
            server_name = server.name

            # Find and compare ports
            for iface in server.interfaces.all():
                if compareInterfaces(iface.name, server_port):
                    port = iface
                else:
                    port = None

            port = server.interfaces.filter(name = server_port) 
            if port:
                conn = InterfaceConnection()
                conn.interface_a = interface
                conn.interface_b = port[0]
                try:
                    conn.save()
                except Exception as e:
                    print("Cannot do a connection {} to {} on {} - error is {}".format(interface.name, server_name, server_port, e))
                    return
                print("Successfully connected interface {} to server {} on port {}".format(interface.name, server_name, server_port))
            else:
                print("Cannot found interface {} on server {}".format(server_port, server_name))
        else:
            print("Cannot find server by AssetTag {}".format(asset_tag))
    else:
        print("Incorrect or None description on interface {} - cannot connect anything".format(interface.name))


if __name__ == '__main__': 
    ''' Sync network device interfaces with netbox
    '''
    if len(sys.argv) < 3:
        print("Script syncing cisco devices info (interface, inventory) with netbox")
        print("Usage {} <device_name> <user> [ifaces regex]".format(os.path.basename(__file__)))
        print("Iface regex is a custom option, if set - will sync only a matched regex interfaces")
        print("By default interfaces match '.*' regex")
        exit(0)

    # Init django enviroment
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")
    django.setup()
    from dcim.models import Device, Interface, InterfaceConnection, InventoryItem

    # Init args
    dev_name = sys.argv[1]
    user = sys.argv[2]
    if len(sys.argv) > 3:
        iface_regex = sys.argv[3]
    else:
        iface_regex = '.*'
    password = getpass.getpass("Password:")

    # Tries to init parser module
    parser = initParser()
    if parser == None:
        print("Cannot work without parser - exiting...")
        exit(-1)

    # Run sync
    device = Device.objects.get(name = dev_name)
    conn = connectToDevice(device, user, password)
    if conn == 0:
        print("Cannot sync without connection - exiting...")
        exit(-1)
    # sync_interfaces(device, conn, iface_regex)

    # sync inventory items
    sync_inventory(device, conn, parser)

    conn.close()