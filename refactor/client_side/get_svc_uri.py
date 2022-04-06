# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

from furl import furl

from refactor.queuer.app.core.config import settings as queuer_settings
from refactor.results.app.core.config import settings as results_settings


class ServiceURI:
    def __init__(
        self,
        scheme: str = "http",
        host: str = "localhost",
        port: int = None,
        prefix: str = "api/v0",
    ) -> None:
        self.scheme = scheme
        self.host = host
        self.port = port
        self.prefix = prefix

    def get_base_url(self):
        base_url = furl().set(scheme=self.scheme, host=self.host, port=self.port)
        if self.prefix:
            base_url.set(path=self.prefix)
        return base_url

    def get_route(self, path: str):
        base_url = self.get_base_url().copy()
        base_url.path /= path
        return base_url.url


class QueuerURI(ServiceURI):
    def __init__(self) -> None:
        super().__init__(port=queuer_settings.QUEUER_SVC_PORT, host=queuer_settings.QUEUER_SVC_HOST)


class ResultsURI(ServiceURI):
    def __init__(self) -> None:
        super().__init__(port=results_settings.RESULTS_SVC_PORT, host=results_settings.RESULTS_SVC_HOST)