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

import hotline.config
from hotline.database import models as db

models = [
    db.Number,
    db.Event,
    db.EventMember,
    db.EventOrganizer,
    db.SmsChat,
    db.SmsChatConnection,
    db.AuditLog,
]


def create_tables():
    with db.db:
        db.db.drop_tables(models)
        db.db.create_tables(models)


if __name__ == "__main__":
    hotline.config.load()
    create_tables()
