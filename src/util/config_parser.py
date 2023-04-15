#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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

"""
@File       : config_parser.py

@Author     : hsn

@Date       : 4/9/23 9:22 AM

@Version    : 1.0.0
"""
import copy
import json
from os import PathLike
from typing import IO, Union


class ConfigParser:
    def __init__(self, config: Union[dict, PathLike, str, IO[bytes]]):
        if isinstance(config, dict):
            self.config: dict = config
        elif isinstance(config, (str, PathLike)):
            with open(config, 'r') as f:
                self.config: dict = json.load(f)
        elif isinstance(config, IO):
            self.config: dict = json.load(config)

    def __contains__(self, item):
        return self.get_from_pointer(item) is not None

    def get_from_pointer(self, pointer: Union[str, int], default=None):
        json_path = str(pointer).split('/')
        json_path = list(filter(lambda x: bool(x), json_path))
        config = copy.deepcopy(self.config)

        for i in json_path:

            if config is None:
                return default
            if isinstance(config, list):
                i = int(i)
                if i >= len(config):
                    return default
                config = config[i]
            elif isinstance(config, dict):
                config = config.get(i, default)
            else:
                return default

        return config

    def __getitem__(self, item):
        return self.get_from_pointer(item)

    def __getattr__(self, item):
        return self.config.__getattribute__(item)