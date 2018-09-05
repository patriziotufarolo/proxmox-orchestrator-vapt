from django.conf import settings
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from django.core.cache import cache
from requests.exceptions import ConnectionError, ConnectTimeout
from singletonify import singleton
import random
import logging
logger = logging.getLogger("orchestrator")


class ProxmoxDriverException(Exception):
    pass


class ProxmoxNotConnectedException(ProxmoxDriverException):
    pass


def if_reachable(func):
    def wrapper(*args, **kwargs):
        if cache.get_or_set("proxmox_reachable", args[0].reachable, 15) is True:
            return func(*args, **kwargs)
        else:
            raise ProxmoxNotConnectedException
    return wrapper


def if_vm_exists(arg_name, node=settings.PROXMOX_NODE_NAME):
    def first_level_wrapper(func):
        def sec_level_wrapper(*args, **kwargs):
            if not arg_name in kwargs:
                raise ValueError("{} not specified".format(arg_name))
            if args[0].nodes(node).qemu(kwargs[arg_name]).get():
                return func(*args, **kwargs)
            else:
                raise ProxmoxDriverException
        return sec_level_wrapper
    return first_level_wrapper


def if_network_interface_exists(arg_name, type='bridge', node=settings.PROXMOX_NODE_NAME):
    def first_level_wrapper(func):
        def sec_level_wrapper(*args, **kwargs):
            if not arg_name in kwargs:
                raise ValueError("{} not specified".format(arg_name))
            if [1 for it in args[0].get_interfaces_list(type=type, node=node) if it['iface'] == kwargs[arg_name]]:
                return func(*args, **kwargs)
            else:
                raise ProxmoxDriverException("Network does not exists")
        return sec_level_wrapper
    return first_level_wrapper


def if_vm_has_network(vm_arg_name, net_arg_name, node=settings.PROXMOX_NODE_NAME):
    def first_level_wrapper(func):
        def sec_level_wrapper(*args, **kwargs):
            if not vm_arg_name in kwargs:
                raise ValueError("{} not specified".format(vm_arg_name))
            if not net_arg_name in kwargs:
                raise ValueError("{} not specified".format(net_arg_name))
            vmid = kwargs[vm_arg_name]
            network = kwargs[net_arg_name]
            if network in args[0].nodes(node).qemu(vmid).config.get():
                return func(*args, **kwargs)
            else:
                raise ProxmoxDriverException("VM {vm} has not a nic named {network}".format(vm=vmid,
                                                                                            network=network))
        return sec_level_wrapper
    return first_level_wrapper

def if_resource_pool_exists(rpool_arg_name:str, exists:bool):
    def first_level_wrapper(func):
        def sec_level_wrapper(*args, **kwargs):
            if not rpool_arg_name in kwargs:
                raise ValueError("{} not specified".format(rpool_arg_name))
            rpool = kwargs[rpool_arg_name]
            if (rpool in [pool.get('poolid') for pool in args[0].pools.get()]) == exists:
                return func(*args, **kwargs)
            else:
                raise ProxmoxDriverException("Pool {poolid} {exists}".format(poolid=rpool, exists="doesn't exist" if exists else "already exists"))
        return sec_level_wrapper
    return first_level_wrapper

def trap_resource_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ResourceException as e:
            raise ProxmoxDriverException("Resource not found or already exists") from e
    return wrapper


