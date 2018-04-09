from dcim.models import Device, Interface, InterfaceConnection, InventoryItem, Manufacturer
from ipam.models import IPAddress
from netaddr import IPNetwork

from dcim.constants import *
from collector.settings import *
import logging
import logging.config
import clitable
import re

#DEBUG
import pdb

logger = logging.getLogger('collector')
logging.config.dictConfig(LOGGING_CONFIG)


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
    '''
        Syncing interfaces
        interfaces: list of lists

        Vars:
        interface['NAME'] - Name of interface
        interface['MAC'] - Mac-Address
        interface['IP'] - List of IP-address
        interface['MTU'] - MTU
        interface['DESCR'] - Description of interfaces
        interface['TYPE'] - Physical type of interface (Default 1G-cooper - cannot get from linux)
        interface['STATE'] - UP|DOWN

        Returns: a tuple: (status: bool, message: string)
    '''
    for interface in interfaces:
        name = interface.get('NAME')
        mac = interface.get('MAC')
        ips = interface.get('IP')
        mtu = interface.get('MTU')
        description = interface.get('DESCR')
        iface_type = interface.get('TYPE')
        iface_state = interface.get('STATE')
        # Updated interface counter
        count=0

        # Get interface from device - for check if exst
        ifaces = device.interfaces.filter(name = name)
        if ifaces:
            logger.info("Interface {} is exist on device {}, will update".format(name, device.name))
            # TODO: I think, that only one item will be in filter, but need to add check for it
            iface = ifaces[0]
        else:
            logger.info("Interface {} is not exist on device {}, will create new".format(name, device.name))
            iface = Interface(name = name)
            iface.device = device

        logger.info("Will be save next parameters: Name:{name}, MAC: {mac}, MTU: {mtu}, Descr: {description}".format(
                                                    name=name, mac=mac, mtu = mtu, description=description))
        if description:
            iface.description = description
        iface.mac_address = mac

        # MTU should be less 32767
        if int(mtu) < 32767:
            iface.mtu = mtu
        # TODO: remake this default parameters
        iface.enabled =  True
        iface.form_factor = IFACE_FF_1GE_FIXED

        try:
            iface.save()
        except Exception as e:
            logger.error("Cannot save interface, error is {}".format(e))
        else:
            count+=1
            logger.info("Interface {} was succesfully saved".format(name, device.name))

        # IP syncing
        if len(ips) > 0:
            for address in ips:
                addr = IPAddress()
                addr.interface = iface
                # TODO: Without v6 support yet
                addr.address = IPNetwork(address)
                addr.save()

    if count==0:
        return(False, "Can't update any inerface, see a log for details")
    return(True, "Succesfully updated {} interfaces".format(count))

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
        # Additional field to process name
        case = item['Case']

        # Name or Case?
        if not name:
            name = case

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



