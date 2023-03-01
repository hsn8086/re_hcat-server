#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@File       ：rename.py

@Author     : hsn

@Date       ：2023/3/1 下午6:26

@Version    : 1.0.0
"""
#  Copyright 2023. hsn
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from html import escape

from containers import User, ReturnData
from event.base_event import BaseEvent


class Rename(BaseEvent):
    auth = True

    def _run(self, name):
        with self.server.open_user(self.user_id) as u:
            user: User = u.value
            user.user_name = escape(name)
            return ReturnData(ReturnData.OK)
