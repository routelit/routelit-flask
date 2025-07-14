import importlib.resources as resources
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

from flask import (
    Flask,
    Response,
    jsonify,
    make_response,
    render_template,
    request,
    send_from_directory,
    stream_with_context,
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

RunMode = Literal["prod", "dev_client", "dev_components"]
"""
The run mode for the RouteLitFlaskAdapter.

- `prod`: Production mode.
- `dev_client`: Development mode for the client.
- `dev_components`: Development mode for the components.
"""


class RunModeEnum(Enum):
    PROD = "prod"
    DEV_CLIENT = "dev_client"
    DEV_COMPONENTS = "dev_components"


class RouteLitFlaskAdapter:
    """
    A Flask adapter for the RouteLit framework, enabling seamless integration of RouteLit's reactive UI components with Flask web applications.
    """

    def __init__(
        self,
        routelit: RouteLit,
        *,
        static_path: Optional[str] = None,
        template_path: str = get_default_template_path(),
        run_mode: RunMode = "prod",
        local_frontend_server: Optional[str] = None,
        local_components_server: Optional[str] = None,
        cookie_config: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize the RouteLitFlaskAdapter.
        - When run_mode="prod", no need to specify local_frontend_server and local_components_server.
        - When run_mode="dev_client", you need to specify local_frontend_server.
        - When run_mode="dev_components", you need to specify local_components_server.

        Args:
            routelit (RouteLit): The RouteLit instance.
            static_path (Optional[str]): The path to the static js/css assets are.
            template_path (str): The path to the index.html template file. Default is in routelit package, so no need to specify.
            run_mode (RunMode): The run mode. Example: "prod", "dev_client", "dev_components".
            local_frontend_server (Optional[str]): The local vite frontend server. Example: "http://localhost:5173".
            local_components_server (Optional[str]): The local vite components server. Example: "http://localhost:5174".
            cookie_config (Optional[dict[str, Any]]): The cookie configuration. Default is production cookie config.
        """
        self.routelit = routelit
        self.static_path = static_path or get_default_static_path()
        self.template_path = template_path
        self.run_mode = run_mode
        self.local_frontend_server = local_frontend_server
        self.local_components_server = local_components_server
        self.cookie_config = cookie_config or production_cookie_config if run_mode == "prod" else {}

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

    def _handle_get_request(self, view_fn: ViewFn, request: FlaskRLRequest, **kwargs: Any) -> Response:
        rl_response = self.routelit.handle_get_request(view_fn, request, **kwargs)
        response = make_response(
            render_template(
                "index.html",
                ROUTELIT_DATA=rl_response.get_str_json_elements(),
                PAGE_TITLE=rl_response.head.title,
                PAGE_DESCRIPTION=rl_response.head.description,
                RUN_MODE=self.run_mode,
                LOCAL_FRONTEND_SERVER=self.local_frontend_server,
                LOCAL_COMPONENTS_SERVER=self.local_components_server,
                default_vite_assets=self.routelit.default_client_assets(),
                vite_assets=self.routelit.client_assets(),
            )
        )
        response.set_cookie(COOKIE_SESSION_KEY, request.get_session_id(), **self.cookie_config)
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
            return self._handle_get_request(view_fn, req, **kwargs)

    def stream_response(
        self,
        view_fn: ViewFn,
        should_inject_builder: Optional[bool] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        req = FlaskRLRequest(request)
        if req.method == "POST":
            resp = Response(
                stream_with_context(
                    self.routelit.handle_post_request_stream_jsonl(view_fn, req, should_inject_builder, *args, **kwargs)
                ),
                mimetype="text/event-stream",
            )
            resp.headers["Content-Type"] = "application/jsonlines"
            return resp
        else:
            return self._handle_get_request(view_fn, req, **kwargs)
