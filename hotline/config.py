# Copyright 2019 Alethea Katherine Flowers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Configures dependency injection across the application."""

import json

from hotline import injector
import hotline.database.lowlevel


def _load_secrets():
    with open("secrets.json") as fh:
        secrets = json.load(fh)

    injector.set("secrets", secrets)


def _initialize_resources():
    # Initialize the database, now that we have configuration.
    hotline.database.lowlevel.initialize_db()


def load():
    _load_secrets()
    _initialize_resources()
