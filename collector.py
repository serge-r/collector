from dcim.models import Device, Interface, InterfaceConnection, InventoryItem, Manufacturer
from dcim.constants import *
from collector.settings import *
from django.utils.log import DEFAULT_LOGGING
import logging
import clitable
import re

logger = logging.getLogger('django.server')


def initParser():
    ''' Init CliTable index and templates
        This function should be call first, before parsing

        Returns: cliTable object or None
    '''
    try:
        parser = clitable.CliTable('index', TEMPLATES_DIRECTORY)
        logger.info("Collector module loads: Im Alive!!!")
    except Exception as e:
        logger.error("Problem with parser init - check index file and templates directory. Error is %s", e)
        return None
    return parser


def _getProcessFunction(parser, attrs):
    ''' Velosiped for return function from index file
        I belive, will possible make it as another simple method
        But now I cannot know how =\

        Returns: Function or None
    '''
    index = parser.index.index
    keys = index.header.values
    out = [dict(zip(keys, row)) for row in index]
    command = attrs['Command']
    vendor = attrs['Vendor']

    for item in out:
        if (re.match(item['Vendor'],vendor) and re.match(item['Command'],command)):
            # Tries to find function to process this command
            func = globals().get(item['Function'])
            logger.info("Function is %s", func)
            return func


def _getOrAddVendor(vendorName):
    ''' Check is this Vendor present on Netbox

        Returns: Vendor object

        TODO: Add a save() check
    '''
    man = Manufacturer.objects.filter(name__icontains = vendorName)
    if man:
        # Get only first...
        logger.info("Found a vendor {} - return it".format(vendorName))
        return man[0]
    else:
        logger.info("Create a new vendor")
        man = Manufacturer()
        man.name = vendorName
        # Replace any non-word character to dash
        man.slug = re.sub("\W+", "-", vendorName)
        man.save()
        return man 


def _getDevice(hostname):
    ''' Get device object from Netbox 
        
        Returns: Device object or None
    '''
    try:
        device = Device.objects.get(name = hostname)
        return device
    except Exception as e:
        logger.error("Cannot get device. Error is: ".format(e))
        return None


def parseQuery(parser, query):
    ''' Tries to parse command in output 
        
        Returns: a tuple: (status: bool, message: string)
    '''
    try:
        command = query['Command']
        data = query['Data']
        hostname = query['Hostname']
    except Exception as e:
        logger.error("One or all params in query failed. Detail: {}".format(e))
        return(False, "Cannot parse a query - check all parameters")

    device = _getDevice(hostname)

    if device == None:
        return (False, "Not found device by hostname: {}".format(hostname))

    # Get Device Vendor (by platform or type)
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

        if result:
            # Process It!
            return processFuncton(device, result)
        else:
            return (False, "Cannot parse a command output - check template or command")
    else:
            logger.warning("Cannot found a process function. Info: parserAgrs {} Device {}".format(attrs, device))
            return (False, "Function for process this command or for this vendor is not implemented yet =(")


def syncInterfaces(device, interfaces):
    return (False, "Not implemented")


def syncInventory(device, invenory):
    ''' Syncing Inventory in NetBox

        Returns: a tuple: (status: bool, message: string)
    '''
    isChanged = False

    for item in invenory:
        # TODO: 
        name = item['Name']
        descr = item['Descr']
        pid = item['PartID']
        serial = item['Serial']

        # Check if manufacturer is present
        if 'Vendor' in item.keys():
            if item['Vendor']:
                manufacturer = _getOrAddVendor(item['Vendor'])
            else:
                manufacturer = None
        else:
                manufacturer = device.device_type.manufacturer

        # Check, if this item exists (by device, name and serial)
        item = InventoryItem.objects.filter(device = device, name = name, serial = serial)
        if item:
           logger.info("Device {} alredy have a item {}".format(device.name, name))
           continue
        else:
            logger.info("Tries to add a item {} on device {}".format(name, device.name))
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
                logger.warning("Error to save Inventory item with name {} to device {}. Error is {}".format(name, device.name, e))
    if isChanged:
        return (True, "Device {} synced succesfully".format(device.name))
    else:
        return {False, "Device {} was not synced. May be all items alredy exists?".format(device.name)}



