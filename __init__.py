import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import async_timeout
import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'my_url_monitor'

CONFIG_SCHEMA = {
    DOMAIN: {
        vol.Required(CONF_NAME): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_URL): vol.All(cv.ensure_list, [cv.url]),
    }
}

async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the URL monitoring component."""
    hass.data[DOMAIN] = URLMonitorData(
        hass, config[DOMAIN][CONF_NAME], config[DOMAIN][CONF_URL]
    )
    hass.async_create_task(hass.data[DOMAIN].async_update())
    return True

class URLMonitor(SensorEntity):
    """Representation of a URL monitor sensor."""

    def __init__(self, data: 'URLMonitorData', index: int) -> None:
        """Initialize the URL monitor sensor."""
        self._data = data
        self._index = index

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"URL Monitor {self._index + 1}"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._data.states[self._index]

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:link" if self._data.states[self._index] == "Online" else "mdi:link-off"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the sensor."""
        return {
            "URL": self._data.urls[self._index],
            "Status": self._data.status[self._index],
            "Last Updated": self._data.last_updated[self._index].isoformat(),
        }

class URLMonitorData:
    """Data for the URL monitoring component."""

    def __init__(self, hass: HomeAssistant, names: List[str], urls: List[str]) -> None:
        """Initialize the URL monitoring data."""
        self.hass = hass
        self.names = names
        self.urls = urls
        self.states = ["Unknown"] * len(urls)
        self.status = [""] * len(urls)
        self.last_updated = [datetime.min] * len(urls)

    async def async_update(self) -> None:
        """Update the URL monitoring data."""
        async with async_timeout.timeout(10):
            await self._check_urls()
        async_track_time_interval(self.hass, self.async_update, timedelta(hours=1))

    async def _check_urls(self) -> None:
        """Check the URLs and update the sensor states."""
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(self.urls):
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            self.states[i] = "Online"
                            self.status[i] = "OK"
                        else:
                            self.states[i] = "Offline"
                            self.status[i] = f"HTTP {response.status}"
                    self.last_updated[i] = datetime.now()
                except aiohttp.ClientError as e:
                    self.states[i] = "Offline"
                    self.status[i] = str(e)
                    self.last_updated[i] = datetime.now()
                except asyncio.TimeoutError:
                    self.states[i] = "Offline"
                    self.status[i] = "Timeout"
                    self.last_updated[i] = datetime.now()

    @property
    def sensors(self) -> List[URLMonitor]:
        """Return the list of URL monitor sensors."""
        return [URLMonitor(self, i) for i in range(len(self.urls))]