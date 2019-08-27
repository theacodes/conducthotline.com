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

"""An abstract chat room.

Whenever one person sends a message, it is forwarded to the other users. The
"number" used for relaying can be set per user.

For example,

Alice sends the message "Hello" to 1234,
Bob receives a message from 3456 that says "Alice: Hello",
Sandy recieves a message from 6789 that says "Alice: "Hello".

This class does not know how to send messages and must be provided with a
function that can send messages. This keeps it decoupled from any particular
way of sending or receiving messages.
"""

import json
from collections import namedtuple
from typing import Any, Optional

from typing_extensions import Protocol

_User = namedtuple("_User", ["name", "number", "relay"])


class SendFn(Protocol):
    def __call__(self, sender: str, to: str, message: str) -> Any:
        pass


class Chatroom:
    def __init__(self):
        self._users = {}

    def remove_user(self, number: str):
        return self._users.pop(number, None)

    def add_user(self, name: str, number: str, relay: str):
        self._users[number] = _User(name=name, number=number, relay=relay)

    @property
    def users(self):
        return self._users.values()

    def get_user_by_name(self, name: str) -> Optional[_User]:
        for user in self._users.values():
            if user.name == name:
                return user
        return None

    def relay(self, user_number: str, message: str, send_message: SendFn):
        sender = self._users[user_number]
        message = f"{sender.name}: {message}"

        for user in self._users.values():
            # Don't send the message back to the user.
            if user == sender:
                continue

            send_message(sender=user.relay, to=user.number, message=message)

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
