from unittest.mock import Mock, patch

import pytest
from flask import Flask
from jinja2 import ChoiceLoader
from routelit import AssetTarget, RouteLit  # type: ignore[import-untyped]

from routelit_flask.adapter import RouteLitFlaskAdapter, RunModeEnum
from routelit_flask.json_encoder import CustomJSONProvider
from routelit_flask.request import FlaskRLRequest


class TestRunModeEnum:
    """Test the RunModeEnum class."""

    def test_enum_values(self):
        """Test that enum has correct values."""
        assert RunModeEnum.PROD.value == "prod"
        assert RunModeEnum.DEV_CLIENT.value == "dev_client"
        assert RunModeEnum.DEV_COMPONENTS.value == "dev_components"


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

    def test_init_default_values_dev_mode(self, mock_routelit):
        """Test adapter initialization with default values in dev mode."""
        adapter = RouteLitFlaskAdapter(mock_routelit, run_mode="dev_client")

        assert adapter.routelit == mock_routelit
        assert adapter.run_mode == "dev_client"
        assert adapter.local_frontend_server is None
        assert adapter.local_components_server is None
        assert adapter.cookie_config == {}  # Empty dict in dev mode

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

    def test_init_custom_cookie_config(self, mock_routelit):
        """Test adapter initialization with custom cookie configuration."""
        custom_cookie_config = {
            "secure": False,
            "samesite": "lax",
            "httponly": False,
            "max_age": 3600,
        }

        adapter = RouteLitFlaskAdapter(mock_routelit, cookie_config=custom_cookie_config)

        assert adapter.cookie_config == custom_cookie_config

    def test_init_dev_components_mode(self, mock_routelit):
        """Test adapter initialization in dev_components mode."""
        adapter = RouteLitFlaskAdapter(
            mock_routelit, run_mode="dev_components", local_components_server="http://localhost:3001"
        )

        assert adapter.run_mode == "dev_components"
        assert adapter.local_components_server == "http://localhost:3001"
        assert adapter.cookie_config == {}

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

        # Mock request
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

        result = adapter._handle_get_request(Mock(), mock_request, kwarg1="value1")

        # Verify RouteLit was called correctly
        call_args = mock_routelit.handle_get_request.call_args[0]
        assert call_args[1] == mock_request
        assert isinstance(call_args[0], Mock)
        call_kwargs = mock_routelit.handle_get_request.call_args[1]
        assert call_kwargs["kwarg1"] == "value1"

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
            mock_handle_get.assert_called_once()
            call_args = mock_handle_get.call_args[0]
            assert call_args[1] == mock_request_instance
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

    @patch("routelit_flask.adapter.stream_with_context")
    @patch("routelit_flask.adapter.Response")
    def test_stream_response_post_request(self, mock_response, mock_stream_with_context, mock_routelit):
        """Test POST request handling in stream_response method."""
        adapter = RouteLitFlaskAdapter(mock_routelit)

        view_fn = Mock()
        mock_stream_data = ["action1", "action2"]
        mock_routelit.handle_post_request_stream_jsonl.return_value = mock_stream_data

        # Create a mock Flask request
        mock_flask_request = Mock()

        with (
            patch("routelit_flask.adapter.request", mock_flask_request),
            patch("routelit_flask.adapter.FlaskRLRequest") as mock_flask_rl_request,
        ):
            mock_request_instance = Mock()
            mock_request_instance.method = "POST"
            mock_flask_rl_request.return_value = mock_request_instance

            mock_response_instance = Mock()
            mock_response_instance.headers = {}
            mock_response.return_value = mock_response_instance

            result = adapter.stream_response(view_fn, True, "arg1", kwarg1="value1")

            # Verify RouteLit was called correctly
            mock_routelit.handle_post_request_stream_jsonl.assert_called_once_with(
                view_fn, mock_request_instance, True, "arg1", kwarg1="value1"
            )

            # Verify stream response was created
            mock_stream_with_context.assert_called_once_with(mock_stream_data)
            mock_response.assert_called_once_with(mock_stream_with_context.return_value, mimetype="text/event-stream")

            # Verify headers were set
            assert mock_response_instance.headers["Content-Type"] == "application/jsonlines"
            assert result == mock_response_instance

    def test_stream_response_get_request(self, mock_routelit):
        """Test GET request handling through stream_response method."""
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

            result = adapter.stream_response(view_fn, None, "arg1", kwarg1="value1")

            # Verify GET handler was called
            mock_handle_get.assert_called_once()
            call_args = mock_handle_get.call_args[0]
            assert call_args[1] == mock_request_instance
            assert result == "get_response"

    def test_handle_get_request_dev_mode(self, mock_routelit):
        """Test GET request handling in dev mode with local servers."""
        adapter = RouteLitFlaskAdapter(
            mock_routelit,
            run_mode="dev_client",
            local_frontend_server="http://localhost:3000",
            local_components_server="http://localhost:3001",
        )

        # Mock request
        mock_request = Mock(spec=FlaskRLRequest)
        mock_request.get_session_id.return_value = "test_session_id"

        # Mock RouteLit response
        mock_response = Mock()
        mock_response.get_str_json_elements.return_value = "json_elements"
        mock_response.head.title = "Test Title"
        mock_response.head.description = "Test Description"
        mock_routelit.handle_get_request.return_value = mock_response

        with (
            patch("routelit_flask.adapter.render_template") as mock_render_template,
            patch("routelit_flask.adapter.make_response") as mock_make_response,
        ):
            mock_flask_response = Mock()
            mock_make_response.return_value = mock_flask_response

            adapter._handle_get_request(Mock(), mock_request, kwarg1="value1")

            # Verify template rendering with dev mode values
            mock_render_template.assert_called_once_with(
                "index.html",
                ROUTELIT_DATA="json_elements",
                PAGE_TITLE="Test Title",
                PAGE_DESCRIPTION="Test Description",
                RUN_MODE="dev_client",
                LOCAL_FRONTEND_SERVER="http://localhost:3000",
                LOCAL_COMPONENTS_SERVER="http://localhost:3001",
                default_vite_assets="default_assets",
                vite_assets="client_assets",
            )

            # Verify cookie was set with dev mode config (empty dict)
            mock_flask_response.set_cookie.assert_called_once_with(
                "ROUTELIT_SESSION_ID",
                "test_session_id",
            )

    def test_configure_with_multiple_static_paths(self, mock_routelit, flask_app):
        """Test configuration with multiple static asset paths."""
        # Mock multiple static paths
        mock_builder = Mock()
        mock_builder.get_client_resource_paths.return_value = [
            {"package_name": "package1", "path": "static/assets1"},
            {"package_name": "package2", "path": "static/assets2"},
        ]
        mock_routelit.get_builder_class.return_value = mock_builder

        adapter = RouteLitFlaskAdapter(mock_routelit)

        with (
            patch("routelit_flask.adapter.send_from_directory"),
            patch("routelit_flask.adapter.Path"),
            patch("routelit_flask.adapter.FileSystemLoader"),
            patch("routelit_flask.adapter.resources.files") as mock_files,
        ):
            mock_files.return_value.joinpath.return_value = "/mock/path"

            adapter.configure(flask_app)

            # Check that both URL rules were added
            rules = [rule.rule for rule in flask_app.url_map.iter_rules()]
            assert "/routelit/package1/<path:filename>" in rules
            assert "/routelit/package2/<path:filename>" in rules
            assert "/routelit/assets/<path:filename>" in rules


