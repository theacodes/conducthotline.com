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

"""Low-level database primitives. Moved here to prevent bleeding db-specific
stuff into the higher-level interface."""

import peewee

import hotline.telephony.chatroom

db = peewee.SqliteDatabase("hotline.db")


class BaseModel(peewee.Model):
    class Meta:
        database = db


class SerializableField(peewee.TextField):
    def __init__(self, cls, *args, **kwargs):
        self._cls = cls
        super().__init__(*args, **kwargs)

    def db_value(self, value):
        return value.serialize()

    def python_value(self, value):
        return self._cls.deserialize(value)


class Chatroom(BaseModel):
    event_name = peewee.TextField()
    room = SerializableField(hotline.telephony.chatroom.Chatroom)


class ChatroomConnection(BaseModel):
    user_number = peewee.CharField()
    relay_number = peewee.CharField()
    user_name = peewee.CharField()
    chatroom = peewee.ForeignKeyField(Chatroom, backref="connections")

    class Meta:
        primary_key = peewee.CompositeKey("user_number", "relay_number")
