# -*- coding: utf-8 -*-
# Copyright (c) 2020 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

import asyncio

import pytest

import eapix
from eapix.messages import Response

# from tests.conftest import EAPI_TARGET

# pytestmark = pytest.mark.skipif(not EAPI_TARGET, reason="target not set")

def test_execute(server, commands, auth):
    target = str(server.url)
    eapix.execute(target, commands=commands, auth=auth)

def test_enable(server, commands, auth):
    target = str(server.url)
    eapix.enable(target, commands=commands, auth=auth, secret="s3cr3t")

def test_execute_text(server, commands, auth):
    target = str(server.url)
    eapix.execute(target, commands=commands, auth=auth, encoding="text")

def test_execute_jsonerr(server, auth):
    target = str(server.url)
    response = eapix.execute(
        target, commands=["show hostname", "show bogus"], auth=auth, encoding="json")

    assert response.code > 0

def test_execute_err(server, auth):
    target = str(server.url)
    response = eapix.execute(target,
        commands=[
            "show hostname",
            "show bogus",
            "show running-config"
        ],
        encoding="text",
        auth=auth
    )
    assert response.code > 0

def test_configure(server, auth):
    target = str(server.url)
    eapix.configure(target, [
        "ip access-list standard DELETE_ME",
        "permit any"
    ], auth=auth)

    eapix.execute(target, ["show ip access-list DELETE_ME"], auth=auth)

    eapix.configure(target, [
        "no ip access-list DELETE_ME"
    ], auth=auth)


def test_watch(server, auth):
    target = str(server.url)
    def _cb(r, matched: bool):
        assert isinstance(r, eapix.messages.Response)
    
    eapix.watch(target, "show clock", callback=_cb, auth=auth, encoding="text", deadline=10)
    

@pytest.mark.asyncio
async def test_aexecute(server, commands, auth):
    target = str(server.url)
    resp = await eapix.aexecute(target, commands, auth=auth)

@pytest.mark.asyncio
async def test_awatch(server, auth):
    target = str(server.url)
    tasks = []

    async def _cb(r, match: bool):
        assert isinstance(r, eapix.messages.Response)

    for c in ["show clock", "show hostname"]:
        tasks.append(
            eapix.awatch(target, c, callback=_cb, auth=auth, encoding="text", deadline=10)
        )
    
    responses = await asyncio.gather(*tasks)

    assert len(responses) == 2

    for rsp in responses:
        assert isinstance(rsp, Response)



    

