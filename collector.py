from dcim.models import Device, Interface, InterfaceConnection, InventoryItem, Manufacturer
from dcim.constants import *
from collector.settings import *
import clitable
import re


def initParser():
    ''' Init CliTable '''
    try:
        parser = clitable.CliTable('index', TEMPLATES_DIRECTORY)
    except Exception as e:
        print("Problem with parser init - check index file and templates directory. Error is {}".format(e))
        return None
    return parser


def _getProcessFunction(parser, attrs):
    ''' Velosiped for return function from index file
        I belive, will possible make it as another simple method
        But now I cannot know how =\
    '''
    index = parser.index.index
    keys = index.header.values
    out = [dict(zip(keys, row)) for row in index]
    command = attrs['Command']
    vendor = attrs['Vendor']

    for item in out:
        if (re.match(item['Vendor'], vendor) and re.match(item['Command'],command)):
            # Tries to find function to process this command
            print(item['Function'])
            return globals().get(item['Function'])


def _getOrAddVendor(vendorName):
    # Check is this Vendor present on Netbox
    man = Manufacturer.objects.filter(name__icontains = vendorName)
    if man:
        # Get only first...
         return man[0]
    else:
        man = Manufacturer()
        man.name = vendorName
        # Replace any non-word character to dash
        man.slug = re.sub("\W+", "-", vendorName)
        man.save()
        return man 


def _getDevice(hostname):
    try:
        device = Device.objects.get(name = hostname)
        return device
    except Exception as e:
        return None


def parseQuery(parser, query):
    ''' Tries to parse command in output '''
    command = query['Command']
    data = query['Data']
    hostname = query['Hostname']

    device = _getDevice(hostname)

    if device == None:
        return (False, "Not found device by hostname: {}".format(hostname))

    # get vendor
    if device.platform:
        vendor = device.platform.name
    else:
        vendor = device.device_type.manufacturer.name

    attrs = {"Command": command, "Vendor": vendor}

    processFuncton = _getProcessFunction(parser, attrs)

    if processFuncton:
        # Its parsing time!
        try:
            parser.ParseCmd(data, attrs)
        except Exception as e:
            return (False, "Error while parsing. {}".format(e))
        # I will use a named indexes to prevent order changes
        keys = parser.header.values
        result = [dict(zip(keys, row)) for row in parser]
        print(result) 

        if result:
            # Process It!
            return processFuncton(device, result)
        else:
            return (False, "Cannot parse a command output - check template or command")
    else:
            return (False, "Function for process this command or for this vendor is not implemented yet =(")

    # if result:
    #     # Simple case
    #     if cmd_type == "Interface":
    #         result, reason = syncInterfaces(device, result)
    #         return {"result": result,
    #                 "detail": reason}
    #     elif cmd_type == "Inventory":
    #         result, reason = syncInventory(device, result)
    #         return {"result": result,
    #                 "detail": reason}
    #     else:
    #         return {"result": False,
    #                 "detail": "Cannot determine command type of command {} - should be Inventory or Interfaces".format(cmd_type)}
    # else:
    #     return {"result": False,
    #             "detail": "Empty parsing result. Check input data"}


def syncInterfaces(device, interfaces):
    return (False, "Not implemented")


def syncInventory(device, invenory):
    ''' Syncing Inventory in NetBox
    '''
    isChanged = False

    for item in invenory:
        # TODO: remake a template for remove dots
        name = item['Name'].strip('"')
        descr = item['Descr'].strip('"')
        pid = item['PartID'].strip('"')
        serial = item['Serial'].strip('"')

        # Check if manufacturer is present
        if 'Vendor' in item.keys():
            if item['Vendor']:
                manufacturer = _getOrAddVendor(item['Vendor'].strip('"'))
            else:
                manufacturer = None
        else:
                manufacturer = device.device_type.manufacturer

        # Check, if this item exists (by device, name and serial)
        item = InventoryItem.objects.filter(device = device, name = name, serial = serial)
        # print(item)
        if item:
           # print("Device {} alredy have a item {}".format(device.name, name))
           continue
        else:
            # print("Tries to add a item {} on device {}".format(name, device.name))
            item = InventoryItem()
            item.manufacturer = manufacturer
            item.name = name
            item.part_id = pid
            item.serial = serial
            item.description = descr
            item.device = device
            try:
                item.save()
                isChanged = True
            except Exception as e:
                print("Error to save Inventory item with name {} to device {}. Error is {}".format(name, device.name, e))
    if isChanged:
        return (True, "Device {} synced succesfully".format(device.name))
    else:
        return {False, "Device {} was not synced. May be all items alredy exists?".format(device.name)}



