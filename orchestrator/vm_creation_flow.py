from .models import VirtualMachine
import taskflow.engines
from taskflow.patterns import linear_flow as lf
from taskflow import task
from .proxmox import ProxmoxConnector
from django.utils.text import slugify

"""
PRE : Ensure pool exists, if not create related pool (bind this to the parent activity)
1 - Clone template into resource pool
2 - Set RAM
3 - Set CPU
4 - Assign networks
5 - Prepare cloud-init image
6 - Attach cloud-init image to vm
7 - Create additional storage
8 - Attach additional storage
9 - Save vmid in this object
"""



class CreatePool(task.Task):
    def execute(self, vm: VirtualMachine, *args, **kwargs):
        if not vm.activity.px_has_pool_been_created():
            return ProxmoxConnector().create_resource_pool(
                poolid=slugify(vm.activity.activity_identifier).upper(),
                comment='{activity_identifier} - {target_application_identifier} {target_application_name}'.format(
                    activity_identifier=vm.activity.activity_identifier,
                    target_application_identifier=vm.activity.target_application_identifier,
                    target_application_name=vm.activity.target_application_name
                )
            )
        return slugify(vm.activity.activity_identifier).upper()

    def rollback(self, vm: VirtualMachine, *args, **kwargs):
        return ProxmoxConnector().delete_resource_pool(poolid=slugify(vm.activity.activity_identifier))

class CloneTemplate(task.Task):
    def execute(self, vm: VirtualMachine, *args, **kwargs):
        vm.px_create_vm() # # @todo Add pool returned above here

class SetRAM(task.Task):
    def execute(self, vm: VirtualMachine, *args, **kwargs):
        vm.set
        pass

class SetCPU(task.Task):
    def execute(self, vm: VirtualMachine, *args, **kwargs):
        pass

class AssignNetworks(task.Task):
    def execute(self, vm: VirtualMachine, *args, **kwargs):
        pass

class PrepareCloudInit(task.Task):
    pass

class AttachCloudInit(task.Task):
    pass

class CreateEvidenceStorage(task.Task):
    pass

class AttachEvidenceStorage(task.Task):
    pass


vm_creation_flow = lf.Flow('vm_creation_flow').add(
    CreatePool()
)