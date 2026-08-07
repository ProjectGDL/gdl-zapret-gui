
class ServiceError(RuntimeError):
    pass

class Service:
    
    def __init__(self, *args, **kwargs):
        raise ServiceError(
            "Service удалён. Используйте DaemonClient из gdl_zapret.client."
        )
