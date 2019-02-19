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

"""High-level database operations."""

from typing import Optional

import peewee

import hotline.telephony.chatroom
from hotline.database import lowlevel


def save_room(room: hotline.telephony.chatroom.Chatroom):
    with lowlevel.db.atomic():
        room_row = lowlevel.Chatroom.create(event_name="test", room=room)

        for connection in room.users:
            lowlevel.ChatroomConnection.create(
                user_number=connection.number,
                relay_number=connection.relay,
                user_name=connection.name,
                chatroom=room_row,
            )


def find_room_for_user(
    user_number: str, relay_number: str
) -> Optional[hotline.telephony.chatroom.Chatroom]:
    with lowlevel.db:
        try:
            connection = lowlevel.ChatroomConnection.get(
                lowlevel.ChatroomConnection.user_number == user_number,
                lowlevel.ChatroomConnection.relay_number == relay_number,
            )

            # This could be faster with a join, but I'm not terribly worried about speed right now.
            return connection.chatroom.room

        except peewee.DoesNotExist:
            return None
