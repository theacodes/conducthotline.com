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


@pytest.mark.parametrize(
    ["country", "expected"],
    [(None, "11234567890"), ("US", "11234567890"), ("GB", "441234567890")],
)
def test_rent_number(country, expected):
    client = mock.create_autospec(nexmo.Client)
    client.application_id = "appid"

    client.get_available_numbers.return_value = {
        "numbers": [
            # Should always grab the first one.
            {"country": country, "msisdn": expected},
            {"country": "US", "msisdn": "19876543210"},
        ]
    }

    result = lowlevel.rent_number(
        sms_callback_url="example.com/sms", country_code=country, client=client
    )

    assert result == {"country": country, "msisdn": f"+{expected}"}

    client.get_available_numbers.assert_called_once_with(country, mock.ANY)
    client.buy_number.assert_called_once_with({"country": country, "msisdn": expected})


def test_rent_number_none_available():
    client = mock.create_autospec(nexmo.Client)
    client.application_id = "appid"

    client.get_available_numbers.return_value = {"numbers": []}

    with pytest.raises(RuntimeError, match="No numbers available"):
        lowlevel.rent_number(sms_callback_url="example.com/sms", client=client)


def test_rent_number_buy_error_is_okay():
    client = mock.create_autospec(nexmo.Client)
    client.application_id = "appid"

    client.get_available_numbers.return_value = {
        "numbers": [
            {"country": "US", "msisdn": "+1123456789"},
            {"country": "US", "msisdn": "+1987654321"},
        ]
    }

    # Return an error when trying to buy the first number, so that the method
    # ends up buying the second number.
    client.buy_number.side_effect = [nexmo.Error(), None]

    result = lowlevel.rent_number(sms_callback_url="example.com/sms", client=client)

    assert result == {"country": "US", "msisdn": "+1987654321"}
    assert client.buy_number.call_count == 2


@mock.patch("time.sleep", autospec=True)
def test_send_sms(sleep):
    client = mock.create_autospec(nexmo.Client)
    client.application_id = "appid"

    client.send_message.return_value = {"messages": [{}]}

    lowlevel.send_sms(to="1234", sender="5678", message="meep", client=client)

    client.send_message.assert_called_once_with(
        {"from": "5678", "to": "1234", "text": "meep"}
    )
