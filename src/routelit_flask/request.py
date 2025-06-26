import uuid
from collections.abc import Mapping
from typing import Any, Optional

from flask import Request
from routelit import COOKIE_SESSION_KEY, RouteLitRequest  # type: ignore[import-untyped]


class FlaskRLRequest(RouteLitRequest):
    """
    Implements the RouteLitRequest interface for Flask.
    """

    def __init__(self, request: Request):
        self.request = request
        super().__init__()
        self.__default_session_id = str(uuid.uuid4())

    def get_headers(self) -> dict[str, str]:
        return self.request.headers  # type: ignore[return-value]

    def get_path_params(self) -> Optional[Mapping[str, Any]]:
        return self.request.view_args

    def get_referrer(self) -> Optional[str]:
        return self.request.referrer or self.request.headers.get("Referer")

    @property
    def method(self) -> str:
        return self.request.method

    def get_json(self) -> Optional[Any]:
        if self.is_json():
            return self.request.json
        else:
            return None

    def is_json(self) -> bool:
        return self.request.is_json

    def get_query_param(self, key: str) -> Optional[str]:
        return self.request.args.get(key)

    def get_query_param_list(self, key: str) -> list[str]:
        return self.request.args.getlist(key)

    def get_session_id(self) -> str:
        return self.request.cookies.get(COOKIE_SESSION_KEY, self.__default_session_id)

    def get_pathname(self) -> str:
        return self.request.path

    def get_host(self) -> str:
        return self.request.host
