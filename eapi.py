# -*- coding: utf-8 -*-
# Copyright (c) 2018 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from __future__ import print_function

import json
import requests
import urllib3
import uuid
import warnings

__version__ = "0.1.9"

# Default behaviors
#
# Override example (suppress SSL errors and warnings):
#
# import eapi
# eapi.DEFAULT_TRANSPORT = "https"
# eapi.SSL_VERIFY = False
# eapi.SSL_WARNINGS = False
#
CONNECT_TIMEOUT = 5
DEFAULT_TRANSPORT = "http"
DEFAULT_AUTH = ("admin", "")
DEFAULT_FORMAT = "json"
EXECUTE_TIMEOUT = 30
INCLUDE_TIMESTAMPS = False
SESSION_HEADERS = {"Content-Type": "application/json"}
SSL_VERIFY = True
SSL_WARNINGS = True

class EapiError(Exception):
    """General eAPI failure"""
    pass

class EapiTimeoutError(EapiError):
    pass

class EapiHttpError(EapiError):
    pass

class EapiResponseError(EapiError):
    pass

class EapiAuthenticationFailure(EapiError):
    pass


class DisableSslWarnings(object):
    """Context manager to disable/enable SSL warnings"""

    def __init__(self):
        self.category = urllib3.exceptions.InsecureRequestWarning

    def __enter__(self):
        if not SSL_WARNINGS:
            warnings.simplefilter('ignore', self.category)

    def __exit__(self, *args):
        warnings.simplefilter('default', self.category)

class Response(object):
    """Data structure for EAPI responses"""

    def __init__(self, commands, output, code=0, message=None):
        self.code = code
        self.message = message
        self.output = output
        self.commands = commands

    def to_dict(self):
        return {
            "code": self.code,
            "commands": self.commands,
            "message": self.message,
            "output": self.output
        }

    def raise_for_error(self):
        if self.code > 0:
            raise EapiResponseError((self.code, self.message))

class Session(object):
    """EAPI Session"""

    def __init__(self, hostaddr,
                 auth=DEFAULT_AUTH,
                 cert=None,
                 port=None,
                 timeout=(CONNECT_TIMEOUT, EXECUTE_TIMEOUT),
                 transport=DEFAULT_TRANSPORT,
                 verify=SSL_VERIFY):

        # use a requests Session to manage state
        self._session = requests.Session()

        # every request should send the same headers
        self._session.headers = SESSION_HEADERS

        self.hostaddr = hostaddr

        self.auth = auth

        self.cert = cert

        self.port = port

        self.transport = transport

        self.timeout = timeout

        self.verify = verify

    def __enter__(self):
        if not self.cert:
            self.login()
        return self

    def __exit__(self, *args):
        self.logout()
        self.close()

    @property
    def verify(self):
        return self._verify

    @verify.setter
    def verify(self, value):
        if not value in (True, False):
            raise TypeError("Expected a boolean")
        self._verify = value

    @property
    def logged_in(self):
        if "Session" in self._session.cookies:
            return True
        return False

    def prepare_url(self, path=""):
        url = "{}://{}".format(self.transport, self.hostaddr)

        if self.port:
            url += ":{}".format(self.port)

        return url + path

    def close(self):
        self._session.close()

    def login(self, **kwargs):
        """Session based Authentication
        """

        if not len(self.auth) == 2:
            raise ValueError("username and password auth tuple is required")

        username, password = self.auth

        payload = {"username": username, "password": password}
        resp = self.send("/login", data=payload, **kwargs)

        if resp.status_code == 401:
            raise EapiAuthenticationFailure(resp.text)
        elif resp.status_code == 404 or "Session" not in resp.cookies:
            # fall back to basic auth if /login is not found or Session key is
            # missing
            self.auth = (username, password)
            return
        elif not resp.ok:
            raise EapiError(resp.reason)

        self.auth = None

    def logout(self, **kwargs):
        if self.logged_in:
            return self.send("/logout", data={}, **kwargs)

    def execute(self, commands, format=DEFAULT_FORMAT,
                timestamps=INCLUDE_TIMESTAMPS, **kwargs):

        code = 0
        message = None
        output = []
        request_id = str(uuid.uuid4())

        params = {
            "version": 1,
            "cmds": commands,
            "format": format
        }

        # timestamps is a newer param, only include it if requested
        if timestamps:
            params["timestamps"] = timestamps

        payload = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": params,
            "id": request_id
        }

        resp = self.send("/command-api", data=payload, **kwargs)

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise EapiHttpError(str(exc))
        resp = resp.json()

        if "error" in resp:
            errored = resp["error"]
            code = errored["code"]
            output = errored["data"]
            message = errored["message"]
        else:
            output = resp["result"]

        return Response(commands, output, code, message)

    # alais for execute to match '/command-api' path
    command_api = execute

    def send(self, path, data, **kwargs):
        """Sends the request to EAPI"""

        url = self.prepare_url(path)

        kwargs.setdefault("timeout", self.timeout)

        if self.cert:
            kwargs.setdefault("cert", self.cert)

        elif not self.logged_in:
            # Note: if the Session key is in cookies no auth parameter is
            # required.
            kwargs.setdefault("auth", self.auth)

        if self.verify is not None:
            kwargs.setdefault("verify", self.verify)

        try:
            with DisableSslWarnings():
                response = self._session.post(url, data=json.dumps(data),
                                              **kwargs)
        except requests.Timeout as exc:
            raise EapiTimeoutError(str(exc))
        except requests.ConnectionError as exc:
            raise EapiError(str(exc))

        return response

def session(*args, **kwargs):
    return Session(*args, **kwargs)
