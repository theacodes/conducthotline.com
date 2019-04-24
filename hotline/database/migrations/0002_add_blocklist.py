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

import peewee

from hotline.database import models


class CreateModels:
    method = "create_tables"
    args = [models.BlockList]

    def run(self):
        models.db.create_tables(self.args)


def migrate(migrator):
    return [
        migrator.add_column(
            "auditlog", "reporter_number", peewee.TextField(null=True, index=False)
        ),
        CreateModels(),
    ]
