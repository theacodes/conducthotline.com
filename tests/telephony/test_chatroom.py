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

from hotline.telephony import chatroom


def test_add_user_unique_constraint():
    room = chatroom.Chatroom()

    room.add_user(name="A", user_number="1234", relay_number="1")
    room.add_user(name="B", user_number="5678", relay_number="2")
    room.add_user(name="C", user_number="1234", relay_number="3")

    assert len(room.users) == 2


@mock.patch("hotline.telephony.lowlevel.send_sms")
def test_relay(send_sms):
    room = chatroom.Chatroom()

    room.add_user(name="A", user_number="1234", relay_number="1")
    room.add_user(name="B", user_number="5678", relay_number="2")
    room.add_user(name="C", user_number="1111", relay_number="3")

    # A message from User A.
    room.relay("1234", "meep")

    send_sms.assert_has_calls(
        [
            mock.call(to="5678", sender="2", message="A: meep"),
            mock.call(to="1111", sender="3", message="A: meep"),
        ]
    )

    # A message from User B.
    send_sms.reset()
    room.relay("5678", "moop")

    send_sms.assert_has_calls(
        [
            mock.call(to="1234", sender="1", message="B: moop"),
            mock.call(to="1111", sender="3", message="B: moop"),
        ]
    )


def test_serialize_deserialize():
    room = chatroom.Chatroom()

    room.add_user(name="A", user_number="1234", relay_number="1")
    room.add_user(name="B", user_number="5678", relay_number="2")
    room.add_user(name="C", user_number="1111", relay_number="3")

    roundtripped = room.deserialize(room.serialize())

    assert list(roundtripped.users) == list(room.users)
