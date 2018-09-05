from django.contrib import admin

from django.contrib.auth.models import Group
from django.forms import ModelForm, ModelChoiceField
from django_select2.forms import Select2Widget, HeavySelect2Widget
from .models import Company, Tester, Activity, Network, VirtualMachine, TesterIpAddress
admin.site.site_header = admin.site.index_title = 'Pannello di gestione'
admin.site.site_title = "Virtual Platform for Penetration Testing"
admin.site.site_url = None

class NetworkInlineForm(ModelForm):
    ip = ModelChoiceField(queryset=TesterIpAddress.objects.all(), empty_label="DHCP", required=False)
    class Meta:
        model = VirtualMachine.network.through
        fields = ("net", "vm", 'ip',)

class NetworkInline(admin.StackedInline):
    model = VirtualMachine.network.through
    extra = 1
    form = NetworkInlineForm

    def __init__(self, parent_model, admin_site):
        super(NetworkInline, self).__init__(parent_model, admin_site)



class VirtualMachineAdmin(admin.ModelAdmin):
    fields = ("activity", "name", "os", "ram", "cpu", )
    list_display = ("activity", "name", "os", "ram", "cpu", )
    inlines = [NetworkInline]

    def has_change_permission(self, request, obj=None):
        if obj and obj.px_has_vm_been_created():
            return False
        else:
            return super(VirtualMachineAdmin, self).has_change_permission(request, obj)

class IPAddressAdmin(admin.StackedInline):
    model = TesterIpAddress
    extra = 1
    fields = ("ip", "cidr", "gateway")

class TesterAdmin(admin.ModelAdmin):
    fields = ("tester_identifier", "name", "company", "user",)
    list_display = ("tester_identifier", "name", "company", )
    inlines = [IPAddressAdmin]

class VmInlineAdd(admin.TabularInline):
    fields = ("name", "os", "ram", "cpu",)
    model = VirtualMachine
    extra = 1
    show_change_link = True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return obj is None



class ActivityAdmin(admin.ModelAdmin):
    fields = ("activity_identifier", "target_application_identifier", "target_application_name", "testers", )
    list_display = ("activity_identifier", "target_application_identifier", "target_application_name")
    inlines = [VmInlineAdd]

class NetworkAdminForm(ModelForm):
    class Meta:
        model = Network
        fields = ("network_description", "bridge_name",)
        widgets = {
            "bridge_name": HeavySelect2Widget(data_view="pxe_networks", attrs={
                'data-placeholder': 'Reti disponibili',
                'data-width':'150px'
            })
        }

class NetworkAdmin(admin.ModelAdmin):
    fields = ("network_description", "bridge_name",)
    list_display = ("network_description", "bridge_name",)
    form = NetworkAdminForm

class TesterIpAddressAdmin(admin.ModelAdmin):
    list_display = fields = ("ip", "cidr", "gateway" ,"tester")

admin.site.unregister(Group)
admin.site.register(Company)
admin.site.register(Tester, TesterAdmin)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(Network, NetworkAdmin)
admin.site.register(VirtualMachine, VirtualMachineAdmin)
admin.site.register(TesterIpAddress, TesterIpAddressAdmin)