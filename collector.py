from dcim.models import Device, Interface, InventoryItem, Manufacturer, Platform, DeviceRole
from ipam.models import IPAddress
from virtualization.models import Cluster, VirtualMachine
from netaddr import IPNetwork
from dcim.constants import *
from collector.settings import *
from math import pow
import ast
import logging
import clitable
import re

# Init logginig settings
logger = logging.getLogger('collector')
logging.config.dictConfig(LOGGING_CONFIG)


def _get_process_function(parser, attrs):
    """ 'Velosiped' for return function name from index file
        I believe, will possible make it as another simple method
        But now I cannot know how =\

        :param parser: cli_table object
        :param attrs: dict {"Command": "some_command", "Vendor": some_vendor}
        :return: function or None
    """
    index = parser.index.index
    keys = index.header.values
    out = [dict(zip(keys, row)) for row in index]
    command = attrs['Command']
    vendor = attrs['Vendor']

    for item in out:
        if re.match(item['Vendor'], vendor) and re.match(item['Command'], command):
            # Tries to find function to process this command
            func = globals().get(item['Function'])
            logger.info("Function is %s", func)
            return func


def _get_or_add_vendor(vendor_name):
    """ Check if this Vendor present on Netbox

        TODO: Add a save() check

        :param vendor_name: String
        :rtype: object NetBox Manufacturer
    """
    man = Manufacturer.objects.filter(name__icontains=vendor_name)
    if man:
        # Get only first...
        logger.info("Found a vendor {} - return it".format(vendor_name))
        return man[0]
    else:
        logger.info("Create a new vendor")
        man = Manufacturer()
        man.name = vendor_name
        # Replace any non-word character to dash
        man.slug = re.sub("\W+", "-", vendor_name)
        man.save()
        return man


def _get_device(hostname):
    """ Get device object from Netbox

    :param hostname: String hostname
    :return:  object NetBox Device
    """
    try:
        device = Device.objects.get(name=hostname)
        return device
    except Exception as e:
        logger.error("Cannot get device. Error is: ".format(e))
        return None


def init_parser():
    """
    Init CliTable index and templates
        This function should be call first, before parsing

        :return: cliTable object or None
    """
    try:
        parser = clitable.CliTable('index', TEMPLATES_DIRECTORY)
        logger.info("Collector module loads: Im Alive!!!")
    except Exception as e:
        logger.error("Problem with parser init - check index file and templates directory. Error is %s", e)
        return None
    return parser


def parse_query(parser, query):
    """ Parsing command output

    :param parser: clitable object
    :param query: Dict
    :return: Bool,String
    """
    try:
        command = query['Command']
        data = query['Data']
        hostname = query['Hostname']
    except Exception as e:
        logger.error("One or all params in query failed. Detail: {}".format(e))
        return False, "Cannot parse a query - check all parameters"

    device = _get_device(hostname)

    if not device:
        return False, "Not found device by hostname: {}".format(hostname)

    # Get Device Vendor (by platform or type)
    if device.platform:
        vendor = device.platform.name
    else:
        vendor = device.device_type.manufacturer.name

    attrs = {"Command": command, "Vendor": vendor}

    process_function = _get_process_function(parser, attrs)

    if process_function:
        # Its parsing time!
        try:
            parser.ParseCmd(data, attrs)
        except Exception as e:
            return False, "Error while parsing. {}".format(e)
        # I will use a named indexes to prevent order changes
        keys = parser.header.values
        result = [dict(zip(keys, row)) for row in parser]

        if result:
            # Process It!
            return process_function(device, result)
        else:
            return False, "Cannot parse a command output - check template or command"
    else:
        logger.warning("Cannot found a process function. Parser Agrs: {} Device: {}".format(attrs, device))
        return False, "Function for process this command or for this vendor is not implemented yet =("


def sync_interfaces(device, interfaces):
    """ Syncing interfaces

        :param device: object NetBox Device
        :param interfaces: list of lists

        interfaces:
            interface['NAME'] - Name of interface
            interface['MAC'] - Mac-Address
            interface['IP'] - List of IP-address
            interface['MTU'] - MTU
            interface['DESCR'] - Description of interfaces
            interface['TYPE'] - Physical type of interface (Default 1G-cooper - cannot get from linux)
            interface['STATE'] - UP|DOWN

        :return: status: bool, message: string
    """
    # Updated interface counter
    count = 0
    for interface in interfaces:
        name = interface.get('NAME')
        mac = interface.get('MAC')
        ips = interface.get('IP')
        mtu = interface.get('MTU')
        description = interface.get('DESCR')
        iface_type = interface.get('TYPE')
        iface_state = interface.get('STATE')

        # Get interface from device - for check if exist
        ifaces = device.interfaces.filter(name=name)
        if ifaces:
            logger.info("Interface {} is exist on device {}, will update".format(name, device.name))
            # TODO: I think, that only one item will be in filter, but need to add check for it
            iface = ifaces[0]
        else:
            logger.info("Interface {} is not exist on device {}, will create new".format(name, device.name))
            iface = Interface(name=name)
            iface.device = device

        logger.info("Will be save next parameters: Name:{name}, MAC: {mac}, MTU: {mtu}, Descr: {description}".format(
            name=name, mac=mac, mtu=mtu, description=description))
        if description:
            iface.description = description
        iface.mac_address = mac

        # MTU should be less 32767
        if int(mtu) < MAX_MTU:
            iface.mtu = mtu
        # TODO: remake this default parameters
        iface.enabled = True
        iface.form_factor = IFACE_FF_1GE_FIXED

        try:
            iface.save()
        except Exception as e:
            logger.error("Cannot save interface, error is {}".format(e))
        else:
            count += 1
            logger.info("Interface {} was succesfully saved".format(name, device.name))

        # IP syncing
        if len(ips) > 0:
            for address in ips:
                addr = IPAddress()
                addr.interface = iface
                # TODO: Need a test ipv6 addresses
                addr.address = IPNetwork(address)
                addr.save()

    if count == 0:
        return False, "Can't update any interface, see a log for details"
    return True, "Successfully updated {} interfaces".format(count)