@singleton
class ProxmoxConnector(ProxmoxAPI):

    def __init__(self):
        """Do nothing"""

    def connection_attempt(self):
        ProxmoxAPI.__init__(self, settings.PROXMOX_URL, user=settings.PROXMOX_USER, password=settings.PROXMOX_PWD,
                            verify_ssl=settings.PROXMOX_VERIFY_SSL, port=getattr(settings, "PROXMOX_PORT", 8006))

    def reachable(self):
        try:
            self.connection_attempt()
            return True
        except (ConnectionError,
                ConnectionRefusedError,
                ConnectionAbortedError,
                ConnectionResetError,
                ConnectTimeout):
            return False

    @if_reachable
    @trap_resource_exception
    def get_interfaces_list(self, node=settings.PROXMOX_NODE_NAME, type='bridge'):
        return cache.get_or_set('network_bridges_{node}'.format(node=node), self.nodes(node).network.get(type=type), 20)

    @if_reachable
    @trap_resource_exception
    def get_vms(self, node=settings.PROXMOX_NODE_NAME):
        return cache.get_or_set('vms_{node}'.format(node=node), self.nodes(node).qemu.get())

    @if_reachable
    @trap_resource_exception
    def get_vm(self, vmid: str, node: str=settings.PROXMOX_NODE_NAME):
        return cache.get_or_set('vm_{vmid}'.format(vmid=vmid, node=node), self.nodes(node).qemu(vmid).get(),10)

    @if_reachable
    @trap_resource_exception
    def clone_vm(self, name, template, node=settings.PROXMOX_NODE_NAME, pool=None):
        next_id = self.cluster.nextid.get()
        self.nodes(node).qemu(template).clone.create(newid=next_id, name=name, pool=pool)
        return next_id

    @if_reachable
    @trap_resource_exception
    def assign_ram(self, vmid, maxram, minram=settings.PROXMOX_VM_MIN_RAM, node=settings.PROXMOX_NODE_NAME):
        self.nodes(node).qemu(vmid).config.post(balloon=minram, memory=maxram)
        return vmid

    @if_reachable
    @trap_resource_exception
    def set_cores(self, vmid, cores, node=settings.PROXMOX_NODE_NAME):
        self.nodes(node).qemu(vmid).config.post(cores=cores)
        return vmid

    @if_reachable
    @trap_resource_exception
    @if_vm_exists("vmid")
    def delete_vm(self, vmid=None, node=settings.PROXMOX_NODE_NAME):
        self.nodes(node).qemu(vmid).delete()
        return True

    @if_reachable
    @trap_resource_exception
    @if_vm_exists("vmid")
    @if_network_interface_exists("bridge")
    def attach_net_to_vm(self, vmid=None, bridge=None, node=settings.PROXMOX_NODE_NAME):
        current_config = self.nodes(node).qemu(vmid).config.get()
        nets = [int(item.replace('net', '')) for item in current_config if item.startswith("net")]
        if not nets:
            next_net = 0
        else:
            next_net = max(nets)+1
        int_number = next_net
        next_net = "net" + str(next_net)
        mac_address = ":"\
            .join(['52', '54', '00'] + [str("%0x" % random.randint(0, 0xFFFFFF))[i:i+2] for i in range(0, 3)])\
            .upper()
        self.nodes(node).qemu(vmid).config.post(**{
            next_net: "model=virtio,bridge={bridge},macaddr={mac_address}"
                                                .format(bridge=bridge, mac_address=mac_address)
        })
        return "eth" + str(int_number), mac_address

    @if_reachable
    @trap_resource_exception
    @if_vm_exists("vmid")
    @if_vm_has_network("vmid", "network")
    def detach_net_from_vm(self, vmid: int=None, network: str='', node: str=settings.PROXMOX_NODE_NAME):
        self.nodes(node).qemu(vmid).config.post(delete=network)
        return True

    @if_reachable
    @trap_resource_exception
    @if_resource_pool_exists("poolid", False)
    def create_resource_pool(self, poolid="", comment=""):
        self.pools.create(poolid=poolid, comment=comment)
        return poolid

    @if_reachable
    @trap_resource_exception
    @if_resource_pool_exists("poolid", True)
    def delete_resource_pool(self, poolid: str = ""):
        self.pools.delete(poolid)
        return True

    @if_reachable
    @trap_resource_exception
    def get_resource_pool(self, poolid: str):
        return self.pools(poolid).get()

    def cloudinit_prepare(self, ip, cidr, root_pwd):
        pass

    @if_reachable
    @trap_resource_exception
    def attach_storage(self):
        raise NotImplemented

    @if_reachable
    @trap_resource_exception
    def detach_storage(self):
        raise NotImplemented

    @if_reachable
    @trap_resource_exception
    def create_storage(self):
        raise NotImplemented

    @if_reachable
    @trap_resource_exception
    def get_vm_desktop(self, node, vm_id):
        raise NotImplemented
