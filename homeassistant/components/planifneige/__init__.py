"""Platform for the City of Montreal's Planif-Neige snow removal APIs."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

DOMAIN = 'planifneige'
DATA_PLANIFNEIGE = 'data_planifneige'

DATA_UPDATED = '{}_data_updated'.format(DOMAIN)

PLANIFNEIGE_ATTRIBUTION = "Information provided by the City of Montreal "

REQUIREMENTS = ['planif-neige-client==0.1.1']

_LOGGER = logging.getLogger(__name__)

CONF_STREET_ID = 'street_id'
CONF_STREETS = 'streets'

DEFAULT_INTERVAL = timedelta(minutes=5)

STREET_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_STREET_ID): cv.positive_int
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL,
                     default=DEFAULT_INTERVAL): vol.All(
                         cv.time_period, cv.positive_timedelta),
        vol.Required(CONF_STREETS): [STREET_SCHEMA]
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the PlanifNeige component."""
    from planif_neige_client import planif_neige_client
    db_path = hass.config.path('planifneige.db')
    conf = config[DOMAIN]

    pn_client = planif_neige_client.PlanifNeigeClient(conf.get(
        CONF_API_KEY), db_path)
    pn_client.get_planification_for_date()

    data = hass.data[DATA_PLANIFNEIGE] = PlanifNeigeData(
        hass, pn_client, conf.get(CONF_STREETS))

    async_track_time_interval(
        hass, data.update, conf[CONF_SCAN_INTERVAL]
        )

    def update(call=None):
        """Service call to manually update the data."""
        data.update()

    hass.services.async_register(DOMAIN, 'update', update)

    hass.async_create_task(
        async_load_platform(
            hass,
            SENSOR_DOMAIN,
            DOMAIN,
            conf[CONF_STREETS],
            config
        )
    )

    return True


class PlanifNeigeData:
    """Get the latest data from PlanifNeige."""

    def __init__(self, hass, pn, streets):
        """Initialize the data object."""
        self.data = []
        self._hass = hass
        self._streets = streets
        self._pn = pn

    def update(self, now=None):
        """Get the latest data from PlanifNeige."""
        self._pn.get_planification_for_date()

        for street in self._streets:
            self.data.append(
                self._pn.get_planification_for_street(street['street_id']))

        dispatcher_send(self._hass, DATA_UPDATED)
