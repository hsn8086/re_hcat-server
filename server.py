#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@File       ：server.py

@Author     : hsn

@Date       ：2023/3/1 下午8:35

@Version    : 2.1.1
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
import copy
import importlib
import logging
import os.path
import platform
import sys
import threading
import time

from RPDB.database import RPDB
from flask import Flask, request
from flask_cors import CORS
from gevent import pywsgi
from permitronix import Permitronix

import util
from containers import User, ReturnData
from event.event_manager import EventManager
from event.recv_event import RecvEvent


class Server:
    ver = '2.1.1'

    def __init__(self, address: tuple[str, int] = None, debug: bool = False, name=__name__, config=None):
        # Initialize Flask object
        self.app = Flask(__name__)
        if debug:
            self.app.config['SESSION_COOKIE_SAMESITE'] = 'None'
            self.app.config['SESSION_COOKIE_SECURE'] = False

        # Enable Cross-Origin Resource Sharing (CORS)
        CORS(self.app)

        # Set host and port for the server
        self.host, self.port = address if address is not None else ('0.0.0.0', 8080)

        # Set debug mode
        self.debug = debug

        # Initialize config
        self.config = {} if config is None else copy.deepcopy(config)

        # Get logger
        self.logger = logging.getLogger(__name__)

        # Generate AES token
        key_path = os.path.join(os.getcwd(), f'{name}.key')
        if not os.path.exists(key_path):
            self.key = util.get_random_token(16)
            with open(key_path, 'w', encoding='utf8') as f:
                f.write(self.key)
        else:
            with open(key_path, 'r', encoding='utf8') as f:
                self.key = f.read()

        # Set event manager
        self.e_mgr = EventManager(self)

        # Set timeout
        self.event_timeout = 604_800  # 1 week
        self.short_id_timeout = 300  # 5 minutes

        # Keep track of active users
        self.activity_dict = {}
        self.activity_dict_lock = threading.Lock()

        # Initialize databases
        self.db_account = RPDB(os.path.join(os.getcwd(), 'data', 'account'))
        self.db_event = RPDB(os.path.join(os.getcwd(), 'data', 'event'))
        self.db_group = RPDB(os.path.join(os.getcwd(), 'data', 'group'))
        self.db_email = RPDB(os.path.join(os.getcwd(), 'data', 'email'))
        self.db_permitronix = RPDB(os.path.join(os.getcwd(), 'data', 'permitronix'))

        self.event_short_id_table = {}

        self.permitronix: Permitronix = Permitronix(self.db_permitronix)

    def server_thread(self):
        # Start the WSGI server
        server = pywsgi.WSGIServer((self.host, self.port), self.app)
        server.serve_forever()

    def activity_list_thread(self):
        # Monitor the activity of users and mark them as offline if they are inactive
        while True:
            del_list = []
            with self.activity_dict_lock:
                for i in self.activity_dict:
                    self.activity_dict[i] -= 1
                    if self.activity_dict[i] <= 0:
                        del_list.append(i)
                for i in del_list:
                    self.activity_dict.pop(i)

            for i in del_list:
                with self.open_user(i) as u:
                    user: User = u.value
                    user.status = 'offline'
            time.sleep(1)

    def event_cleaner_thread(self):
        # Remove expired events from the event database
        while True:
            del_e_count = 0
            del_sid_count = 0
            for i in copy.deepcopy(self.db_event.keys):
                with self.db_event.enter(i) as v:
                    e: dict = v.value
                    if e and time.time() - e['time'] > self.event_timeout:
                        v.value = None
                        del_e_count += 1

            for k, v in copy.deepcopy(self.event_short_id_table).items():
                try:
                    can_del = v not in self.db_event.keys or self.get_user_event(v)['time'] > self.short_id_timeout
                except:
                    can_del = True
                if can_del:
                    self.event_short_id_table.pop(k)
                    del_sid_count += 1
            if del_sid_count>0 or del_e_count>0:
                self.logger.info(f'Event cleaner: {del_e_count} events deleted, {del_sid_count} short IDs deleted.')
            time.sleep(30)

    def load_auxiliary_events(self):
        # get all auxiliary events
        for name_ in os.listdir(os.path.join('event', 'auxiliary_events')):
            # get file name
            name = "".join(name_.split(".")[:-1])
            if len(name) == 0:
                continue

            # get class name
            class_name = ''
            for i in name.split("_"):
                class_name += i[0].upper() + ('' if len(i) < 2 else i[1:])

            # logout
            self.logger.debug(f'Auxiliary event "{name}" loaded.')

            # import module and add event
            event_module = importlib.import_module(f'event.auxiliary_events.{name}')
            event_class = getattr(event_module, class_name)
            self.e_mgr.add_auxiliary_event(event_class.main_event, event_class)

    def start(self):
        # Log server start
        self.logger.info('Starting server...')

        # Load auxiliary events
        self.logger.info('Loading auxiliary events...')
        self.load_auxiliary_events()

        # Create route for handling incoming requests
        self.logger.info('Creating route...')

        @self.app.route('/api/<path:path>', methods=['GET', 'POST'])
        def recv(path):
            rt = self.e_mgr.create_event(RecvEvent, request, path)
            # format return data
            if isinstance(rt, ReturnData):
                rt = rt.jsonify()
            elif rt is None:
                rt = ReturnData(ReturnData.NULL, '').jsonify()
            return rt

        # Start server threads
        self.logger.info('Starting server threads...')
        server_thread = threading.Thread(target=self.server_thread, daemon=True, name='server_thread')
        cleaner_thread = threading.Thread(target=self.event_cleaner_thread, daemon=True, name='event_cleaner_thread')
        activity_thread = threading.Thread(target=self.activity_list_thread, daemon=True, name='activity_thread')
        threads = [server_thread, cleaner_thread, activity_thread]
        for t in threads:
            t.start()

        # Log server status and information
        self.logger.info('Server started.')
        self.logger.info(f'Server listening on {self.host}:{self.port}.')
        self.logger.info('----Server information----')
        self.logger.info(f'Version: {self.ver}')
        self.logger.info(f'Python version: {sys.version}')
        self.logger.info(f'System version: {platform.platform()}')
        self.logger.info(f'Debug mode: {self.debug}')
        self.logger.info(f'Current working directory: {os.getcwd()}')
        self.logger.info('--------------------------')

        try:
            # Wait for the server thread to finish
            while True:
                server_thread.join(0.1)
        except KeyboardInterrupt:
            # save data and exit
            self.logger.info('Saving data...')
            self.db_event.close()
            self.db_email.close()
            self.db_group.close()
            self.db_account.close()
            self.db_permitronix.close()
            try:
                sys.exit()
            except SystemExit:
                self.logger.info('Server closed.')

    def open_user(self, user_id):
        return self.db_account.enter(user_id)

    def is_user_exist(self, user_id):
        with self.open_user(user_id) as u:
            return u.value is not None

    def get_user_event(self, event_id: str) -> dict:
        eid = copy.copy(event_id)
        if eid in self.event_short_id_table:
            eid = self.event_short_id_table[eid]
        with self.db_event.enter(eid) as e:
            return e.value