class TestFlaskRLRequest:
    """Test the FlaskRLRequest class."""

    @pytest.fixture
    def mock_flask_request(self):
        """Create a mock Flask request for testing."""
        mock_request = Mock()
        mock_request.headers = {"Content-Type": "application/json", "Referer": "http://example.com"}
        mock_request.view_args = {"id": "123"}
        mock_request.referrer = "http://example.com"
        mock_request.method = "GET"
        mock_request.json = {"key": "value"}
        mock_request.is_json = True
        mock_request.args = {"param1": "value1", "param2": ["value2", "value3"]}
        mock_request.path = "/test/path"
        mock_request.host = "example.com"
        mock_request.cookies = {"ROUTELIT_SESSION_ID": "existing_session_id"}
        return mock_request

    def test_init(self, mock_flask_request):
        """Test FlaskRLRequest initialization."""
        rl_request = FlaskRLRequest(mock_flask_request)

        assert rl_request.request == mock_flask_request
        assert rl_request._FlaskRLRequest__default_session_id is not None

    def test_get_headers(self, mock_flask_request):
        """Test get_headers method."""
        rl_request = FlaskRLRequest(mock_flask_request)

        headers = rl_request.get_headers()
        assert headers == mock_flask_request.headers

    def test_get_path_params(self, mock_flask_request):
        """Test get_path_params method."""
        rl_request = FlaskRLRequest(mock_flask_request)

        params = rl_request.get_path_params()
        assert params == {"id": "123"}

    def test_get_path_params_none(self, mock_flask_request):
        """Test get_path_params method when view_args is None."""
        mock_flask_request.view_args = None
        rl_request = FlaskRLRequest(mock_flask_request)

        params = rl_request.get_path_params()
        assert params is None

    def test_get_referrer_from_referrer(self, mock_flask_request):
        """Test get_referrer method using request.referrer."""
        rl_request = FlaskRLRequest(mock_flask_request)

        referrer = rl_request.get_referrer()
        assert referrer == "http://example.com"

    def test_get_referrer_from_headers(self, mock_flask_request):
        """Test get_referrer method using headers when referrer is None."""
        mock_flask_request.referrer = None
        rl_request = FlaskRLRequest(mock_flask_request)

        referrer = rl_request.get_referrer()
        assert referrer == "http://example.com"

    def test_get_referrer_none(self, mock_flask_request):
        """Test get_referrer method when both referrer and header are None."""
        mock_flask_request.referrer = None
        mock_flask_request.headers = {}
        rl_request = FlaskRLRequest(mock_flask_request)

        referrer = rl_request.get_referrer()
        assert referrer is None

    def test_method_property(self, mock_flask_request):
        """Test method property."""
        rl_request = FlaskRLRequest(mock_flask_request)

        assert rl_request.method == "GET"

    def test_get_json_when_is_json(self, mock_flask_request):
        """Test get_json method when request is JSON."""
        rl_request = FlaskRLRequest(mock_flask_request)

        json_data = rl_request.get_json()
        assert json_data == {"key": "value"}

    def test_get_json_when_not_json(self, mock_flask_request):
        """Test get_json method when request is not JSON."""
        mock_flask_request.is_json = False
        rl_request = FlaskRLRequest(mock_flask_request)

        json_data = rl_request.get_json()
        assert json_data is None

    def test_is_json_property(self, mock_flask_request):
        """Test is_json property."""
        rl_request = FlaskRLRequest(mock_flask_request)

        assert rl_request.is_json() is True

    def test_get_query_param(self, mock_flask_request):
        """Test get_query_param method."""
        rl_request = FlaskRLRequest(mock_flask_request)

        param = rl_request.get_query_param("param1")
        assert param == "value1"

    def test_get_query_param_not_found(self, mock_flask_request):
        """Test get_query_param method when parameter is not found."""
        rl_request = FlaskRLRequest(mock_flask_request)

        param = rl_request.get_query_param("nonexistent")
        assert param is None

    def test_get_query_param_list(self, mock_flask_request):
        """Test get_query_param_list method."""
        rl_request = FlaskRLRequest(mock_flask_request)

        # Patch args to have getlist
        mock_flask_request.args = Mock()
        mock_flask_request.args.getlist.return_value = ["value2", "value3"]
        params = rl_request.get_query_param_list("param2")
        mock_flask_request.args.getlist.assert_called_once_with("param2")
        assert params == ["value2", "value3"]

    def test_get_session_id_existing(self, mock_flask_request):
        """Test get_session_id method when session ID exists in cookies."""
        rl_request = FlaskRLRequest(mock_flask_request)

        session_id = rl_request.get_session_id()
        assert session_id == "existing_session_id"

    def test_get_session_id_default(self, mock_flask_request):
        """Test get_session_id method when session ID doesn't exist in cookies."""
        mock_flask_request.cookies = {}
        rl_request = FlaskRLRequest(mock_flask_request)

        session_id = rl_request.get_session_id()
        assert session_id == rl_request._FlaskRLRequest__default_session_id

    def test_get_pathname(self, mock_flask_request):
        """Test get_pathname method."""
        rl_request = FlaskRLRequest(mock_flask_request)

        pathname = rl_request.get_pathname()
        assert pathname == "/test/path"

    def test_get_host(self, mock_flask_request):
        """Test get_host method."""
        rl_request = FlaskRLRequest(mock_flask_request)

        host = rl_request.get_host()
        assert host == "example.com"


