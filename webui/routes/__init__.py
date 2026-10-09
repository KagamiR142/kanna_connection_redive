def register_routes(router):
    from .admin_ops import register as register_admin_ops
    from .auth import register as register_auth
    from .member import register as register_member
    from .panel import register as register_panel

    register_auth(router)
    register_member(router)
    register_admin_ops(router)
    register_panel(router)
