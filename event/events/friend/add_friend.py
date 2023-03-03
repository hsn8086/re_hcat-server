#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@File       ：add_friend.py

@Author     : hsn

@Date       ：2023/3/1 下午6:27

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
import time

from containers import ReturnData, User, EventContainer
from event.base_event import BaseEvent


class AddFriend(BaseEvent):
    auth = True

    def _run(self, user_id, add_info=''):
        if not self.server.is_user_exist(user_id):
            return ReturnData(ReturnData.NULL, 'User does not exist.').jsonify()
        with self.server.open_user(self.user_id) as u:
            user: User = u.value
            if user_id in user.friend_dict:
                return ReturnData(ReturnData.ERROR, 'You are already friends with each other.')

        ec = EventContainer(self.server.db_event)
        ec. \
            add('type', 'friend_request'). \
            add('rid', ec.rid). \
            add('user_id', self.user_id). \
            add('req_user_id', user_id). \
            add('add_info', add_info). \
            add('time', time.time())
        ec.write_in()

        with self.server.open_user(user_id) as u:
            user: User = u.value

            user.add_user_event(ec)
            return ReturnData(ReturnData.OK)
