import logging
import multiprocessing
import os

import pymongo
import pytest
import requests
import time
import tornado.gen
from tornado.ioloop import IOLoop
from tornado.web import HTTPError

import core4.logger.mixin
import core4.service
from core4.api.v1.application import CoreApiContainer
from core4.api.v1.tool import serve
from core4.api.v1.request.main import CoreRequestHandler

MONGO_URL = 'mongodb://core:654321@localhost:27017'
MONGO_DATABASE = 'core4test'


@pytest.fixture(autouse=True)
def setup(tmpdir):
    logging.shutdown()
    core4.logger.mixin.CoreLoggerMixin.completed = False
    os.environ["CORE4_OPTION_folder__root"] = str(tmpdir)
    os.environ["CORE4_OPTION_DEFAULT__mongo_url"] = MONGO_URL
    os.environ["CORE4_OPTION_DEFAULT__mongo_database"] = MONGO_DATABASE
    os.environ["CORE4_OPTION_logging__mongodb"] = "DEBUG"
    os.environ["CORE4_OPTION_api__token__expiration"] = "!!int 60"
    os.environ["CORE4_OPTION_api__setting__debug"] = "!!bool True"
    os.environ["CORE4_OPTION_api__setting__cookie_secret"] = "blabla"
    os.environ["CORE4_OPTION_worker__min_free_ram"] = "!!int 32"
    conn = pymongo.MongoClient(MONGO_URL)
    conn.drop_database(MONGO_DATABASE)
    core4.logger.mixin.logon()
    yield
    conn.drop_database(MONGO_DATABASE)
    for i, j in core4.service.setup.CoreSetup.__dict__.items():
        if callable(j):
            if "has_run" in j.__dict__:
                j.has_run = False
    core4.util.tool.Singleton._instances = {}
    dels = []
    for k in os.environ:
        if k.startswith('CORE4_'):
            dels.append(k)
    for k in dels:
        del os.environ[k]


class StopHandler(CoreRequestHandler):
    protected = False

    def get(self):
        self.logger.warning("stop IOLoop now: %s", IOLoop.current())
        IOLoop.current().stop()


class LocalTestServer:
    base_url = "/core4/api/v1"

    def __init__(self):
        self.port = 5555
        self.process = None
        self.process = multiprocessing.Process(target=self.run)
        self.process.start()
        while True:
            try:
                url = self.url("/profile")
                requests.get(url, timeout=1)
                break
            except:
                pass
            time.sleep(1)
            tornado.gen.sleep(1)
        self.signin = requests.get(
            self.url("/login?username=admin&password=hans"))
        self.token = self.signin.json()["data"]["token"]
        assert self.signin.status_code == 200

    def url(self, url):
        return "http://localhost:{}{}".format(self.port, self.base_url) + url

    def request(self, method, url, **kwargs):
        if self.token:
            kwargs.setdefault("headers", {})[
                "Authorization"] = "Bearer " + self.token
        return requests.request(method, self.url(url), **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def run(self):

        cls = self.start()
        cls.root = self.base_url
        self.serve(cls)

    def serve(self, cls, **kwargs):
        serve(cls, port=self.port, **kwargs)

    def start(self, *args, **kwargs):

        class CoreApiTestServer(CoreApiContainer):
            rules = [
                (r'/kill', StopHandler)
            ]

        return CoreApiTestServer

    def stop(self):
        rv = self.get("/kill")
        assert rv.status_code == 200
        self.process.join()


@pytest.fixture()
def http():
    server = LocalTestServer()
    yield server
    server.stop()


class FlashHandler(CoreRequestHandler):

    def get(self):
        self.flash("INFO", "hello world")
        self.flash("DEBUG", "you 2")
        self.flash_debug("this is %s", "debug")
        self.flash_info("this is info")
        self.flash_warning("this is warning")
        self.flash_error("this is error")
        self.reply([1, 2, 3])


class ErrorHandler(CoreRequestHandler):

    def get(self, variant):
        if variant == "/abort":
            raise HTTPError(409, "this is so not possible")
        raise RuntimeError("this is unexpected")


class MyTestServer(LocalTestServer):
    base_url = "/core4/api/v2"

    def start(self, *args, **kwargs):
        class CoreApiTestServer(CoreApiContainer):
            rules = [
                (r'/kill', StopHandler),
                (r'/flash', FlashHandler),
                (r'/error(/.*)?', ErrorHandler),
            ]

        return CoreApiTestServer


class MyShortTestServer(MyTestServer):

    def serve(self, cls, **kwargs):
        serve(cls, port=self.port, debug=False, **kwargs)


def test_error():
    server = MyTestServer()
    rv = server.get("/xxx")
    assert rv.status_code == 404
    data = rv.json()
    assert data["code"] == 404
    assert data["message"] == "Not Found"
    msg = data["error"].strip()
    assert msg.startswith("Traceback")
    assert msg.endswith("tornado.web.HTTPError: HTTP 404: Not Found")
    server.stop()


def test_error_short():
    server = MyShortTestServer()
    rv = server.get("/xxx")
    assert rv.status_code == 404
    data = rv.json()
    assert data["code"] == 404
    assert data["message"] == "Not Found"
    msg = data["error"].strip()
    assert msg == "tornado.web.HTTPError: HTTP 404: Not Found " \
                  "(http://localhost:5555/core4/api/v2/xxx)"
    server.stop()


def test_flash():
    server = MyShortTestServer()
    rv = server.get("/flash")
    assert rv.status_code == 200
    data = rv.json()
    assert data["flash"] == [
        {'level': 'INFO', 'message': 'hello world'},
        {'level': 'DEBUG', 'message': 'you 2'},
        {'level': 'DEBUG', 'message': 'this is debug'},
        {'level': 'INFO', 'message': 'this is info'},
        {'level': 'WARNING', 'message': 'this is warning'},
        {'level': 'ERROR', 'message': 'this is error'}]
    server.stop()


def test_error():
    server = MyShortTestServer()
    rv = server.get("/error")
    data = rv.json()
    assert data["code"] == 500
    assert data["message"] == "Internal Server Error"
    assert data["error"].startswith("RuntimeError: this is unexpected")
    server.stop()


def test_abort():
    server = MyShortTestServer()
    rv = server.get("/error/abort")
    data = rv.json()
    print(data)
    assert data["code"] == 409
    assert data["message"] == "Conflict"
    assert data["error"] == "tornado.web.HTTPError: HTTP 409: " \
                            "Conflict (this is so not possible)\n"
    server.stop()