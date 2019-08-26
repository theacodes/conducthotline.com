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


reporter_number = "1234"
reporter_name = "Reporter"


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_no_event(send_sms, database):

    with pytest.raises(smschat.EventDoesNotExist):
        smschat.handle_message(reporter_number, event_number, "Hello")

    send_sms.assert_not_called()


event_number = "5678"
event_name = "Test event"


def create_event():
    number = db.Number()
    number.number = event_number
    number.country = "US"
    number.features = ""
    number.save()

    event = db.Event()
    event.name = event_name
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
        smschat.handle_message(reporter_number, event_number, "Hello")

    send_sms.assert_not_called()


bob_organizer_name = "Bob"
bob_organizer_number = "101"
alice_organizer_name = "Alice"
alice_organizer_number = "202"


def create_organizers(event):
    member = db.EventMember()
    member.name = bob_organizer_name
    member.number = bob_organizer_number
    member.event = event
    member.verified = True
    member.save()

    member = db.EventMember()
    member.name = alice_organizer_name
    member.number = alice_organizer_number
    member.event = event
    member.verified = True
    member.save()

    member = db.EventMember()
    member.name = "Judy"
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
        smschat.handle_message(reporter_number, event_number, "Hello")

    send_sms.assert_not_called()


relay_number = "1111"


def create_relays():
    number = db.Number()
    number.number = relay_number
    number.country = "US"
    number.features = ""
    number.pool = db.NumberPool.SMS_RELAY
    number.save()

    number = db.Number()
    number.number = "2222"
    number.country = "US"
    number.features = ""
    number.pool = db.NumberPool.SMS_RELAY
    number.save()

    return list(db.Number.select())


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_new_chat(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()

    smschat.handle_message(reporter_number, event_number, "Hello")

    # A total of 5 messages:
    # The first should acknolwege the reporter.
    # The next two should have been sent to the two verified organizers to
    # introduce the chat.
    # The last two should relay the reporter's message.
    assert send_sms.call_count == 5
    send_sms.assert_has_calls(
        [
            mock.call(
                sender=event_number,
                to=reporter_number,
                message=f"You have started a new chat with the organizers of {event_name}.",
            ),
            # The sender should be the *first available* relay number (1111)
            mock.call(
                sender=relay_number,
                to=bob_organizer_number,
                message=f"This is the beginning of a new chat for {event_name}, the last 4 digits of the reporter's number are {reporter_number}.",
            ),
            mock.call(
                sender=relay_number,
                to=alice_organizer_number,
                message=f"This is the beginning of a new chat for {event_name}, the last 4 digits of the reporter's number are {reporter_number}.",
            ),
            mock.call(sender=relay_number, to=bob_organizer_number, message=f"{reporter_name}: Hello"),
            mock.call(sender=relay_number, to=alice_organizer_number, message=f"{reporter_name}: Hello"),
        ]
    )

    # The database should have an entry for this chat.
    assert db.SmsChat.select().count() == 1

    # And three entries for the connections, as there are three people in the
    # chat.
    room = db.SmsChat.get()
    connections = (
        db.SmsChatConnection.select()
        .where(db.SmsChatConnection.smschat == room)
        .order_by(db.SmsChatConnection.user_number)
    )
    assert len(connections) == 3
    assert connections[0].user_name == bob_organizer_name
    assert connections[0].user_number == bob_organizer_number
    assert connections[0].relay_number == relay_number
    assert connections[1].user_name == reporter_name
    assert connections[1].user_number == reporter_number
    assert connections[1].relay_number == event_number
    assert connections[2].user_name == alice_organizer_name
    assert connections[2].user_number == alice_organizer_number
    assert connections[2].relay_number == relay_number


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_reply(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()

    # Send initial message to establish the chat.
    smschat.handle_message(reporter_number, event_number, "Hello")

    # Reset the mock for send_sms
    send_sms.reset_mock()

    # Send a reply from one of the organizers.
    smschat.handle_message(bob_organizer_number, relay_number, "Goodbye")

    # Two messages should have been sent. One to the reporter, and one to the
    # other verified member.
    # The sender should be the hotline number for the reporter and the *first*
    # relay number (1111) for the member.
    assert send_sms.call_count == 2
    send_sms.assert_has_calls(
        [
            mock.call(sender=event_number, to=reporter_number, message=f"{bob_organizer_name}: Goodbye"),
            mock.call(sender=relay_number, to=alice_organizer_number, message=f"{bob_organizer_name}: Goodbye"),
        ]
    )


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_event(send_sms):
    err = smschat.EventDoesNotExist()

    smschat.handle_sms_chat_error(err, reporter_number, event_number)

    send_sms.assert_called_once_with(sender=event_number, to=reporter_number, message=mock.ANY)

    message = send_sms.mock_calls[0][2]["message"]

    assert "event configured" in message


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_organizers(send_sms):
    err = smschat.NoOrganizersAvailable()

    smschat.handle_sms_chat_error(err, reporter_number, event_number)

    send_sms.assert_called_once_with(sender=event_number, to=reporter_number, message=mock.ANY)

    message = send_sms.mock_calls[0][2]["message"]

    assert "aren't any organizers" in message


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_relays(send_sms):
    err = smschat.NoRelaysAvailable()

    smschat.handle_sms_chat_error(err, reporter_number, event_number)

    send_sms.assert_called_once_with(sender=event_number, to=reporter_number, message=mock.ANY)

    message = send_sms.mock_calls[0][2]["message"]

    assert "aren't any relays" in message
