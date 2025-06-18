import importlib.resources as resources
from pathlib import Path
from typing import Any, Optional

from flask import (
    Flask,
    Response,
    jsonify,
    make_response,
    render_template,
    request,
    send_from_directory,
)
from jinja2 import ChoiceLoader, FileSystemLoader
from routelit import COOKIE_SESSION_KEY, AssetTarget, RouteLit, ViewFn  # type: ignore[import-untyped]

from .json_encoder import CustomJSONProvider
from .request import FlaskRLRequest
from .utils import (
    get_default_static_path,
    get_default_template_path,
)

production_cookie_config = {
    "secure": True,
    "samesite": "none",
    "httponly": True,
    "max_age": 60 * 60 * 24 * 1,  # 1 day
}


class RouteLitFlaskAdapter:
    """
    A Flask adapter for the RouteLit framework, enabling seamless integration of RouteLit's reactive UI components with Flask web applications.
    """

    def __init__(
        self,
        routelit: RouteLit,
        *,
        static_path: str = get_default_static_path(),
        template_path: str = get_default_template_path(),
        is_dev: bool = False,
        is_dev_frontend: bool = False,
        local_frontend_server: str = "http://localhost:5173",
        local_elements_server: str = "http://localhost:5174",
    ):
        self.routelit = routelit
        self.static_path = static_path
        self.template_path = template_path
        self.debug = is_dev_frontend
        self.local_frontend_server = local_frontend_server
        self.cookie_config = production_cookie_config if not is_dev else {}
        self.local_elements_server = local_elements_server

    @classmethod
    def configure_static_assets(cls, flask_app: Flask, asset_target: AssetTarget) -> None:
        package_name, path = asset_target["package_name"], asset_target["path"]
        assets_path = resources.files(package_name).joinpath(path)
        flask_app.add_url_rule(
            f"/routelit/{package_name}/<path:filename>",
            endpoint=f"assets_static_{package_name}",
            view_func=lambda filename: send_from_directory(str(assets_path), filename),
        )

    def configure(self, flask_app: Flask) -> "RouteLitFlaskAdapter":
        """
        Configure the Flask application to use the RouteLitFlaskAdapter.

        Args:
            flask_app: The Flask application to configure.

        Returns:
            The RouteLitFlaskAdapter instance.
        """
        # Set custom JSON encoder
        flask_app.json_provider_class = CustomJSONProvider

        for static_path in self.routelit.get_builder_class().get_client_resource_paths():
            self.configure_static_assets(flask_app, static_path)

        assets_path = Path(self.static_path) / "assets"
        flask_app.add_url_rule(
            "/routelit/assets/<path:filename>",
            endpoint="routelit_assets_static",
            view_func=lambda filename: send_from_directory(str(assets_path), filename),
        )

        # configure jinja templates for index.html
        current_loader = flask_app.jinja_loader
        if isinstance(current_loader, ChoiceLoader):
            # Append to the list of loaders
            current_loader.loaders.append(FileSystemLoader(self.template_path))  # type: ignore[attr-defined]
        else:
            # Wrap current loader and new one in a ChoiceLoader
            flask_app.jinja_loader = ChoiceLoader([current_loader, FileSystemLoader(self.template_path)])  # type: ignore[list-item]
        return self

    def _handle_get_request(self, view_fn: ViewFn, request: FlaskRLRequest, *args: Any, **kwargs: Any) -> Response:
        response = self.routelit.handle_get_request(view_fn, request, *args, **kwargs)
        response = make_response(
            render_template(
                "index.html",
                ROUTELIT_DATA=response.get_str_json_elements(),
                PAGE_TITLE=response.head.title,
                PAGE_DESCRIPTION=response.head.description,
                DEBUG=self.debug,
                LOCAL_FRONTEND_SERVER=self.local_frontend_server,
                LOCAL_ELEMENTS_SERVER=self.local_elements_server,
                default_vite_assets=self.routelit.default_client_assets(),
                vite_assets=self.routelit.client_assets(),
            )
        )
        response.set_cookie(COOKIE_SESSION_KEY, request.get_session_id(), **self.cookie_config)  # type: ignore[arg-type]
        return response

    def response(
        self,
        view_fn: ViewFn,
        should_inject_builder: Optional[bool] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """
        Handle a request and return a response.

        Args:
            view_fn: The view function to handle the request.
            should_inject_builder: Whether to inject the builder into the request.
            *args: Additional arguments to pass to the view function.
            **kwargs: Additional keyword arguments to pass to the view function.

        Returns:
            A Flask response.
        """
        req = FlaskRLRequest(request)
        if req.method == "POST":
            actions = self.routelit.handle_post_request(view_fn, req, should_inject_builder, *args, **kwargs)
            return jsonify(actions)
        else:
            return self._handle_get_request(view_fn, req, should_inject_builder, *args, **kwargs)
