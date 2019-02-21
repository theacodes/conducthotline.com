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

import hotline.telephony.chatroom
from hotline import injector
import peewee
import playhouse.db_url

db = peewee.Proxy()


@injector.needs("secrets.database")
def initialize_db(database):
    db.initialize(playhouse.db_url.connect(database))


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
    room = SerializableField(hotline.telephony.chatroom.Chatroom)


class ChatroomConnection(BaseModel):
    user_number = peewee.CharField()
    relay_number = peewee.CharField()
    user_name = peewee.CharField()
    chatroom = peewee.ForeignKeyField(Chatroom, backref="connections")

    class Meta:
        primary_key = peewee.CompositeKey("user_number", "relay_number")


def find_unused_event_numbers():
    return list(
        Number.select()
        .join(Event, peewee.JOIN.LEFT_OUTER, on=(Event.primary_number_id == Number.id))
        .where(Event.primary_number_id.is_null())
        .limit(5)
    )


def find_unused_relay_number(event_number, organizer_number):
    """Find a relay number that isn't currently used by an existing chatroom
    connection."""
    # TODO: Should probably be a join, but its unlikely this list will
    # get big enough in the near future to be an issue.
    used_relay_numbers_query = ChatroomConnection.select(
        ChatroomConnection.relay_number
    ).where(ChatroomConnection.user_number == organizer_number)

    used_relay_numbers = [row.relay_number for row in used_relay_numbers_query]

    print("Used relay numbers: ", used_relay_numbers)

    # Don't use the event number as a relay number
    used_relay_numbers.append(event_number)

    unused_number_query = (
        Number.select(Number.number)
        .where(Number.number.not_in(used_relay_numbers))
        .limit(1)
    )

    numbers = [row.number for row in unused_number_query]

    print("Available relay numbers: ", numbers)

    if not numbers:
        return None
    else:
        return numbers[0]
