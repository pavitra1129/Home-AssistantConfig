# -*- coding: utf-8 -*-

"""Support for LaMetric notifications."""

import logging
import voluptuous as vol

from enum import Enum
import requests
import json

from homeassistant.components.notify import ATTR_DATA, ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService

from . import DOMAIN as LAMETRIC_DOMAIN
from . import CONF_IP_ADDRESS
from . import CONF_PORT
from . import CONF_API_KEY
from . import CONF_CUSTOMIZE

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the LaMetric notification service."""

    if discovery_info is None:
        return None

    # _LOGGER.warning("%s", discovery_info)

    return LaMetricNotificationService(discovery_info)


########################################################################################################

def to_json(json_text):
  try:
    return json.loads(json_text)
  except ValueError as e:
    return None

class LaMetricNotificationService(BaseNotificationService):

    """Implement the notification service for LaMetric."""

    def __init__(self, config):

        # _LOGGER.warning("Lametric config: %s", config)

        self._default = config[CONF_CUSTOMIZE]
        self._device = LaMetricTime(config[CONF_IP_ADDRESS],
                                    port=config[CONF_PORT],
                                    api_key=config[CONF_API_KEY])

    def send_message(self, message='', **kwargs):
        """Send a message to some LaMetric device."""

        targets = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA)
        _LOGGER.debug('Targets/Data: %s/%s', targets, data)

        priority = 'info'

        icon = 'a7956'
        cycles = 1
        duration = None

        sound = 'notification'
        category = 'notifications'
        repeat = 1

        # defaults

        if self._default is not None:
            if 'priority' in self._default:
                priority = self._default['priority']

            if 'icon' in self._default:
                icon = self._default['icon']

            if 'sound' in self._default:
                sound = self._default['sound']

            if 'repeat' in self._default:
                repeat = self._default['repeat']

            if 'category' in self._default:
                category = self._default['category']

            if 'cycles' in self._default:
                cycles = self._default['cycles']

            if 'duration' in self._default:
                duration = self._default['duration']

        # Additional data as override?

        if data is not None:
            if 'priority' in data:
                priority = data['priority']

            if 'icon' in data:
                icon = data['icon']

            if 'duration' in data:
                duration = data['duration']

            if 'sound' in data:
                sound = data['sound']

            if 'repeat' in data:
                repeat = data['repeat']

            if 'category' in data:
                category = data['category']

            if 'cycles' in data:
                cycles = data['cycles']

        frames = [Frame(icon=icon, text=message, duration=duration)]
        if data is not None:
            if 'frames' in data:
                frames = to_json(data['frames'])

        if priority not in ['info', 'warning', 'critical']:
            priority = 'info'

        if category not in ['notifications', 'alarms']:
            category = 'notifications'

        notification = Notification(priority, cycles=cycles, frames=frames, sound=Sound(sound=sound, category=category, repeat=repeat))
        (status_code, error_text) = self._device.notification(notification)
        if status_code != 200:
            _LOGGER.warning('Warning: %s/%s', status_code, error_text)


########################################################################################################

class Sound(dict):

    """ Represents notification sound """
    def __init__(self, sound='notification', category='notifications', repeat=1):
        """
        Constructor
        :param sound: Sound id, full list can be found at
            http://lametric-documentation.readthedocs.io/en/latest/reference-docs/device-notifications.html
        :param repeat: Sound repeat count, if set to 0 sound will be played until notification is dismissed
        """

        dict.__init__({})
        if category is not None:
            self['category'] = category

        if sound is not None:
            self['id'] = sound

        if repeat is not None:
            self['repeat'] = repeat

        return


class Frame(dict):

    """ Represents single frame. Frame can display icon and text. """

    def __init__(self, icon, text, duration=None):
        """
        Constructor
        :param icon: icon id in form of "iXXX" for static icons, or "aXXXX" for animated ones.
        :param text: text message to be displayed
        """

        dict.__init__({})
        if icon is not None:
            self['icon'] = icon

        if duration is not None:
            self['duration'] = duration

        if type(text) == str:
            self['text'] = text
        else:
            self['chartData'] = text


class Notification(dict):

    """ Represents notification message """
    def __init__(self, priority, frames, sound, cycles=1):
        """
        Constructor
        :param priority: notification priority, Priority enum.
        :param frames: list of Frame objects
        :param sound: Sound object
        """

        dict.__init__({})
        self['priority'] = priority

        if priority == 'info':
            self['icon_type'] = 'info'

        if priority == 'critical':
            self['icon_type'] = 'alert'

        self['model'] = {'cycles': cycles, 'frames': frames,
                         'sound': sound}
        return


class LaMetricTime:

    """
    Allows to send notification to your LaMetric Time device in local network
    """
    def __init__(self, ip_address, port, api_key):
        """
        Constructor
        :param ip_address: IP address of the LaMetric Time
        :param port: 8080 for insecure connection or 4343 for secure one
        :param api_key: device API key
        """

        self.ip_address = ip_address
        self.port = port
        self._api_key = api_key
        return

    def notification(self, notification):
        """
        Sends notification to LaMetric Time
        :param notification: instance of Notification class
        :return: (status_code, body)
        """

        notifications_url = 'http://{0}:{1}/api/v2/device/notifications'.format(self.ip_address, self.port)
        r = requests.post(notifications_url, json=notification,
                          auth=('dev', self._api_key), verify=False)
        return (r.status_code, r.text)

    def push(self, push, app_id, app_key, channels):
        """
        Sends notification to LaMetric Time
        :param notification: instance of Notification class
        :return: (status_code, body)
        """

        headers = {'Accept': 'application/json',
                   'X-Access-Token': app_key,
                   'Cache-Control': 'no-cache'}

        # https://developer.lametric.com

        push_url = 'http://{0}:{1}/api/v1/dev/widget/update/com.lametric.{2}'.format(self.ip_address, self.port, app_id)
        if channels is not None:
            push_url = push_url + '?channels=' + channels

        # print(push_url);

        r = requests.post(push_url, json=push, auth=('dev',
                          self._api_key), headers=headers, verify=False)
        return (r.status_code, r.text)
