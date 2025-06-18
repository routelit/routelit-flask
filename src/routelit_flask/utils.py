import importlib.resources as resources


def get_default_static_path() -> str:
    static_path = resources.files("routelit").joinpath("static")
    return str(static_path)


def get_default_template_path() -> str:
    template_path = resources.files("routelit").joinpath("templates")
    return str(template_path)
