"""CRM theme: seed-driven CSS variable overrides.

One entry point, so the www page and the API both derive the palette from a
single cached settings read.
"""


def get_theme_css(settings=None):
    """The <style> body for the CRM page, or '' when no seed is configured."""
    from upande_crm.theme import tokens

    if settings is None:
        from upande_crm.api.settings import get_settings

        settings = get_settings()

    return tokens.get_theme_css(settings)


def get_tokens(settings=None):
    from upande_crm.theme import tokens

    if settings is None:
        from upande_crm.api.settings import get_settings

        settings = get_settings()

    return tokens.get_tokens(settings)
