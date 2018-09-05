from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
import unicodedata
import re
from orchestrator.proxmox import ProxmoxConnector, ProxmoxDriverException
from .fields import IntegerRangeField


class Company(models.Model):
    name = models.CharField("Nome azienda", max_length=50)

    class Meta:
        verbose_name = "Azienda"
        verbose_name_plural = "Aziende"

    def __str__(self):
        return self.name


class Tester(models.Model):
    name = models.CharField("Nome completo", max_length=50)
    tester_identifier = models.CharField("Matricola", max_length=10)
    company = models.ForeignKey(Company, verbose_name="Azienda", on_delete=models.CASCADE, related_name="Testers")
    user = models.OneToOneField(User, verbose_name="Utenza portale", on_delete=models.CASCADE, related_name="Tester", null=True)

    def apx_has_user_been_created(self):
        return True

    def px_has_user_been_created(self):
        users = ProxmoxConnector().proxmox.access.users.get()

    def px_create_user(self):
        pass

    def px_delete_user(self):
        pass

    def __str__(self):
        return "[{tester_identifier}] {name}".format(
            tester_identifier=self.tester_identifier,
            name=self.name
        )


class TesterIpAddress(models.Model):
    ip = models.GenericIPAddressField("Indirizzo IP", protocol="IPv4")
    cidr = IntegerRangeField("CIDR", default=25, min_value=0, max_value=32)
    gateway = models.GenericIPAddressField("Gateway", protocol="IPv4", null=True, blank=True)
    tester = models.ForeignKey(Tester, null=False, related_name="ip", on_delete=models.CASCADE)

    def __str__(self):
        return "{ip}/{cidr}".format(ip=self.ip, cidr=self.cidr)

    class Meta:
        verbose_name = "Indirizzo IP"
        verbose_name_plural = "Indirizzi IP"


class Activity(models.Model):
    activity_identifier = models.CharField("Codice attivita", max_length=15)
    target_application_identifier = models.CharField("Codice Applicazione", max_length=10)
    target_application_name = models.CharField("Nome applicazione", max_length=50)
    testers = models.ManyToManyField(Tester, related_name="Attività")

    def px_has_pool_been_created(self):
        pool_id = slugify(self.activity_identifier).upper()
        try:
            ProxmoxConnector().get_resource_pool(pool_id)
            return True
        except ProxmoxDriverException:
            return False

    def px_has_authorizations_been_given(self):
        pass

    def px_sync_authorizations(self):
        pass

    def px_create_pool(self):
        if not self.px_has_pool_been_created():
            return ProxmoxConnector().create_resource_pool(
                poolid=slugify(self.activity_identifier).upper(),
                comment='{activity_identifier} - {target_application_identifier} {target_application_name}'.format(
                    activity_identifier=self.activity_identifier,
                    target_application_identifier=self.target_application_identifier,
                    target_application_name=self.target_application_name
                )
            )
        return slugify(self.activity_identifier).upper()

    def px_delete_pool(self):
        if not self.px_has_pool_been_created():
            return False
        else:
            return ProxmoxConnector().delete_resource_pool(
                poolid=slugify(self.activity_identifier).upper()
            )

    def __str__(self):
        return self.activity_identifier

    class Meta:
        verbose_name = verbose_name_plural = "Attività"


class Network(models.Model):
    network_description = models.CharField("Descrizione", max_length=20)
    bridge_name = models.CharField("Nome bridge", unique=True, max_length=5)

    class Meta:
        verbose_name = "Rete"
        verbose_name_plural = "Reti"

    def __str__(self):
        return self.network_description


class VMNet(models.Model):
    net = models.ForeignKey(Network, on_delete=models.CASCADE, verbose_name="Rete")
    vm = models.ForeignKey("VirtualMachine", on_delete=models.CASCADE, verbose_name="VM")
    ip = models.OneToOneField(TesterIpAddress, verbose_name="Indirizzo IP",
                              on_delete=models.SET_NULL, null=True, blank=True, unique=True)
    class Meta:
        unique_together = (("net", "vm",),)
        verbose_name = "Associazione reti"
        verbose_name_plural = "Associazioni reti"

    def __str__(self):
        return "{network} - {ip}".format(network=self.net, ip=self.ip if self.ip else "DHCP")


class VirtualMachine(models.Model):
    OSS = (
        ("Win7", "Windows 7"),
        ("Win10", "Windows 10"),
        ("Kali", "Kali Linux"),
    )
    name = models.CharField("Nome", max_length=50)
    os = models.CharField("Sistema operativo", choices=OSS, max_length=20)
    ram = IntegerRangeField("RAM (MB)", min_value=512, max_value=8192)
    cpu = IntegerRangeField("CPU", min_value=1, max_value=8)
    network = models.ManyToManyField(Network, verbose_name="Reti", related_name="vms", through=VMNet)
    activity = models.ForeignKey(Activity, verbose_name="Attività", related_name="vms", on_delete=models.CASCADE, null=True)
    vmid = models.CharField("VM ID", null=True, blank=True, max_length=7)

    def __str__(self):
        return "{activity} - {name}".format(name=self.name, activity=self.activity) if self.activity else self.name

    @property
    def hostname(self):
        hostname = str(self.name)
        hostname = unicodedata.normalize('NFKD', hostname).encode('ascii', 'ignore').decode('ascii')
        hostname = re.sub(r'[^\w\s-]', '', hostname).strip().lower()
        hostname = re.sub(r'[-\s]+', '-', hostname)
        hostname = re.sub(r'^[^a-z]*|[^a-z1-9]*?$', '', hostname)
        return mark_safe(hostname)

    def px_has_vm_been_created(self):
        if not self.vmid:
            return False
        else:
            try:
                ProxmoxConnector().get_vm(self.vmid)
                return True
            except ProxmoxDriverException:
                return False

    def px_create_vm(self):
        if not self.px_has_vm_been_created():
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
            
        else:
            return False

    def px_destroy_vm(self):
        pass

    class Meta:
        verbose_name = "Macchina virtuale"
        verbose_name_plural = "Macchine virtuali"