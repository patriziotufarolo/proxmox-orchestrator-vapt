from django.shortcuts import render

from django.conf import settings
from django.views.generic.list import BaseListView
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from orchestrator.proxmox import ProxmoxConnector, ProxmoxNotConnectedException
from django.contrib.auth.mixins import LoginRequiredMixin


class PxeNetworks(LoginRequiredMixin, BaseListView):

    def get(self, request, *args, **kwargs):
        try:
            bridges = ProxmoxConnector().get_interfaces_list()
            return JsonResponse({
                'results': [
                    {
                        'text': obj.get('iface'),
                        'id': obj.get('iface'),
                    }
                    for obj in bridges if obj.get('iface')
                ],
                'more': False
            })
        except ProxmoxNotConnectedException:
            return JsonResponse({
                'results': [
                    {
                        'text': "Could not connect to Proxmox!",
                        'disabled': True
                    }
                ],
                'more': False
            }, status=500)
