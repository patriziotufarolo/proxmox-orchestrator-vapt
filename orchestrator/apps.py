from django.apps import AppConfig



class OrchestratorConfig(AppConfig):
    name = 'orchestrator'
    verbose_name = 'VPPT'

    def ready(self):
        import orchestrator.utils
        import jet.utils
        jet.utils.get_menu_items = orchestrator.utils.get_menu_items
