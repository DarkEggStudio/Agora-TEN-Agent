from ten import (
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from .log import logger
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from functools import partial


class HTTPHandler(BaseHTTPRequestHandler):
    def __init__(self, ten, *args, directory=None, **kwargs):
        logger.info("new handler: %s %s %s", directory, args, kwargs)
        self.ten = ten
        super().__init__(*args, **kwargs)

    def do_POST(self):
        logger.info("post request incoming %s", self.path)
        if self.path == "/cmd":
            try:
                content_length = int(self.headers["Content-Length"])
                input = self.rfile.read(content_length).decode("utf-8")
                logger.info("incoming request %s", input)
                self.ten.send_cmd(
                    Cmd.create_from_json(input),
                    lambda ten, result: logger.info(
                        "finish send_cmd from http server %s %s", input, result
                    ),
                )
                self.send_response_only(200)
                self.end_headers()
            except Exception as e:
                logger.warning("failed to handle request, err {}".format(e))
                self.send_response_only(500)
                self.end_headers()
        else:
            logger.warning("invalid path: %s", self.path)
            self.send_response_only(404)
            self.end_headers()


WORKER_HTTP_PORT_KEY = "worker_http_server_port"
class HTTPServerExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.listen_addr = "127.0.0.1"
        self.listen_port = 8888
        self.worker_http_server_port = 8081
        self.cmd_white_list = None
        self.server = None
        self.thread = None

    def on_start(self, ten_env: TenEnv) -> None:
        self.listen_addr = ten_env.get_property_string("listen_addr")
        self.listen_port = ten_env.get_property_int("listen_port")
        self.worker_http_server_port = self.get_property_int(ten_env, WORKER_HTTP_PORT_KEY)
        """
            white_list = ten.get_property_string("cmd_white_list")
            if len(white_list) > 0:
                self.cmd_white_list = white_list.split(",")
        """

        logger.info(
            "HTTPServerExtension on_start %s:%d (%d), %s",
            self.listen_addr,
            self.listen_port,
            self.worker_http_server_port,
            self.cmd_white_list,
        )

        self.server = HTTPServer(
            ("127.0.0.1", self.worker_http_server_port), partial(HTTPHandler, ten_env)
            # (self.listen_addr, self.listen_port), partial(HTTPHandler, ten)
        )
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

        ten_env.on_start_done()

    def on_stop(self, ten: TenEnv):
        logger.info("on_stop")
        self.server.shutdown()
        self.thread.join()
        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd):
        cmd_json = cmd.to_json()
        logger.info("on_cmd json: " + cmd_json)
        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "ok")
        ten.return_result(cmd_result, cmd)

    def get_property_int(self, data: Data, property_name: str) -> int:
        """Helper to get int property from data with error handling."""
        try:
            return data.get_property_int(property_name)
        except Exception as err:
            logger.warning(f"GetProperty {property_name} failed: {err}")
            return 0
