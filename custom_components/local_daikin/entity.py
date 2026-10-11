from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity


def climate_updated_signal(entry_id: str) -> str:
    """Dispatcher signal sent by the climate entity after every poll."""
    return f"local_daikin_climate_updated_{entry_id}"


class DaikinClimateFollower(Entity):
    """Mixin for entities that mirror the climate entity's cached state.

    Instead of polling on their own timer (which added up to a full extra scan
    interval of lag), they refresh as soon as the climate entity has polled the
    unit. Subclasses read from the climate entity in `update()` (no HTTP) and
    must set `self._entry_id`. List this mixin before the HA entity class.
    """

    _attr_should_poll = False
    _entry_id: str

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, climate_updated_signal(self._entry_id), self._async_climate_updated
            )
        )
        self._refresh_from_climate()

    @callback
    def _async_climate_updated(self):
        self._refresh_from_climate()
        self.async_write_ha_state()

    def _refresh_from_climate(self):
        # update() only reads the climate entity's cache, so it is safe in the event loop.
        update = getattr(self, "update", None)
        if update is not None:
            update()
