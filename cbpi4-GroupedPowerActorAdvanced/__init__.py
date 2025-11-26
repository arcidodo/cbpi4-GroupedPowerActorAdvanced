import logging
#from unittest.mock import MagicMock, patch
import asyncio
import numpy as np
from cbpi.api import *
from cbpi.api.base import CBPiBase

_LOGGER = logging.getLogger("cbpi4-GroupedPowerActor")

class GroupedPowerActor(Actor):
    """
    Grouped actor: bedient meerdere schakelaars tegelijk én
    controleert periodiek of ze werkelijk in de gewenste staat zijn.
    """

    switch1 = Property.Actor("Switch 1")
    switch2 = Property.Actor("Switch 2")
    switch3 = Property.Actor("Switch 3")
    switch4 = Property.Actor("Switch 4")
    switch5 = Property.Actor("Switch 5")
    switch6 = Property.Actor("Switch 6")
    switch7 = Property.Actor("Switch 7")
    switch8 = Property.Actor("Switch 8")

    interval = Property.Number("Check interval (s)", configurable=True, default_value=10)

    def init(self):
        self._task = None
        _LOGGER.info("[GroupedPowerActor] init")

    async def start(self):
        _LOGGER.info("[GroupedPowerActor] start")
        self._task = asyncio.create_task(self._periodic_check())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        _LOGGER.info("[GroupedPowerActor] stop")

    async def _periodic_check(self):
        while True:
            try:
                for prop in (self.switch1, self.switch2, self.switch3, self.switch4,
                             self.switch5, self.switch6, self.switch7, self.switch8):
                    if prop:
                        actor_id = prop.id
                        # Haal huidige actor status
                        actual = await cbpi.get_actor_state(actor_id)
                        desired = await self._get_desired(actor_id)
                        if actual != desired:
                            _LOGGER.warning(
                                f"[GroupedPowerActor] MISMATCH actor {actor_id}: actual={actual}, desired={desired}. Correcting."
                            )
                            await cbpi.set_actor_state(actor_id, desired)
            except Exception as e:
                _LOGGER.error(f"[GroupedPowerActor] periodic check error: {e}")
            await asyncio.sleep(self.interval)

    async def _get_desired(self, actor_id):
        # Afhankelijk hoe jij hebt ingesteld: bijvoorbeeld:
        # als grouped actor aan is → alle kinderen aan, anders uit
        # Hier gewoon: grouped actor staat aan als power > 0
        if int(self.power or 0) > 0:
            return 1
        else:
            return 0

    @cbpi.action("On")
    async def on(self, **kwargs):
        self.power = 100
        for prop in (self.switch1, self.switch2, self.switch3, self.switch4,
                     self.switch5, self.switch6, self.switch7, self.switch8):
            if prop:
                await cbpi.set_actor_state(prop.id, 1)

    @cbpi.action("Off")
    async def off(self, **kwargs):
        self.power = 0
        for prop in (self.switch1, self.switch2, self.switch3, self.switch4,
                     self.switch5, self.switch6, self.switch7, self.switch8):
            if prop:
                await cbpi.set_actor_state(prop.id, 0)
