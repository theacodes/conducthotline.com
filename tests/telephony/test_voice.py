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

from unittest import mock

import nexmo
import pytest

from hotline.database import create_tables, highlevel
from hotline.database import models as db
from hotline.telephony import voice


@pytest.fixture
def database(tmpdir):
    db_file = tmpdir.join("database.sqlite")
    highlevel.initialize_db(database=f"sqlite:///{db_file}")

    create_tables.create_tables()

    with db.db:
        yield db


def test_handle_inbound_call_no_event(database):
    nexmo_client = mock.create_autospec(nexmo.Client)

    ncco = voice.handle_inbound_call(
        reporter_number="1234",
        event_number="5678",
        conversation_uuid="conversation",
        call_uuid="call",
        host="example.com",
        client=nexmo_client,
    )

    assert len(ncco) == 1
    assert "No event was found" in ncco[0]["text"]


def create_event():
    number = db.Number()
    number.number = "5678"
    number.country = "US"
    number.save()

    event = db.Event()
    event.name = "Test event"
    event.slug = "test"
    event.owner_user_id = "abc123"
    event.primary_number = number.number
    event.primary_number_id = number
    event.save()

    return event


def test_handle_inbound_call_blocked(database):
    event = create_event()
    add_unverfied_members(event)

    nexmo_client = mock.create_autospec(nexmo.Client)

    db.BlockList.create(event=event, number="1234", blocked_by="test")

    ncco = voice.handle_inbound_call(
        reporter_number="1234",
        event_number="5678",
        conversation_uuid="conversation",
        call_uuid="call",
        host="example.com",
        client=nexmo_client,
    )

    assert len(ncco) == 1
    assert "unavailable" in ncco[0]["text"]


def add_unverfied_members(event):
    member = db.EventMember()
    member.name = "Unverified Judy"
    member.number = "303"
    member.event = event
    member.verified = False
    member.save()


def test_handle_inbound_call_no_members(database):
    event = create_event()
    add_unverfied_members(event)

    nexmo_client = mock.create_autospec(nexmo.Client)

    ncco = voice.handle_inbound_call(
        reporter_number="1234",
        event_number="5678",
        conversation_uuid="conversation",
        call_uuid="call",
        host="example.com",
        client=nexmo_client,
    )

    assert len(ncco) == 1
    assert "no verified members" in ncco[0]["text"]


def add_members(event):
    member = db.EventMember()
    member.name = "Bob"
    member.number = "101"
    member.event = event
    member.verified = True
    member.save()

    member = db.EventMember()
    member.name = "Alice"
    member.number = "202"
    member.event = event
    member.verified = True
    member.save()


def test_handle_inbound_call(database):
    event = create_event()
    add_members(event)

    nexmo_client = mock.create_autospec(nexmo.Client)

    ncco = voice.handle_inbound_call(
        reporter_number="1234",
        event_number="5678",
        conversation_uuid="conversation",
        call_uuid="call",
        host="example.com",
        client=nexmo_client,
    )

    # The caller should have been greeted and then connected to a conference
    # call.
    assert len(ncco) == 2
    assert ncco[0]["action"] == "talk"
    assert "Thank you" in ncco[0]["text"]
    assert ncco[1]["action"] == "conversation"
    assert ncco[1]["name"] == "conversation"

    # The nexmo client should have been used to call the two organizers.
    assert nexmo_client.create_call.call_count == 2

    calls_created = [call[1][0] for call in nexmo_client.create_call.mock_calls]

    assert calls_created[0]["to"] == [{"type": "phone", "number": "101"}]
    assert calls_created[0]["from"] == {"type": "phone", "number": "5678"}
    assert "example.com" in calls_created[0]["answer_url"][0]
    assert calls_created[1]["to"] == [{"type": "phone", "number": "202"}]
    assert calls_created[1]["from"] == {"type": "phone", "number": "5678"}
    assert "example.com" in calls_created[1]["answer_url"][0]


def test_handle_inbound_call_custom_greeting(database):
    event = create_event()
    add_members(event)

    nexmo_client = mock.create_autospec(nexmo.Client)

    event.voice_greeting = "Ahoyhoy!"
    event.save()

    ncco = voice.handle_inbound_call(
        reporter_number="1234",
        event_number="5678",
        conversation_uuid="conversation",
        call_uuid="call",
        host="example.com",
        client=nexmo_client,
    )

    # The caller should have been greeted with the custom greeting.
    assert ncco[0]["action"] == "talk"
    assert ncco[0]["text"] == "Ahoyhoy!"


def test_handle_member_answer_no_event(database):
    nexmo_client = mock.create_autospec(nexmo.Client)

    ncco = voice.handle_member_answer(
        event_number="5678",
        member_number="202",
        origin_conversation_uuid="conversation",
        origin_call_uuid="call",
        client=nexmo_client,
    )

    assert len(ncco) == 1
    assert ncco[0]["action"] == "talk"
    assert "error" in ncco[0]["text"]


def test_handle_member_answer(database):
    event = create_event()
    add_members(event)

    nexmo_client = mock.create_autospec(nexmo.Client)

    ncco = voice.handle_member_answer(
        event_number="5678",
        member_number="202",
        origin_conversation_uuid="conversation",
        origin_call_uuid="call",
        client=nexmo_client,
    )

    assert len(ncco) == 2

    # The member should have been greeted and then connected to a conference
    # call.
    assert ncco[0]["action"] == "talk"
    assert "Test event" in ncco[0]["text"]
    assert "Alice" in ncco[0]["text"]
    assert ncco[1]["action"] == "conversation"
    assert ncco[1]["name"] == "conversation"

    # The conference call should have been notified that the member is joining.
    nexmo_client.send_speech.assert_called_once_with("call", text=mock.ANY)
