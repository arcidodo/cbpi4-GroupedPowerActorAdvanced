# cbpi4-GroupedPowerActor/__init__.py
# -*- coding: utf-8 -*-
import asyncio
import logging

from cbpi.api import *
from cbpi.api.base import ActorBase
from cbpi.api.actor import ActorAction

logger = logging.getLogger("cbpi4-GroupedPowerActor")


@parameters([
    Property.Actor(label="Actor 1"),
    Property.Actor(label="Actor 2"),
    Property.Actor(label="Actor 3"),
    Property.Actor(label="Actor 4"),
    Property.Actor(label="Actor 5"),
    Property.Actor(label="Actor 6"),
    Property.Actor(label="Actor 7"),
    Property.Actor(label="Actor 8"),
    Property.Number(label="Check interval (s)", configurable=True, default_value=5,
                    description="Every X seconds check that grouped actors are really ON/OFF"),
    Property.Select(label="Auto-correct mismatch", options=["Yes", "No"], configurable=True, default_value="No",
                    description="If a grouped actor is not in the correct state, automatically correct it")
])
class GroupedPowerActor(ActorBase):
    """
    GroupedPowerActor
    - Controls up to 8 child actors as a single grouped actor
    - Periodically checks whether child actors are actually in the desired state
    - Optionally auto-corrects mismatches
    """

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)

        # Gather configured actor ids (some may be None/empty)
        self.group = []
        for i in range(1, 9):
            key = f"Actor {i}"
            val = props.get(key)
            if val:
                # Some CBPi installations store actor id as integer, some as string
                # Keep as-is; later we use it to lookup in cbpi.actor.actor_list
                self.group.append(val)

        # Configurable behaviour
        try:
            self.check_interval = int(props.get("Check interval (s)", 5))
        except Exception:
            self.check_interval = 5
        self.auto_correct = (props.get("Auto-correct mismatch", "No") == "Yes")

        # Runtime state
        self.power = 0  # 0-100 group power
        self._monitor_task = None
        self._running = True

        logger.info(f"[GroupedPowerActor] init: group={self.group}, check_interval={self.check_interval}, auto_correct={self.auto_correct}")

    async def on_start(self):
        """Start the background monitor task when actor starts."""
        logger.info("[GroupedPowerActor] on_start: starting monitor task")
        # Start the monitor as background task
        self._monitor_task = asyncio.create_task(self._state_monitor())

    async def on_shutdown(self):
        """Cleanup on shutdown: cancel monitor task."""
        logger.info("[GroupedPowerActor] on_shutdown: cancelling monitor task")
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"[GroupedPowerActor] on_shutdown: monitor cancel error: {e}")

    async def _state_monitor(self):
        """Background loop that periodically checks the real state of child actors."""
        # short initial delay to let system finish startup
        await asyncio.sleep(2)
        logger.info(f"[GroupedPowerActor] State monitor started (interval {self.check_interval}s)")

        while self._running:
            try:
                # Only run checks while CBPi marked actor controllers running
                # but we still allow checks even if this grouped actor hasn't been explicitly turned on by CBPi UI
                await self._check_group_state()
            except asyncio.CancelledError:
                logger.debug("[GroupedPowerActor] State monitor cancelled")
                break
            except Exception as e:
                logger.exception(f"[GroupedPowerActor] Exception in state monitor: {e}")

            # sleep interval
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

    async def _check_group_state(self):
        """Check each child actor actual 'power' and compare to desired state."""
        # determine desired boolean (True if group power > 0)
        desired_on = (self.power > 0)

        for aid in self.group:
            try:
                # actor lookup: cbpi.actor.actor_list is a dict-like in this CBPi version
                actor = None
                try:
                    actor = self.cbpi.actor.actor_list.get(aid)
                except Exception:
                    # fallback: maybe actor ids are ints or stored differently
                    # try scanning actor_list keys for something matching string form
                    for k, v in self.cbpi.actor.actor_list.items():
                        if str(k) == str(aid) or getattr(v, "name", "") == str(aid):
                            actor = v
                            break

                if actor is None:
                    logger.warning(f"[GroupedPowerActor] Child actor '{aid}' not found")
                    continue

                # Many actors store last power in attribute 'power'; fallback to get_state()
                actual_on = False
                # prefer actor.power when present and numeric
                if hasattr(actor, "power"):
                    try:
                        actual_on = bool(int(round(float(actor.power or 0))))
                    except Exception:
                        actual_on = bool(actor.power)
                else:
                    # try actor.get_state() if available and returns boolean or dict
                    try:
                        st = actor.get_state()
                        if isinstance(st, dict):
                            # common format: {'power': N} or {'power': N, ...}
                            if "power" in st:
                                actual_on = bool(int(round(float(st.get("power") or 0))))
                            else:
                                # fallback: any truthy dict means on
                                actual_on = True if st else False
                        else:
                            actual_on = bool(st)
                    except Exception:
                        # last fallback: consider it off
                        actual_on = False

                if actual_on != desired_on:
                    logger.warning(f"[GroupedPowerActor] MISMATCH for '{aid}': actual={'ON' if actual_on else 'OFF'} but desired={'ON' if desired_on else 'OFF'}")
                    if self.auto_correct:
                        logger.info(f"[GroupedPowerActor] Auto-correcting '{aid}' -> {'ON' if desired_on else 'OFF'}")
                        try:
                            if desired_on:
                                # set full power for child
                                await actor.on(power=100)
                            else:
                                await actor.off()
                        except Exception as e:
                            logger.exception(f"[GroupedPowerActor] Failed to autocorrect '{aid}': {e}")

            except Exception as e:
                logger.exception(f"[GroupedPowerActor] Error checking child actor '{aid}': {e}")

    @ActorAction(name="Set Power", parameters=[Property.Number(label="Power", description="0–100")])
    async def set_power(self, Power=100, **kwargs):
        """
        Set group power. We will set each child actor to the same Power value.
        (Simpler and deterministic behaviour for grouped actors.)
        """
        try:
            p = int(round(float(Power)))
        except Exception:
            p = 0
        p = max(0, min(100, p))
        self.power = p

        logger.info(f"[GroupedPowerActor] set_power -> {self.power}% (applying to {len(self.group)} children)")

        # Apply the power to all child actors (set same power)
        for aid in self.group:
            try:
                actor = self.cbpi.actor.actor_list.get(aid)
                if actor is None:
                    # try fallback lookup like above
                    for k, v in self.cbpi.actor.actor_list.items():
                        if str(k) == str(aid) or getattr(v, "name", "") == str(aid):
                            actor = v
                            break
                if actor:
                    # if power > 0 call on(power), else off()
                    if p > 0:
                        await actor.on(power=p)
                    else:
                        await actor.off()
            except Exception as e:
                logger.exception(f"[GroupedPowerActor] Error setting child actor '{aid}' power: {e}")

        # Update CBPi UI for this grouped actor
        try:
            await self.cbpi.actor.actor_update(self.id, self.power)
        except Exception:
            pass

    @ActorAction(name="On")
    async def on(self, **kwargs):
        """Turn group fully on (100%)."""
        self.power = 100
        logger.info("[GroupedPowerActor] ON -> turning all children ON (100%)")
        for aid in self.group:
            try:
                actor = self.cbpi.actor.actor_list.get(aid)
                if actor:
                    await actor.on(power=100)
            except Exception as e:
                logger.exception(f"[GroupedPowerActor] Error turning on child '{aid}': {e}")
        try:
            await self.cbpi.actor.actor_update(self.id, self.power)
        except Exception:
            pass

    @ActorAction(name="Off")
    async def off(self, **kwargs):
        """Turn group off (0%)."""
        self.power = 0
        logger.info("[GroupedPowerActor] OFF -> turning all children OFF")
        for aid in self.group:
            try:
                actor = self.cbpi.actor.actor_list.get(aid)
                if actor:
                    await actor.off()
            except Exception as e:
                logger.exception(f"[GroupedPowerActor] Error turning off child '{aid}': {e}")
        try:
            await self.cbpi.actor.actor_update(self.id, self.power)
        except Exception:
            pass

    def get_state(self):
        """Return state for CBPi UI"""
        return dict(power=self.power)


def setup(cbpi):
    cbpi.plugin.register("GroupedPowerActor", GroupedPowerActor)
    logger.info("GroupedPowerActor (with state-check) loaded")
