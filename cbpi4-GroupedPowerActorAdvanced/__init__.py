
# -*- coding: utf-8 -*-
#import os
#from aiohttp import web
import logging
#from unittest.mock import MagicMock, patch
import asyncio
import numpy as np
from cbpi.api import *
from cbpi.api.base import CBPiBase

logger = logging.getLogger("cbpi4-GroupedPowerActor")

@parameters([
    Property.Actor(label="Actor 1", required=False),
    Property.Actor(label="Actor 2", required=False),
    Property.Actor(label="Actor 3", required=False),
    Property.Actor(label="Actor 4", required=False),
    Property.Actor(label="Actor 5", required=False),
    Property.Actor(label="Actor 6", required=False),
    Property.Actor(label="Actor 7", required=False),
    Property.Actor(label="Actor 8", required=False),
    Property.Number(label="Check interval (s)", configurable=True, default_value=5,
                    description="Every X seconds check that grouped actors are really ON/OFF"),
    Property.Select(label="Auto-correct mismatch", options=["Yes", "No"], configurable=True, default_value="No",
                    description="If a grouped actor is not in the correct state, automatically correct it")
])
class GroupedPowerActor(ActorBase):

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        # collect the actor ids from the 8 possible slots
        self.group = [props.get(f"Actor {i}") for i in range(1, 9)]
        # filter out None
        self.group = [a for a in self.group if a]
        self.check_interval = int(props.get("Check interval (s)", 5))
        self.auto_correct = (props.get("Auto-correct mismatch") == "Yes")

        self.power = 0  # overall group power (0–100)
        self._monitor_task = None
        self._running = True

        logger.info(f"[GroupedPowerActor] Initialized group: {self.group}, check_interval={self.check_interval}, auto_correct={self.auto_correct}")

    async def on_start(self):
        logger.info("[GroupedPowerActor] on_start — launching state monitor")
        self._monitor_task = asyncio.create_task(self._state_monitor())

    async def on_shutdown(self):
        logger.info("[GroupedPowerActor] on_shutdown — canceling monitor")
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()

    async def _state_monitor(self):
        await asyncio.sleep(2)  # initial delay to let system stabilize
        logger.info(f"[GroupedPowerActor] State monitor started (interval {self.check_interval}s)")
        while self._running:
            try:
                await self._check_group_state()
            except Exception as e:
                logger.exception(f"[GroupedPowerActor] Error in state monitor: {e}")
            await asyncio.sleep(self.check_interval)

    async def _check_group_state(self):
        desired_on = (self.power > 0)
        for aid in self.group:
            actor = self.cbpi.actor.actor_list.get(aid)
            if actor is None:
                logger.warning(f"[GroupedPowerActor] Actor '{aid}' not found in CBPi")
                continue
            # actor.get_state() may return dict, but actor.power often holds the last power value
            # We'll treat any non-zero actor.power as ON
            actual_on = bool(getattr(actor, "power", 0))
            if actual_on != desired_on:
                logger.warning(f"[GroupedPowerActor] MISMATCH: '{aid}' is {'ON' if actual_on else 'OFF'}, but should be {'ON' if desired_on else 'OFF'}")
                if self.auto_correct:
                    logger.info(f"[GroupedPowerActor] Auto-correcting '{aid}' → {'ON' if desired_on else 'OFF'}")
                    if desired_on:
                        await actor.on(power=100)
                    else:
                        await actor.off()

    @ActorAction(name="Set Power", parameters=[Property.Number(label="Power", description="0–100")])
    async def set_power(self, Power=100, **kwargs):
        # Called when user sets group power
        p = int(max(0, min(100, Power)))
        self.power = p
        logger.info(f"[GroupedPowerActor] set_power → {self.power}%")
        # calculate distribution among sub-actors (same logic as original)
        # distribute full 100% to first, then remainder, etc.
        remaining = p
        per = 100 / len(self.group) if self.group else 0
        for aid in self.group:
            actor = self.cbpi.actor.actor_list.get(aid)
            if not actor:
                continue
            # Decide sub-power: simplistic: if remaining >= per, set 100, else set proportional
            sub = 100 if remaining >= (100 / len(self.group)) else int(round((remaining / p) * 100)) if p > 0 else 0
            remaining -= per
            await actor.on(power=sub if sub > 0 else 0)
        # Update own UI state
        await self.cbpi.actor.actor_update(self.id, self.power)

    @ActorAction(name="On")
    async def on(self, **kwargs):
        self.power = 100
        logger.info("[GroupedPowerActor] ON → all actors ON")
        for aid in self.group:
            actor = self.cbpi.actor.actor_list.get(aid)
            if actor:
                await actor.on(power=100)
        await self.cbpi.actor.actor_update(self.id, self.power)

    @ActorAction(name="Off")
    async def off(self, **kwargs):
        self.power = 0
        logger.info("[GroupedPowerActor] OFF → all actors OFF")
        for aid in self.group:
            actor = self.cbpi.actor.actor_list.get(aid)
            if actor:
                await actor.off()
        await self.cbpi.actor.actor_update(self.id, self.power)

    async def get_state(self):
        return dict(power=self.power)

def setup(cbpi):
    cbpi.plugin.register("GroupedPowerActor", GroupedPowerActor)
    logger.info("GroupedPowerActor (with state-check) loaded")
