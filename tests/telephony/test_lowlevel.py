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

from hotline.telephony import lowlevel


def test_rent_number():
    client = mock.create_autospec(nexmo.Client)

    client.get_available_numbers.return_value = {"numbers": [
        {"country": "US", "msisdn": "123456789"},
        {"country": "US", "msisdn": "987654321"},
    ]}

    result = lowlevel.rent_number(client=client)

    assert result == {"country": "US", "msisdn": "123456789"}

    client.get_available_numbers.assert_called_once()
    client.buy_number.assert_called_once_with(result)


def test_rent_number_none_available():
    client = mock.create_autospec(nexmo.Client)

    client.get_available_numbers.return_value = {"numbers": [
    ]}

    with pytest.raises(RuntimeError, match="No numbers available"):
        lowlevel.rent_number(client=client)


def test_rent_number_buy_error_is_okay():
    client = mock.create_autospec(nexmo.Client)

    client.get_available_numbers.return_value = {"numbers": [
        {"country": "US", "msisdn": "123456789"},
        {"country": "US", "msisdn": "987654321"},
    ]}

    # Return an error when trying to buy the first number, so that the method
    # ends up buying the second number.
    client.buy_number.side_effect = [
        nexmo.Error(),
        None
    ]

    result = lowlevel.rent_number(client=client)

    assert result == {"country": "US", "msisdn": "987654321"}
    assert client.buy_number.call_count == 2


def test_send_sms():
    client = mock.create_autospec(nexmo.Client)

    client.send_message.return_value = {"messages": [{}]}

    lowlevel.send_sms(to="1234", sender="5678", message="meep", client=client)

    client.send_message.assert_called_once_with({
        "from": "5678",
        "to": "1234",
        "text": "meep"
    })
