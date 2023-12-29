#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#  Copyright (C) 2023. HCAT-Project-Team
#  _
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#  _
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#  _
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
@File       : fastapi_receiver.py

@Author     : hsn

@Date       : 11/4/23 12:01 PM

@Version    : 1.0.0
"""
import json
import logging
from pathlib import Path
from textwrap import dedent

import fastapi
import socketio
import uvicorn
from fastapi import FastAPI, UploadFile
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, Response

from dynamic_obj_loader import DynamicObjLoader
from src.containers import Request, ReturnData
from src.request_receiver.base_receiver import BaseReceiver
from src.util.i18n import gettext_func as _
from ...util.sockets import sio_server


def gen_api_doc():
    dol = DynamicObjLoader()
    objs = dol.load_objs('src/event/events')
    base_path = Path('tools/doc_tool/doc')

    paths_json = {}
    for i in objs:
        paths_json['api/' + '/'.join(i.__module__.split('.')[3:])] = gen(i)
    return {'openapi': '3.1.0', 'info': {'title': 'HCAT', 'description': 'HCAT API', 'version': '0.0.1'},
            'paths': paths_json}


def gen(obj_):
    docs = dedent(str(obj_.__doc__)).split('\n')
    return {
        "post": {
            "summary": docs[1] if len(docs) >= 2 else '',
            "description": '\n'.join(docs[2:]) or '',
            "operationId": obj_.__name__,
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                i: {
                                    "type": "string"
                                } for i in obj_(None, None, None).parameters
                            }
                        }
                    }
                }
            },
            "responses": {
                "200": {
                    "description": "OK",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {**{
                                    i: {
                                        "type": obj_.returns.get(i, str).__name__
                                    } for i in obj_.returns

                                }, "status": {"type": "string"}, "message": {"type": "string"}}
                            }
                        }
                    }
                }

            }

        }
    }


class FastapiReceiver(BaseReceiver):
    def _start(self):
        self.app = FastAPI(debug=True)

        # Enable Cross-Origin Resource Sharing (CORS)
        if self.receiver_config.get_from_pointer("enable-cors", True):
            self.app.add_middleware(
                CORSMiddleware,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        sio_asgi_app = socketio.ASGIApp(
            socketio_server=sio_server, other_asgi_app=self.app
        )
        self.app.add_route("/socket.io/", route=sio_asgi_app, methods=["GET", "POST"])
        self.app.add_websocket_route("/socket.io/", sio_asgi_app)

        @self.app.get("/api/{path:path}")
        @self.app.post("/api/{path:path}")
        async def recv(path, request: fastapi.Request, file: UploadFile | None = None):
            data = {}
            f = {}
            if request.method == "GET":
                data = dict(request.query_params)
            elif request.method == "POST":
                if file:
                    f = {file.filename: file.file}
                else:
                    content = await request.body()
                    if content:
                        data = json.loads(content)
                    else:
                        data = {}

            req = Request(
                path=path,
                data=data,
                files=f,
                cookies=request.cookies,
                headers=dict(request.headers),
            )

            rt = self.create_req(req)

            if rt is None:
                rt = ReturnData(ReturnData.NULL, "")
            elif not isinstance(rt, ReturnData):
                raise TypeError(
                    f"Return type of {type(self).__name__} must be ReturnData or None, not {type(rt)}"
                )
            resp = Response(json.dumps(rt.json_data), media_type="application/json")

            if rt.json_data.get("_cookies", False):
                for k, v in rt.json_data["_cookies"].items():
                    resp.set_cookie(key=k, **v)

            return resp

        # optional, but recommended
        if self.receiver_config.get_from_pointer("enable-static", True):

            @self.app.get("/")
            @self.app.get("/{path:path}")
            def send_static(path=None):
                static_folder = self.receiver_config.get_from_pointer(
                    "static-folder", "static"
                )
                if not path or (not (Path.cwd() / static_folder / path).exists()):
                    path = "index.html"
                return FileResponse(Path.cwd() / static_folder / path)
        self.app.openapi = gen_api_doc
        # def custom_openapi():
        #     return {'openapi': '3.1.0', 'info': {'title': 'HCAT', 'description': 'HCAT API', 'version': '0.0.1'},
        #             'paths': {}}
        #
        # self.app.openapi = custom_openapi
        # ssl
        ssl_kwargs = {}
        if self.global_config.get_from_pointer("/network/ssl/enable", False):
            ssl_cert = self.global_config.get_from_pointer("/network/ssl/cert")
            ssl_key = self.global_config.get_from_pointer("/network/ssl/key")
            ssl_kwargs = {"keyfile": ssl_key, "certfile": ssl_cert}
            self.logger.debug(_("FlaskHttpReceiver started with SSL."))

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            reload=False,
            workers=1,
            **ssl_kwargs,
        )
        server = uvicorn.Server(config)
        self.asgi_server = server

        try:
            server.run()
        except KeyboardInterrupt:
            server.shutdown()
            logging.info(_("FastapiReceiver stopped."))