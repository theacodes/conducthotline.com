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

"""Implements a chat room via sms.

Whenever one person sends a message, it is forwarded to the other users. The
number used for relaying can be set per user.

For example,

Alice sends the message "Hello" to 1234,
Bob receives a message from 3456 that says "Alice: Hello",
Sandy recieves a message from 6789 that says "Alice: "Hello".
"""

import json
from collections import namedtuple

from hotline.telephony import lowlevel

_User = namedtuple("_User", ["name", "number", "relay"])


class Chatroom:
    def __init__(self):
        self._users = {}

    def add_user(self, name: str, user_number: str, relay_number: str):
        self._users[user_number] = _User(
            name=name, number=user_number, relay=relay_number
        )

    @property
    def users(self):
        return self._users.values()

    def relay(self, user_number: str, message: str):
        sender = self._users[user_number]
        message = f"{sender.name}: {message}"

        for user in self._users.values():
            # Don't send the message back to the user.
            if user == sender:
                continue

            resp = lowlevel.send_sms(sender=user.relay, to=user.number, message=message)
            print(resp)

    def __str__(self) -> str:
        users = [user.name for user in self._users.values()]
        return f"<Chatroom users=[{', '.join(users)}]>"

    def serialize(self) -> str:
        return json.dumps({"__class__": self.__class__.__name__, "_users": self._users})

    @classmethod
    def deserialize(cls, data: str):
        loaded_data = json.loads(data)
        instance = cls()
        instance._users = {
            key: _User(*value) for key, value in loaded_data["_users"].items()
        }

        return instance
