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
EVENT_NUMBER_2 = "8765"
EVENT_NAME_2 = "Test event 2"
REPORTER_NUMBER = "1234"
REPORTER_NAME = "Reporter"


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_no_event(send_sms, database):

    with pytest.raises(smschat.EventDoesNotExist):
        smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    send_sms.assert_not_called()


def create_event(name=EVENT_NAME, number=EVENT_NUMBER):
    number_ = db.Number()
    number_.number = number
    number_.country = "US"
    number_.features = ""
    number_.save()

    event = db.Event()
    event.name = name
    event.slug = name
    event.owner_user_id = "abc123"
    event.primary_number = number_.number
    event.primary_number_id = number_
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
RELAY_NUMBER_2 = "2222"


def create_relays():
    number = db.Number()
    number.number = RELAY_NUMBER
    number.country = "US"
    number.features = ""
    number.pool = db.NumberPool.SMS_RELAY
    number.save()

    number = db.Number()
    number.number = RELAY_NUMBER_2
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
    # The first should acknowledge the reporter.
    # The next two should have been sent to the two verified organizers to
    # introduce the chat.
    # The last two should relay the reporter's message.
    assert send_sms.call_count == 6
    send_sms.assert_has_calls(
        [
            mock.call(
                sender=EVENT_NUMBER,
                to=REPORTER_NUMBER,
                message=f"You have started a new chat with the organizers of {EVENT_NAME}.",
            ),
            # The reporter should get a notice about how to opt out.
            mock.call(
                sender=EVENT_NUMBER,
                to=REPORTER_NUMBER,
                message="Reply STOP at any time to opt-out of receiving messages from this conversation.",
            ),
            # The sender should be the *first available* relay number (1111)
            mock.call(
                sender=RELAY_NUMBER,
                to=BOB_ORGANIZER_NUMBER,
                message=f"This is the beginning of a new chat for {EVENT_NAME}, the last 4 digits of the reporter's number are {REPORTER_NUMBER}. "
                "Reply STOP at any time to opt-out of receiving messages from this conversation.",
            ),
            mock.call(
                sender=RELAY_NUMBER,
                to=ALICE_ORGANIZER_NUMBER,
                message=f"This is the beginning of a new chat for {EVENT_NAME}, the last 4 digits of the reporter's number are {REPORTER_NUMBER}. "
                "Reply STOP at any time to opt-out of receiving messages from this conversation.",
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


def create_chatroom(send_sms, number=EVENT_NUMBER):
    # Send initial message to establish the chat.
    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    # Reset the mock for send_sms, because it's called
    # indirectly while creating the chatroom
    send_sms.reset_mock()


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_message_reply(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()
    create_chatroom(send_sms)

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
def test_organizer_in_two_events(send_sms, database):
    """Tests the case where an organizer is in two different events.

    This causes issues with a naive relay assignment algorithm that will try to
    assign a relay used in event one for event two, leading to a database error.
    The second event should get a unique relay number, and having an organizer in both
    effectively reduces the available number of relays.
    """
    event_one = create_event()
    event_two = create_event(name=EVENT_NAME_2, number=EVENT_NUMBER_2)
    create_organizers(event_one)
    create_organizers(event_two)
    create_relays()

    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "Hello")

    senders = set([call[2]["sender"] for call in send_sms.mock_calls])
    assert senders == set([EVENT_NUMBER, RELAY_NUMBER])

    # This should still work and should assign a different relay than the one above.
    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER_2, "Hello")

    senders = set([call[2]["sender"] for call in send_sms.mock_calls])
    assert senders == set([EVENT_NUMBER, EVENT_NUMBER_2, RELAY_NUMBER, RELAY_NUMBER_2])


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_stop_reply(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()
    create_chatroom(send_sms)

    # Verify a room currently exists for the reporter, and is deleted after the
    # reporter opts-out by texting stop.
    assert highlevel.find_smschat_by_user_and_relay_numbers(
        REPORTER_NUMBER, EVENT_NUMBER
    )
    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "STOP")
    assert not highlevel.find_smschat_by_user_and_relay_numbers(
        REPORTER_NUMBER, EVENT_NUMBER
    )

    # Three messages should have been sent. One for each of the two organizers,
    # notifying them that the reporter has left the chat, and one to the reporter,
    # to acknowledge that they opted out.
    assert send_sms.call_count == 3
    send_sms.assert_has_calls(
        [
            mock.call(
                sender=RELAY_NUMBER,
                to=BOB_ORGANIZER_NUMBER,
                message=f"{REPORTER_NAME}: This participant has chosen to leave the chat.",
            ),
            mock.call(
                sender=RELAY_NUMBER,
                to=ALICE_ORGANIZER_NUMBER,
                message=f"{REPORTER_NAME}: This participant has chosen to leave the chat.",
            ),
            mock.call(
                sender=EVENT_NUMBER,
                to=REPORTER_NUMBER,
                message="You've been successfully unsubscribed, you'll no longer receive messages from this number.",
            ),
        ]
    )

    # Reset the mock.
    send_sms.reset_mock()

    # Verify a room currently exists for this responder, and is deleted after the
    # responder opts-out by texting stop.
    assert highlevel.find_smschat_by_user_and_relay_numbers(
        BOB_ORGANIZER_NUMBER, RELAY_NUMBER
    )
    smschat.handle_message(BOB_ORGANIZER_NUMBER, RELAY_NUMBER, "Stop")
    assert not highlevel.find_smschat_by_user_and_relay_numbers(
        BOB_ORGANIZER_NUMBER, RELAY_NUMBER
    )

    # Two messages should have been sent. One to the remaining organizer,
    # notifying them that the Bob has left the chat, and one to Bob,
    # to acknowledge that they opted out.
    assert send_sms.call_count == 2
    send_sms.assert_has_calls(
        [
            mock.call(
                sender=RELAY_NUMBER,
                to=ALICE_ORGANIZER_NUMBER,
                message=f"{BOB_ORGANIZER_NAME}: This participant has chosen to leave the chat.",
            ),
            mock.call(
                sender=RELAY_NUMBER,
                to=BOB_ORGANIZER_NUMBER,
                message="You've been successfully unsubscribed, you'll no longer receive messages from this number.",
            ),
        ]
    )


@mock.patch("hotline.telephony.lowlevel.send_sms", autospec=True)
def test_handle_new_chat_after_stop_reply(send_sms, database):
    event = create_event()
    create_organizers(event)
    create_relays()
    create_chatroom(send_sms)

    # Verify a room currently exists for the reporter.
    initial_chat = highlevel.find_smschat_by_user_and_relay_numbers(
        REPORTER_NUMBER, EVENT_NUMBER
    )
    assert initial_chat

    # Verify the room no longer exists after reporter opts-out by texting stop.
    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "STOP")
    assert not highlevel.find_smschat_by_user_and_relay_numbers(
        REPORTER_NUMBER, EVENT_NUMBER
    )

    # Send a new message from the reporter to re-establish the chat.
    create_chatroom(send_sms)

    # Verify a new room is recreated for the reporter under a new relay number.
    new_chat = highlevel.find_smschat_by_user_and_relay_numbers(
        REPORTER_NUMBER, EVENT_NUMBER
    )
    assert new_chat
    assert new_chat.id != initial_chat.id
    assert new_chat.relay_number != initial_chat.relay_number

    # Opt-out again, verify the room no longer exists.
    smschat.handle_message(REPORTER_NUMBER, EVENT_NUMBER, "STOP")
    assert not highlevel.find_smschat_by_user_and_relay_numbers(
        REPORTER_NUMBER, EVENT_NUMBER
    )

    # Verify the new relay number was used for the messages.
    assert send_sms.call_count == 3
    send_sms.assert_has_calls(
        [
            mock.call(
                sender=new_chat.relay_number,
                to=BOB_ORGANIZER_NUMBER,
                message=f"{REPORTER_NAME}: This participant has chosen to leave the chat.",
            ),
            mock.call(
                sender=new_chat.relay_number,
                to=ALICE_ORGANIZER_NUMBER,
                message=f"{REPORTER_NAME}: This participant has chosen to leave the chat.",
            ),
            mock.call(
                sender=EVENT_NUMBER,
                to=REPORTER_NUMBER,
                message="You've been successfully unsubscribed, you'll no longer receive messages from this number.",
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
