# -*- coding: utf-8 -*-
"""
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram/
"""
import logging
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_MESSAGE, ATTR_TITLE, ATTR_DATA, ATTR_TARGET,
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import ATTR_LOCATION

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mytelegram_bot'
DEPENDENCIES = [DOMAIN]

ATTR_KEYBOARD = 'keyboard'
ATTR_INLINE_KEYBOARD = 'inline_keyboard'
ATTR_PHOTO = 'photo'
ATTR_DOCUMENT = 'document'

CONF_CHAT_ID = 'chat_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CHAT_ID): vol.Coerce(int),
})


def get_service(hass, config, discovery_info=None):
    """Get the Telegram notification service."""
    chat_id = config.get(CONF_CHAT_ID)
    return TelegramNotificationService(hass, chat_id)


class TelegramNotificationService(BaseNotificationService):
    """Implement the notification service for Telegram."""

    def __init__(self, hass, chat_id):
        """Initialize the service."""
        self._chat_id = chat_id
        self.hass = hass

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        service_data = dict(target=kwargs.get(ATTR_TARGET, self._chat_id))
        if ATTR_TITLE in kwargs:
            service_data.update({ATTR_TITLE: kwargs.get(ATTR_TITLE)})
        if message:
            service_data.update({ATTR_MESSAGE: message})
        data = kwargs.get(ATTR_DATA)

        # Get keyboard info
        if data is not None and ATTR_KEYBOARD in data:
            keys = data.get(ATTR_KEYBOARD)
            keys = keys if isinstance(keys, list) else [keys]
            service_data.update(keyboard=keys)
        elif data is not None and ATTR_INLINE_KEYBOARD in data:
            keys = data.get(ATTR_INLINE_KEYBOARD)
            keys = keys if isinstance(keys, list) else [keys]
            service_data.update(inline_keyboard=keys)

        # Send a photo, a document or a location
        if data is not None and ATTR_PHOTO in data:
            photos = data.get(ATTR_PHOTO, None)
            photos = photos if isinstance(photos, list) else [photos]
            for photo_data in photos:
                service_data.update(photo_data)
                self.hass.services.call(
                    DOMAIN, 'send_photo', service_data=service_data)
            return
        elif data is not None and ATTR_LOCATION in data:
            service_data.update(data.get(ATTR_LOCATION))
            return self.hass.services.call(
                DOMAIN, 'send_location', service_data=service_data)
        elif data is not None and ATTR_DOCUMENT in data:
            service_data.update(data.get(ATTR_DOCUMENT))
            return self.hass.services.call(
                DOMAIN, 'send_document', service_data=service_data)

        # Send message
        _LOGGER.debug('TELEGRAM NOTIFIER calling %s.send_message with %s',
                      DOMAIN, service_data)
        return self.hass.services.call(
            DOMAIN, 'send_message', service_data=service_data)
