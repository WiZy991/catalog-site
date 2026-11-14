"""Context processors for the partners (wholesale) section."""


def partner_desktop_viewport(request):
    """
    После авторизации в ЛК партнёра на мобильных показываем десктопную вёрстку:
    viewport width=1280 вместо device-width.
    Публичные страницы (витрина, логин, регистрация) остаются адаптивными.
    """
    force = False
    path = getattr(request, 'path', '') or ''
    user = getattr(request, 'user', None)

    if (
        path.startswith('/partners/')
        and user is not None
        and getattr(user, 'is_authenticated', False)
    ):
        public_prefixes = (
            '/partners/login',
            '/partners/register',
            '/partners/password-reset',
            '/partners/browse',
        )
        is_public = (
            path.rstrip('/') in ('/partners', '/partners/')
            or any(path.startswith(prefix) for prefix in public_prefixes)
        )
        if not is_public:
            if getattr(user, 'is_staff', False):
                force = True
            elif hasattr(user, 'partner_profile'):
                try:
                    force = bool(user.partner_profile.is_active)
                except Exception:
                    force = False

    return {'FORCE_PARTNER_DESKTOP': force}
