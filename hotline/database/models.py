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

import hotline.chatroom

db = peewee.Proxy()


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


class Number(BaseModel):
    number = peewee.TextField()


class Event(BaseModel):
    # Always required stuff.
    name = peewee.TextField()
    slug = peewee.CharField(unique=True)
    owner_user_id = peewee.CharField()

    # Number assignement.
    # Stored as destructured as well to speed things up a little.
    primary_number = peewee.TextField(null=True)
    primary_number_id = peewee.ForeignKeyField(Number, null=True)

    # Information fields.
    coc_link = peewee.TextField(null=True, index=False)
    website = peewee.TextField(null=True, index=False)
    contact_email = peewee.TextField(null=True, index=False)
    location = peewee.TextField(null=True, index=False)


class EventMember(BaseModel):
    event = peewee.ForeignKeyField(Event, backref="members")
    name = peewee.TextField()
    number = peewee.TextField()
    verified = peewee.BooleanField()


class Chatroom(BaseModel):
    event = peewee.ForeignKeyField(Event)
    room = SerializableField(hotline.chatroom.Chatroom)


class ChatroomConnection(BaseModel):
    user_number = peewee.CharField()
    relay_number = peewee.CharField()
    user_name = peewee.CharField()
    chatroom = peewee.ForeignKeyField(Chatroom, backref="connections")

    class Meta:
        primary_key = peewee.CompositeKey("user_number", "relay_number")
