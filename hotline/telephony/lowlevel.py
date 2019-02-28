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

"""Handles low-level telephony-related actions, such as renting numbers and
sending messages."""

import nexmo

from hotline import injector


@injector.provides(
    "nexmo.client", needs=["secrets.nexmo.api_key", "secrets.nexmo.api_secret"]
)
def _make_client(api_key, api_secret):
    return nexmo.Client(key=api_key, secret=api_secret)


@injector.needs("nexmo.client")
def rent_number(client: nexmo.Client, country_code: str = "US") -> dict:
    """Rents a number for the given country.

    NOTE: This immediately charges us for the number (for at least a month).
    """
    numbers = client.get_available_numbers(
        country_code, {"features": "SMS,VOICE", "type": "mobile-lvn"}
    )

    error = RuntimeError("No numbers available.")

    for number in numbers["numbers"]:
        try:
            client.buy_number(
                {"country": number["country"], "msisdn": number["msisdn"]}
            )
            return number
        except nexmo.Error as error:
            continue

    raise error


@injector.needs("nexmo.client")
def send_sms(sender: str, to: str, message: str, client: nexmo.Client) -> dict:
    """Sends an SMS.

    ``sender`` and ``to`` must be in proper long form.
    """
    resp = client.send_message({"from": sender, "to": to, "text": message})

    # Nexmo client incorrectly treats failed messages as successful
    error_text = resp["messages"][0].get("error-text")

    if error_text:
        raise nexmo.ClientError(error_text)

    import time

    # TODO: Something... better.
    time.sleep(2)

    return resp
