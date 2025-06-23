from unittest.mock import Mock, patch

import pytest
from flask import Flask
from jinja2 import ChoiceLoader
from routelit import AssetTarget, RouteLit

from routelit_flask.adapter import RouteLitFlaskAdapter
from routelit_flask.json_encoder import CustomJSONProvider
from routelit_flask.request import FlaskRLRequest


class TestRouteLitFlaskAdapter:
    @pytest.fixture
    def mock_routelit(self):
        """Create a mock RouteLit instance for testing."""
        mock_rl = Mock(spec=RouteLit)
        mock_builder = Mock()
        mock_builder.get_client_resource_paths.return_value = []
        mock_rl.get_builder_class.return_value = mock_builder
        mock_rl.default_client_assets.return_value = "default_assets"
        mock_rl.client_assets.return_value = "client_assets"
        return mock_rl

    @pytest.fixture
    def flask_app(self):
        """Create a Flask app for testing."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    def test_init_default_values(self, mock_routelit):
        """Test adapter initialization with default values."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        assert adapter.routelit == mock_routelit
        assert adapter.run_mode == "prod"
        assert adapter.local_frontend_server is None
        assert adapter.local_components_server is None
        assert adapter.cookie_config == {
            "secure": True,
            "samesite": "none",
            "httponly": True,
            "max_age": 60 * 60 * 24 * 1,  # 1 day
        }

    def test_init_custom_values(self, mock_routelit):
        """Test adapter initialization with custom values."""
        adapter = RouteLitFlaskAdapter(
            mock_routelit,
            static_path="/custom/static",
            template_path="/custom/templates",
            local_frontend_server="http://localhost:3000",
            local_components_server="http://localhost:3001",
        )

        assert adapter.static_path == "/custom/static"
        assert adapter.template_path == "/custom/templates"
        assert adapter.local_frontend_server == "http://localhost:3000"
        assert adapter.local_components_server == "http://localhost:3001"

    @patch("routelit_flask.adapter.send_from_directory")
    def test_configure_static_assets(self, mock_send_from_directory, flask_app):
        """Test static asset configuration."""
        asset_target: AssetTarget = {"package_name": "test_package", "path": "static/assets"}

        with patch("routelit_flask.adapter.resources.files") as mock_files:
            mock_files.return_value.joinpath.return_value = "/mock/path"

            RouteLitFlaskAdapter.configure_static_assets(flask_app, asset_target)

            # Check that URL rule was added
            assert any(rule.rule == "/routelit/test_package/<path:filename>" for rule in flask_app.url_map.iter_rules())

    def test_configure_flask_app(self, mock_routelit, flask_app):
        """Test Flask app configuration."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        with (
            patch("routelit_flask.adapter.send_from_directory"),
            patch("routelit_flask.adapter.Path") as mock_path,
            patch("routelit_flask.adapter.FileSystemLoader"),
        ):
            mock_path.return_value.__truediv__.return_value = "/mock/assets/path"

            result = adapter.configure(flask_app)

            # Check that the adapter is returned
            assert result == adapter

            # Check that JSON provider was set
            assert flask_app.json_provider_class == CustomJSONProvider

            # Check that assets URL rule was added
            assert any(rule.rule == "/routelit/assets/<path:filename>" for rule in flask_app.url_map.iter_rules())

    def test_configure_jinja_loader_with_choice_loader(self, mock_routelit, flask_app):
        """Test Jinja loader configuration when ChoiceLoader already exists."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        # Set up existing ChoiceLoader
        existing_loader = Mock()
        choice_loader = ChoiceLoader([existing_loader])
        flask_app.jinja_loader = choice_loader

        with (
            patch("routelit_flask.adapter.send_from_directory"),
            patch("routelit_flask.adapter.Path"),
            patch("routelit_flask.adapter.FileSystemLoader") as mock_fs_loader,
        ):
            mock_fs_instance = Mock()
            mock_fs_loader.return_value = mock_fs_instance

            adapter.configure(flask_app)

            # Check that FileSystemLoader was appended to existing loaders
            assert mock_fs_instance in choice_loader.loaders

    def test_configure_jinja_loader_without_choice_loader(self, mock_routelit, flask_app):
        """Test Jinja loader configuration when no ChoiceLoader exists."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        # Set up existing single loader
        existing_loader = Mock()
        flask_app.jinja_loader = existing_loader

        with (
            patch("routelit_flask.adapter.send_from_directory"),
            patch("routelit_flask.adapter.Path"),
            patch("routelit_flask.adapter.FileSystemLoader") as mock_fs_loader,
            patch("routelit_flask.adapter.ChoiceLoader", ChoiceLoader),
        ):
            mock_fs_instance = Mock()
            mock_fs_loader.return_value = mock_fs_instance

            adapter.configure(flask_app)

            # Check that a ChoiceLoader was created with both loaders
            assert isinstance(flask_app.jinja_loader, ChoiceLoader)
            # Verify both loaders are present
            assert existing_loader in flask_app.jinja_loader.loaders
            assert mock_fs_instance in flask_app.jinja_loader.loaders

    @patch("routelit_flask.adapter.render_template")
    @patch("routelit_flask.adapter.make_response")
    def test_handle_get_request(self, mock_make_response, mock_render_template, mock_routelit):
        """Test GET request handling."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        # Mock view function and request
        view_fn = Mock()
        mock_request = Mock(spec=FlaskRLRequest)
        mock_request.get_session_id.return_value = "test_session_id"

        # Mock RouteLit response
        mock_response = Mock()
        mock_response.get_str_json_elements.return_value = "json_elements"
        mock_response.head.title = "Test Title"
        mock_response.head.description = "Test Description"
        mock_routelit.handle_get_request.return_value = mock_response

        # Mock Flask response
        mock_flask_response = Mock()
        mock_make_response.return_value = mock_flask_response

        result = adapter._handle_get_request(view_fn, mock_request, "arg1", kwarg1="value1")

        # Verify RouteLit was called correctly
        mock_routelit.handle_get_request.assert_called_once_with(view_fn, mock_request, "arg1", kwarg1="value1")

        # Verify template rendering
        mock_render_template.assert_called_once_with(
            "index.html",
            ROUTELIT_DATA="json_elements",
            PAGE_TITLE="Test Title",
            PAGE_DESCRIPTION="Test Description",
            RUN_MODE="prod",
            LOCAL_FRONTEND_SERVER=None,
            LOCAL_COMPONENTS_SERVER=None,
            default_vite_assets="default_assets",
            vite_assets="client_assets",
        )

        # Verify cookie was set
        mock_flask_response.set_cookie.assert_called_once_with(
            "ROUTELIT_SESSION_ID",
            "test_session_id",
            secure=True,
            samesite="none",
            httponly=True,
            max_age=86400,
        )

        assert result == mock_flask_response

    @patch("routelit_flask.adapter.jsonify")
    def test_response_post_request(self, mock_jsonify, mock_routelit):
        """Test POST request handling."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        view_fn = Mock()
        mock_actions = ["action1", "action2"]
        mock_routelit.handle_post_request.return_value = mock_actions

        # Create a mock Flask request
        mock_flask_request = Mock()

        with (
            patch("routelit_flask.adapter.request", mock_flask_request),
            patch("routelit_flask.adapter.FlaskRLRequest") as mock_flask_rl_request,
        ):
            mock_request_instance = Mock()
            mock_request_instance.method = "POST"
            mock_flask_rl_request.return_value = mock_request_instance

            result = adapter.response(view_fn, True, "arg1", kwarg1="value1")

            # Verify RouteLit was called correctly
            mock_routelit.handle_post_request.assert_called_once_with(
                view_fn, mock_request_instance, True, "arg1", kwarg1="value1"
            )

            # Verify JSON response
            mock_jsonify.assert_called_once_with(mock_actions)
            assert result == mock_jsonify.return_value

    def test_response_get_request(self, mock_routelit):
        """Test GET request handling through response method."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        view_fn = Mock()

        # Create a mock Flask request
        mock_flask_request = Mock()

        with (
            patch("routelit_flask.adapter.request", mock_flask_request),
            patch("routelit_flask.adapter.FlaskRLRequest") as mock_flask_rl_request,
            patch.object(adapter, "_handle_get_request") as mock_handle_get,
        ):
            mock_request_instance = Mock()
            mock_request_instance.method = "GET"
            mock_flask_rl_request.return_value = mock_request_instance

            mock_handle_get.return_value = "get_response"

            result = adapter.response(view_fn, None, "arg1", kwarg1="value1")

            # Verify GET handler was called
            mock_handle_get.assert_called_once_with(view_fn, mock_request_instance, None, "arg1", kwarg1="value1")

            assert result == "get_response"

    def test_response_with_flask_rl_request_creation(self, mock_routelit):
        """Test that FlaskRLRequest is created correctly."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        view_fn = Mock()

        # Create a mock Flask request
        mock_flask_request = Mock()

        with (
            patch("routelit_flask.adapter.request", mock_flask_request),
            patch("routelit_flask.adapter.FlaskRLRequest") as mock_flask_rl_request,
            patch.object(adapter, "_handle_get_request"),
        ):
            mock_request_instance = Mock()
            mock_request_instance.method = "GET"
            mock_flask_rl_request.return_value = mock_request_instance

            adapter.response(view_fn)

            # Verify FlaskRLRequest was created with Flask request
            mock_flask_rl_request.assert_called_once_with(mock_flask_request)
