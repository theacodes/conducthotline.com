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


EVENT_NUMBER = "5678"
EVENT_NAME = "Test event"
REPORTER_NUMBER = "1234"
REPORTER_NAME = "Reporter"


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_no_event(send_sms, database):

    with pytest.raises(smschat.EventDoesNotExist):
        smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    send_sms.assert_not_called()


def create_event():
    number = db.Number()
    number.number = EVENT_NUMBER
    number.country = "US"
    number.features = ""
    number.save()

    event = db.Event()
    event.name = EVENT_NAME
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
        smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    send_sms.assert_not_called()


BOB_ORGANIZER_NAME = "Bob"
BOB_ORGANIZER_NUMBER = "101"
ALICE_ORGANIZER_NAME = "Alice"
ALICE_ORGANIZER_NUMBER = "202"


def create_organizers(event):
    member = db.EventMember()
    member.name = BOB_ORGANIZER_NAME
    member.number = BOB_ORGANIZER_NUMBER
    member.event = event
    member.verified = True
    member.save()

    member = db.EventMember()
    member.name = ALICE_ORGANIZER_NAME
    member.number = ALICE_ORGANIZER_NUMBER
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
        smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    send_sms.assert_not_called()


RELAY_NUMBER = "1111"


def create_relays():
    number = db.Number()
    number.number = RELAY_NUMBER
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

    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    # A total of 5 messages:
    # The first should acknolwege the reporter.
    # The next two should have been sent to the two verified organizers to
    # introduce the chat.
    # The last two should relay the reporter's message.
    assert send_sms.call_count == 5
    send_sms.assert_has_calls(
        [
            mock.call(
                sender=EVENT_NUMBER,
                to=REPORTER_NUMBER,
                message=f"You have started a new chat with the organizers of {EVENT_NAME}.",
            ),
            # The sender should be the *first available* relay number (1111)
            mock.call(
                sender=RELAY_NUMBER,
                to=BOB_ORGANIZER_NUMBER,
                message=f"This is the beginning of a new chat for {EVENT_NAME}, the last 4 digits of the reporter's number are {REPORTER_NUMBER}.",
            ),
            mock.call(
                sender=RELAY_NUMBER,
                to=ALICE_ORGANIZER_NUMBER,
                message=f"This is the beginning of a new chat for {EVENT_NAME}, the last 4 digits of the reporter's number are {REPORTER_NUMBER}.",
            ),
            mock.call(
                sender=RELAY_NUMBER,
                to=BOB_ORGANIZER_NUMBER,
                message=f"{REPORTER_NAME}: Hello",
            ),
            mock.call(
                sender=RELAY_NUMBER,
                to=ALICE_ORGANIZER_NUMBER,
                message=f"{REPORTER_NAME}: Hello",
            ),
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
    assert connections[0].user_name == BOB_ORGANIZER_NAME
    assert connections[0].user_number == BOB_ORGANIZER_NUMBER
    assert connections[0].relay_number == RELAY_NUMBER
    assert connections[1].user_name == REPORTER_NAME
    assert connections[1].user_number == REPORTER_NUMBER
    assert connections[1].relay_number == EVENT_NUMBER
    assert connections[2].user_name == ALICE_ORGANIZER_NAME
    assert connections[2].user_number == ALICE_ORGANIZER_NUMBER
    assert connections[2].relay_number == RELAY_NUMBER


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_reply(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()

    # Send initial message to establish the chat.
    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    # Reset the mock for send_sms
    send_sms.reset_mock()

    # Send a reply from one of the organizers.
    smschat.handle_message(BOB_ORGANIZER_NUMBER, RELAY_NUMBER, "Goodbye")

    # Two messages should have been sent. One to the reporter, and one to the
    # other verified member.
    # The sender should be the hotline number for the reporter and the *first*
    # relay number (1111) for the member.
    assert send_sms.call_count == 2
    send_sms.assert_has_calls(
        [
            mock.call(
                sender=EVENT_NUMBER,
                to=REPORTER_NUMBER,
                message=f"{BOB_ORGANIZER_NAME}: Goodbye",
            ),
            mock.call(
                sender=RELAY_NUMBER,
                to=ALICE_ORGANIZER_NUMBER,
                message=f"{BOB_ORGANIZER_NAME}: Goodbye",
            ),
        ]
    )


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_event(send_sms):
    err = smschat.EventDoesNotExist()

    smschat.handle_sms_chat_error(err, REPORTER_NUMBER, EVENT_NUMBER)

    send_sms.assert_called_once_with(
        sender=EVENT_NUMBER, to=REPORTER_NUMBER, message=mock.ANY
    )

    message = send_sms.mock_calls[0][2]["message"]

    assert "event configured" in message


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_organizers(send_sms):
    err = smschat.NoOrganizersAvailable()

    smschat.handle_sms_chat_error(err, REPORTER_NUMBER, EVENT_NUMBER)

    send_sms.assert_called_once_with(
        sender=EVENT_NUMBER, to=REPORTER_NUMBER, message=mock.ANY
    )

    message = send_sms.mock_calls[0][2]["message"]

    assert "aren't any organizers" in message


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_sms_chat_error_no_relays(send_sms):
    err = smschat.NoRelaysAvailable()

    smschat.handle_sms_chat_error(err, REPORTER_NUMBER, EVENT_NUMBER)

    send_sms.assert_called_once_with(
        sender=EVENT_NUMBER, to=REPORTER_NUMBER, message=mock.ANY
    )

    message = send_sms.mock_calls[0][2]["message"]

    assert "aren't any relays" in message
