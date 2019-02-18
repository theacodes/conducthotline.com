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

"""Configures dependency injection across the application."""

from typing import List


def flatten_dict(source: dict, ancestors: List[str] = None) -> dict:
    """Flattens a nested dictionary.

    This::

        {
            "nexmo": {
                "api_key": "example",
                "api_secret": "sssh",
            }
        }

    Becomes::

        {
            "nexmo.api_key": "example",
            "nexmo.api_secret": "sssh"
        }
    """

    if ancestors is None:
        ancestors = []

    destination = {}
    for key, value in source.items():
        key_parts = ancestors + [key]
        stem = ".".join(key_parts)
        if isinstance(value, dict):
            destination.update(flatten_dict(value, ancestors=key_parts))
        else:
            destination[stem] = value

    return destination
