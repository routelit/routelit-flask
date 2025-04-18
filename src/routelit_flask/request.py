from typing import Any, Dict, List, Optional
import uuid

from flask import Request
from routelit import RouteLitRequest, RouteLitEvent

from .utils import COOKIE_SESSION_KEY


class FlaskRLRequest(RouteLitRequest):
    def __init__(self, request: Request):
        self.request = request
        self.__default_session_id = str(uuid.uuid4())
        self.__ui_event = self._get_ui_event()

    def get_headers(self) -> Dict[str, str]:
        return self.request.headers

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

    def _get_ui_event(self) -> Optional[RouteLitEvent]:
        if self.request.is_json:
            return self.request.json.get("ui_event")
        else:
            return None

    def get_ui_event(self) -> Optional[RouteLitEvent]:
        return self.__ui_event
    
    def clear_event(self):
        self.__ui_event = None
        
    def get_query_param(self, key: str) -> Optional[str]:
        return self.request.args.get(key)

    def get_query_param_list(self, key: str) -> List[str]:
        return self.request.args.getlist(key)

    def get_session_id(self) -> str:
        return self.request.cookies.get(COOKIE_SESSION_KEY, self.__default_session_id)

    def get_pathname(self) -> str:
        return self.request.path

    def get_host(self) -> str:
        return self.request.host
