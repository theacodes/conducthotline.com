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

import pytest

from hotline.database import create_tables, highlevel
from hotline.database import models as db
from hotline.telephony import smschat


@pytest.fixture
def database(tmpdir):
    db_file = tmpdir.join("database.sqlite")
    highlevel.initialize_db(database=f"sqlite:///{db_file}")

    create_tables.create_tables()

    with db.db:
        yield db


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_no_event(send_sms, database):

    with pytest.raises(smschat.EventDoesNotExist):
        smschat.handle_message("1234", "5678", "Hello")

    send_sms.assert_not_called()


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


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_no_organizers(send_sms, database):
    create_event()

    with pytest.raises(smschat.NoOrganizersAvailable):
        smschat.handle_message("1234", "5678", "Hello")

    send_sms.assert_not_called()


def create_organizers(event):
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

    member = db.EventMember()
    member.name = "Unverified Judy"
    member.number = "303"
    member.event = event
    member.verified = False
    member.save()

    return list(db.EventMember().select())


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_no_relays(send_sms, database):
    event = create_event()
    create_organizers(event)

    with pytest.raises(smschat.NoRelaysAvailable):
        smschat.handle_message("1234", "5678", "Hello")

    send_sms.assert_not_called()


def create_relays():
    number = db.Number()
    number.number = "1111"
    number.country = "US"
    number.save()

    number = db.Number()
    number.number = "2222"
    number.country = "US"
    number.save()

    return list(db.Number.select())


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_new_chat(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()

    smschat.handle_message("1234", "5678", "Hello")

    # A total of 5 messages:
    # The first should acknolwege the reporter.
    # The next two should have been sent to the two verified organizers to
    # introduce the chat.
    # The last two should relay the reporter's message.
    assert send_sms.call_count == 5
    send_sms.assert_has_calls(
        [
            mock.call(
                sender="5678",
                to="1234",
                message="You have started a new chat with the organizers of Test event.",
            ),
            # The sender should be the *first available* relay number (1111)
            mock.call(
                sender="1111",
                to="101",
                message="This is the beginning of a new chat for Test event, the last 4 digits of the reporters number are 1234.",
            ),
            mock.call(
                sender="1111",
                to="202",
                message="This is the beginning of a new chat for Test event, the last 4 digits of the reporters number are 1234.",
            ),
            mock.call(sender="1111", to="101", message="Reporter: Hello"),
            mock.call(sender="1111", to="202", message="Reporter: Hello"),
        ]
    )

    # The database should have an entry for this chat.
    assert db.Chatroom.select().count() == 1

    # And three entries for the connections, as there are three people in the
    # chat.
    room = db.Chatroom.get()
    connections = (
        db.ChatroomConnection.select()
        .where(db.ChatroomConnection.chatroom == room)
        .order_by(db.ChatroomConnection.user_number)
    )
    assert len(connections) == 3
    assert connections[0].user_name == "Bob"
    assert connections[0].user_number == "101"
    assert connections[0].relay_number == "1111"
    assert connections[1].user_name == "Reporter"
    assert connections[1].user_number == "1234"
    assert connections[1].relay_number == "5678"
    assert connections[2].user_name == "Alice"
    assert connections[2].user_number == "202"
    assert connections[2].relay_number == "1111"


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_reply(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()

    # Send initial message to establish the chat.
    smschat.handle_message("1234", "5678", "Hello")

    # Reset the mock for send_sms
    send_sms.reset_mock()

    # Send a reply from one of the organizers.
    smschat.handle_message("101", "1111", "Goodbye")

    # Two messages should have been sent. One to the reporter, and one to the
    # other verified member.
    # The sender should be the hotline number for the reporter and the *first*
    # relay number (1111) for the member.
    assert send_sms.call_count == 2
    send_sms.assert_has_calls(
        [
            mock.call(sender="5678", to="1234", message="Bob: Goodbye"),
            mock.call(sender="1111", to="202", message="Bob: Goodbye"),
        ]
    )


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_event(send_sms):
    err = smschat.EventDoesNotExist()

    smschat.handle_sms_chat_error(err, "1234", "5678")

    send_sms.assert_called_once_with(sender="5678", to="1234", message=mock.ANY)

    message = send_sms.mock_calls[0][2]["message"]

    assert "event configured" in message


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_organizers(send_sms):
    err = smschat.NoOrganizersAvailable()

    smschat.handle_sms_chat_error(err, "1234", "5678")

    send_sms.assert_called_once_with(sender="5678", to="1234", message=mock.ANY)

    message = send_sms.mock_calls[0][2]["message"]

    assert "aren't any organizers" in message


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_relays(send_sms):
    err = smschat.NoRelaysAvailable()

    smschat.handle_sms_chat_error(err, "1234", "5678")

    send_sms.assert_called_once_with(sender="5678", to="1234", message=mock.ANY)

    message = send_sms.mock_calls[0][2]["message"]

    assert "aren't any relays" in message