def sync_inventory(device, inventory):
    """ Syncing Inventory in NetBox

        :return: status: bool, message: string
    """
    is_changed = False

    for item in inventory:
        name = item['Name']
        descr = item['Descr']
        pid = item['PartID']
        serial = item['Serial']
        # Additional field to process name or device type
        case = item['Case']

        # Name or Case?
        if not name:
            name = case

        # Check if manufacturer is present
        if 'Vendor' in item.keys():
            if item['Vendor']:
                manufacturer = _get_or_add_vendor(item['Vendor'])
            else:
                manufacturer = None
        else:
            manufacturer = device.device_type.manufacturer

        # Check, if this item exists (by device, name and serial)
        item = InventoryItem.objects.filter(device=device, name=name, serial=serial)
        if item:
            logger.info("Device {} already have a item {}".format(device.name, name))
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
                is_changed = True
            except Exception as e:
                logger.warning(
                    "Error to save Inventory item with name {} to device {}. Error is {}".format(name, device.name, e))
    if is_changed:
        return True, "Device {} synced successfully".format(device.name)
    else:
        return False, "Device {} was not synced. May be all items already exists?".format(device.name)


def sync_vms(device, vms):
    """ Syncing VirtualMachines from device

    :param device:
    :param vms:
    :return:
    """
    if not vms:
        return False, "There is no VM to update"

    # TODO: cluster tenancy, role and platform
    cluster = device.cluster
    # By default all VMS - is a linux VMs
    platform = Platform.objects.get(name='Linux')
    # And server roles
    role = DeviceRole.objects.get(name='Server')

    # TODO: Need a get vm disks from vm objects
    for vm_instance in vms:
        pass

    if cluster:
        for vm_data in vms:
            vm = VirtualMachine.objects.filter(name=vm_data['NAME'])
            if vm:
                logger.info("VM {} already exists. Will update this VM".format(vm_data['NAME']))
                vm = vm[0]
            else:
                logger.info("VM {} is not exist. Will create new VM".format(vm_data['NAME']))
                vm = VirtualMachine()
                vm.name = vm_data['NAME']

            vm.cluster = cluster
            vm.platform = platform
            vm.role = role
            vm.memory = int(vm_data['MEM'])/1024 # its a simple method - we need a MB
            vm.vcpus = int(vm_data['VCPU'])

            # get disks
            names = vm_data['DISKNAMES']
            sizes = vm_data['DISKSIZES']
            paths = vm_data['DISKPATHS']

            # TODO: govnocode style - rewrite it for pythonic true way
            disks = []
            total_size = 0
            for name in names:
                name = ast.literal_eval(name)
                temp = name.copy()
                index = temp.get('diskindex')
                for size in sizes:
                    size = ast.literal_eval(size)
                    size_index = size.get('diskindex')
                    if size_index == index:
                        temp.update(size)
                for path in paths:
                    path = ast.literal_eval(path)
                    path_index = path.get('diskindex')
                    if path_index == index:
                        temp.update(path)
                disks.append(temp)
                del temp  # non-urgent

            logger.info("Disks is: {}, len is {}".format(disks, len(disks)))

            # Filling VM comments with Disk Section
            separator = "***\r\n"
            # saving comments
            try:
                comments = vm.comments.split(separator)[1]
            except:
                comments = vm.comments
            disk_string = ""
            # and adding disks
            for disk in disks:
                size = int(disk.get('size')) / pow(1024, 3)
                disk_string += "**Disk:** {}\t**Size:** {} GB\t**Path:** {}\n".format(disk.get('name'),
                                                                                      int(size),
                                                                                      disk.get('path'))
                total_size += size
            disk_string += separator
            vm.comments = disk_string + comments
            vm.disk = int(total_size)
            vm.save()
        return True, "VM successfully synced"
    else:
        return False, "Cannot determine cluster for device"
