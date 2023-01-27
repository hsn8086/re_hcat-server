import json

from flask import make_response

import util
from containers import ReturnData, User
from event.base_event import BaseEvent


class Login(BaseEvent):
    auth = False

    def _run(self, user_id, password):
        if not self.server.is_user_exist(user_id):
            return ReturnData(ReturnData.NULL, 'User does not exist.').jsonify()
        self.server.activity_dict_lock.acquire()
        self.server.activity_dict[user_id] = 30
        self.server.activity_dict_lock.release()
        with self.server.open_user(user_id) as u:
            user: User = u.value
            if user.auth(password):
                user.status = 'online'
                # generate token
                user.token = util.get_random_token()

                # init a response
                resp = make_response(ReturnData(ReturnData.OK).jsonify(), 200)

                # generate auth_data
                auth_data = json.dumps({'user_id': user_id, 'token': user.token, 'salt': util.get_random_token()})

                # crypto
                aes = util.AesCrypto(self.server.key)

                # set a @Yummy_Cookies_S
                # XD
                resp.set_cookie('auth_data', aes.encrypto(auth_data))

                # return
                return resp
            else:
                return ReturnData(ReturnData.ERROR, 'Incorrect user ID or password.')
