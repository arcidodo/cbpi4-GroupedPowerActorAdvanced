# -*- coding: utf-8 -*-
import asyncio
import logging
from cbpi.api.base import CBPiActor
from cbpi.api import Property, cbpi

_LOGGER = logging.getLogger(__name__)

class GroupedPowerActor(CBPiActor):
    """
    CBPi4 Actor om meerdere schakelaars tegelijk te bedienen
    met periodieke controle of ze echt aan/uit staan.
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task = None

    async def start(self):
        """
        Start periodic control loop
        """
        _LOGGER.info("GroupedPowerActor gestart")
        self._task = asyncio.create_task(self._periodic_check())

    async def stop(self):
        """
        Stop periodic control loop
        """
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        _LOGGER.info("GroupedPowerActor gestopt")

    async def _periodic_check(self):
        """
        Controleer periodiek de status van alle geselecteerde switches
        """
        while True:
            try:
                for switch_prop in [
                    self.switch1, self.switch2, self.switch3, self.switch4,
                    self.switch5, self.switch6, self.switch7, self.switch8
                ]:
                    if switch_prop:
                        actual_state = await cbpi.get_actor_state(switch_prop.id)
                        desired_state = self.get_desired_state(switch_prop)
                        if actual_state != desired_state:
                            _LOGGER.warning(
                                f"Switch '{switch_prop.name}' status mismatch: "
                                f"gewenst={desired_state}, huidig={actual_state}. Correctie uitvoeren."
                            )
                            await cbpi.set_actor_state(switch_prop.id, desired_state)
            except Exception as e:
                _LOGGER.error(f"Fout bij periodic check: {e}")
            await asyncio.sleep(self.interval)

    def get_desired_state(self, switch_prop):
        """
        Bepaal gewenste status van een switch.
        Hier kan je logica aanpassen als nodig.
        Voor nu: als actor 'on' is volgens CBPi, willen we aanzetten.
        """
        return 1 if self.is_actor_on(switch_prop) else 0

    def is_actor_on(self, switch_prop):
        """
        Huidige gewenste status bepalen (je kan hier eigen logica toevoegen)
        """
        # Default: alles uit, kan je aanpassen
        return False

    async def on(self, actor):
        """
        Zet alle geselecteerde schakelaars aan
        """
        for switch_prop in [
            self.switch1, self.switch2, self.switch3, self.switch4,
            self.switch5, self.switch6, self.switch7, self.switch8
        ]:
            if switch_prop:
                await cbpi.set_actor_state(switch_prop.id, 1)

    async def off(self, actor):
        """
        Zet alle geselecteerde schakelaars uit
        """
        for switch_prop in [
            self.switch1, self.switch2, self.switch3, self.switch4,
            self.switch5, self.switch6, self.switch7, self.switch8
        ]:
            if switch_prop:
                await cbpi.set_actor_state(switch_prop.id, 0)
