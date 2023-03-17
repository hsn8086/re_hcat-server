#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@File       ：register.py

@Author     : hsn

@Date       ：2023/3/1 下午6:26

@Version    : 1.0.0
"""

#  Copyright (C) 2023. HCAT-Project-Team
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import re
from html import escape

from containers import ReturnData, User
from event.base_event import BaseEvent
from util.regex import name_regex


class Register(BaseEvent):
    auth = False

    def _run(self, user_id, password, username):
        if self.server.is_user_exist(user_id):
            return ReturnData(ReturnData.ERROR, 'ID has been registered.').jsonify()

        # check if user_id is legal

        if not re.match(name_regex, user_id):
            return ReturnData(ReturnData.ERROR,
                              f'User ID does not match {name_regex} .').jsonify()

        # check if the password is longer than 6 digits
        if len(password) < 6:
            return ReturnData(ReturnData.ERROR, 'Password is too short.')

        with self.server.open_user(user_id) as u:
            user=User(user_id, password, escape(username))

            u.value = user
            user.add_fri_msg2todos(self.server, '0sAccount', 'Account_BOT', 'Account_BOT',
                                   'Welcome to HCAT!<br>'
                                   'The first thing you need to do is use `/email bind [email]` to '
                                   'bind your email.<br>'
                                   'Then you can use `/email code [code]` to verify your email.<br>'
                                   'After that, you can use `/email unbind` to unbind your email if you want.<br>'
                                   'Have fun!')

            return ReturnData(ReturnData.OK)