class TestCustomJSONProvider:
    """Test the CustomJSONProvider class."""

    @pytest.fixture
    def json_provider(self):
        """Create a CustomJSONProvider instance for testing."""
        mock_app = Mock()
        return CustomJSONProvider(mock_app)

    def test_dumps_with_default_kwargs(self, json_provider):
        """Test dumps method with default kwargs."""
        data = {"key": "value"}

        with patch("json.dumps") as mock_dumps:
            json_provider.dumps(data)

            mock_dumps.assert_called_once()
            call_kwargs = mock_dumps.call_args[1]
            assert call_kwargs["skipkeys"] is True
            assert call_kwargs["default"] == json_provider._default

    def test_dumps_with_custom_kwargs(self, json_provider):
        """Test dumps method with custom kwargs."""
        data = {"key": "value"}

        with patch("json.dumps") as mock_dumps:
            json_provider.dumps(data, indent=2, sort_keys=True)

            mock_dumps.assert_called_once()
            call_kwargs = mock_dumps.call_args[1]
            assert call_kwargs["skipkeys"] is True
            assert call_kwargs["default"] == json_provider._default
            assert call_kwargs["indent"] == 2
            assert call_kwargs["sort_keys"] is True

    def test_default_with_dict_attribute(self, json_provider):
        """Test _default method with object that has __dict__."""

        class TestObject:
            def __init__(self):
                self.name = "test"
                self.value = 123
                self.none_value = None

        obj = TestObject()
        result = json_provider._default(obj)

        # Should only include non-None values
        assert result == {"name": "test", "value": 123}

    def test_default_without_dict_attribute(self, json_provider):
        """Test _default method with object that doesn't have __dict__."""
        obj = "string_object"

        with patch.object(json_provider, "_default") as mock_super_default:
            mock_super_default.return_value = "default_value"
            result = json_provider._default(obj)

            assert result == "default_value"


class TestUtils:
    """Test utility functions."""

    @patch("routelit_flask.utils.resources.files")
    def test_get_default_static_path(self, mock_files):
        """Test get_default_static_path function."""
        mock_files.return_value.joinpath.return_value = "/mock/static/path"

        from routelit_flask.utils import get_default_static_path

        result = get_default_static_path()

        mock_files.assert_called_once_with("routelit")
        mock_files.return_value.joinpath.assert_called_once_with("static")
        assert result == "/mock/static/path"

    @patch("routelit_flask.utils.resources.files")
    def test_get_default_template_path(self, mock_files):
        """Test get_default_template_path function."""
        mock_files.return_value.joinpath.return_value = "/mock/template/path"

        from routelit_flask.utils import get_default_template_path

        result = get_default_template_path()

        mock_files.assert_called_once_with("routelit")
        mock_files.return_value.joinpath.assert_called_once_with("templates")
        assert result == "/mock/template/path"
