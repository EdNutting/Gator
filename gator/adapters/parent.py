# Copyright 2023, Peter Birch, mailto:peter@lightlogic.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import atexit
import json
import logging
import os
import sys
from queue import SimpleQueue
from threading import Event, Thread

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect


class TeardownMarker:
    pass


class Parent:
    """
    Thread based wrapper around the Gator websocket interface

    :param ws_address: Optional websocket address for the parent tier, otherwise
                       it will be read from the GATOR_PARENT environment variable
    """

    def __init__(self, ws_address: str | None = None):
        self._ws_address = ws_address or Parent.get_parent_address()
        if not self._ws_address:
            raise ValueError(
                "WebSocket address for parent process is not set and could not be "
                "determined from the environment. Please provide ws_address parameter "
                "or set GATOR_PARENT environment variable."
            )
        self._rx_q = SimpleQueue[dict[str, str]]
        self._tx_q = SimpleQueue[TeardownMarker | dict[str, str]]()
        self._teardown_started = Event()    # Signals teardown initiated
        self._teardown_completed = Event()  # Signals teardown complete (was _teardown_evt)
        self._ws_thread = Thread(target=self._manage_ws, daemon=True)
        self._ws_thread.start()
        atexit.register(self._teardown_at_exit)

    @staticmethod
    def get_parent_address() -> str | None:
        return os.environ.get("GATOR_PARENT", None)

    def post(self, action, **payload):
        self._tx_q.put(
            {
                "action": action,
                "posted": True,
                "payload": payload,
            }
        )

    def receive(self) -> dict[str, str]:
        return self._rx_q.get()

    def _manage_ws(self):
        idx = 0
        logger = logging.getLogger("gator_ws")

        def _receiver(
            ws, rx_q: SimpleQueue[dict[str, str]], logger: logging.Logger, teardown_started: Event
        ):
            try:
                for packet in ws:
                    rx_q.put(json.loads(packet))
            except ConnectionClosed as e:
                if not teardown_started.is_set():
                    # UNEXPECTED: Connection closed before teardown was initiated
                    logger.error(
                        f"WebSocket connection closed unexpectedly in receiver: "
                        f"code={e.rcvd.code if e.rcvd else 'unknown'}, "
                        f"reason={e.rcvd.reason if e.rcvd else 'unknown'}"
                    )
                    # Signal connection loss by putting a sentinel value
                    rx_q.put({"action": "_connection_closed", "posted": True, "payload": {}})
                else:
                    # EXPECTED: Connection closed during normal shutdown
                    logger.debug("Receiver: WebSocket closed during graceful shutdown")

        rx_thread = None
        try:
            with connect(
                f"ws://{self._ws_address}",
                logger=logger,
            ) as ws:
                # Disable log propagation to avoid recursive forwarding
                logger.propagate = False
                # Setup a receiving thread
                rx_thread = Thread(
                    target=_receiver,
                    daemon=True,
                    args=(ws, self._rx_q, logger, self._teardown_started),
                )
                rx_thread.start()
                # Transmit until a teardown is inserted
                while True:
                    packet = self._tx_q.get()
                    # Check if the process wants us to teardown
                    if isinstance(packet, TeardownMarker):
                        break
                    # Otherwise send the message
                    ws.send(json.dumps(packet))
                    idx += 1
        except ConnectionClosed as e:
            if not self._teardown_started.is_set():
                # UNEXPECTED: Connection died during normal operation
                logger.error(
                    f"WebSocket connection closed unexpectedly in management thread: "
                    f"code={e.rcvd.code if e.rcvd else 'unknown'}, "
                    f"reason={e.rcvd.reason if e.rcvd else 'unknown'}"
                )
            else:
                # EXPECTED: Connection closed while exiting context manager during teardown
                logger.debug("Management thread: WebSocket closed during graceful shutdown")
        # Wait for the receiver thread to end with timeout
        if rx_thread:
            rx_thread.join(timeout=5)
            if rx_thread.is_alive():
                logger.error(
                    "Receiver thread failed to terminate within 5 seconds after connection closure"
                )
        # Set the teardown event to signify a clean exit
        self._teardown_completed.set()  # Renamed from _teardown_evt

    def _teardown_at_exit(self):
        self._teardown()

    def _teardown(self):
        self._teardown_started.set()  # Signal that teardown has started
        self._tx_q.put(TeardownMarker())
        if not self._teardown_completed.wait(timeout=10):  # Renamed from _teardown_evt
            print(
                "Gator timed out waiting for the websocket thread to teardown, "
                "some packets may have been missed!",
                file=sys.stderr,
            )
