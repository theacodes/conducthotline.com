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

"""Recreates database tables / does migrations."""

from hotline.database import lowlevel

models = [
    lowlevel.Number,
    lowlevel.Event,
    lowlevel.EventMember,
    lowlevel.Chatroom,
    lowlevel.ChatroomConnection,
]


def create_tables():
    with lowlevel.db:
        lowlevel.db.drop_tables(models)
        lowlevel.db.create_tables(models)


if __name__ == "__main__":
    create_tables()
