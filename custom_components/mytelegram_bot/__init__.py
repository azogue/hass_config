# -*- coding: utf-8 -*-
"""
Component to send and receive telegram messages, including callback queries.

Either by polling or webhook.
"""
import asyncio
import io
from functools import partial
import logging
import os
import requests
from urllib.error import HTTPError
import voluptuous as vol
from homeassistant.config import load_yaml_config_file
from homeassistant.components.notify import (
    ATTR_MESSAGE, ATTR_TITLE, ATTR_DATA, BaseNotificationService)
from homeassistant.const import (
    CONF_PLATFORM, CONF_API_KEY, CONF_TIMEOUT, ATTR_LATITUDE, ATTR_LONGITUDE)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery, config_per_platform
from homeassistant.setup import async_prepare_setup_platform

DOMAIN = 'mytelegram_bot'
REQUIREMENTS = ['python-telegram-bot==5.3.1']

_LOGGER = logging.getLogger(__name__)

EVENT_TELEGRAM_COMMAND = 'telegram_command'
EVENT_TELEGRAM_TEXT = 'telegram_text'
EVENT_TELEGRAM_CALLBACK = 'telegram_callback'

CONF_ALLOWED_CHAT_IDS = 'allowed_chat_ids'
PARSER_MD = 'markdown'
PARSER_HTML = 'html'
ATTR_TEXT = 'text'
ATTR_COMMAND = 'command'
ATTR_USER_ID = 'user_id'
ATTR_ARGS = 'args'
ATTR_MSG = 'message'
ATTR_CHAT_INSTANCE = 'chat_instance'
ATTR_CHAT_ID = 'chat_id'
ATTR_MSGID = 'id'
ATTR_FROM_FIRST = 'from_first'
ATTR_FROM_LAST = 'from_last'
ATTR_SHOW_ALERT = 'show_alert'
ATTR_MESSAGEID = 'message_id'
ATTR_PARSER = 'parse_mode'
ATTR_DISABLE_NOTIF = 'disable_notification'
ATTR_DISABLE_WEB_PREV = 'disable_web_page_preview'
ATTR_REPLY_TO_MSGID = 'reply_to_message_id'
ATTR_CALLBACK_QUERY = 'callback_query'
ATTR_CALLBACK_QUERY_ID = 'callback_query_id'
ATTR_TARGET = 'target'
ATTR_KEYBOARD = 'keyboard'
ATTR_KEYBOARD_INLINE = 'inline_keyboard'
ATTR_URL = 'url'
ATTR_FILE = 'file'
ATTR_CAPTION = 'caption'
ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ALLOWED_CHAT_IDS):
        vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Optional(ATTR_PARSER, default=PARSER_MD): cv.string,
}, extra=vol.ALLOW_EXTRA)

BASE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Optional(ATTR_PARSER): cv.string,
    vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
    vol.Optional(ATTR_DISABLE_WEB_PREV): cv.boolean,
    vol.Optional(ATTR_KEYBOARD): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
}, extra=vol.ALLOW_EXTRA)
SERVICE_SEND_MESSAGE = 'send_message'
SERVICE_SCHEMA_SEND_MESSAGE = BASE_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE): cv.template,
})
SERVICE_SEND_PHOTO = 'send_photo'
SERVICE_SEND_DOCUMENT = 'send_document'
SERVICE_SCHEMA_SEND_FILE = BASE_SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_URL): cv.string,
    vol.Optional(ATTR_FILE): cv.string,
    vol.Optional(ATTR_CAPTION): cv.string,
    vol.Optional(ATTR_USERNAME): cv.string,
    vol.Optional(ATTR_PASSWORD): cv.string,
})
SERVICE_SEND_LOCATION = 'send_location'
SERVICE_SCHEMA_SEND_LOCATION = BASE_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_LONGITUDE): float,
    vol.Required(ATTR_LATITUDE): float,
})
SERVICE_EDIT_MESSAGE = 'edit_message'
SERVICE_SCHEMA_EDIT_MESSAGE = SERVICE_SCHEMA_SEND_MESSAGE.extend({
    vol.Required(ATTR_MESSAGEID): vol.Any(cv.positive_int, cv.string),
    vol.Required(ATTR_CHAT_ID): cv.positive_int,
})
SERVICE_EDIT_CAPTION = 'edit_caption'
SERVICE_SCHEMA_EDIT_CAPTION = vol.Schema({
    vol.Required(ATTR_MESSAGEID): vol.Any(cv.positive_int, cv.string),
    vol.Required(ATTR_CHAT_ID): cv.positive_int,
    vol.Required(ATTR_CAPTION): cv.string,
    vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
}, extra=vol.ALLOW_EXTRA)
SERVICE_EDIT_REPLYMARKUP = 'edit_replymarkup'
SERVICE_SCHEMA_EDIT_REPLYMARKUP = vol.Schema({
    vol.Required(ATTR_MESSAGEID): vol.Any(cv.positive_int, cv.string),
    vol.Required(ATTR_CHAT_ID): cv.positive_int,
    vol.Required(ATTR_KEYBOARD_INLINE): cv.ensure_list,
}, extra=vol.ALLOW_EXTRA)
SERVICE_ANSWER_CALLBACK_QUERY = 'answer_callback_query'
SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Required(ATTR_CALLBACK_QUERY_ID): cv.positive_int,
    vol.Optional(ATTR_SHOW_ALERT): cv.boolean,
}, extra=vol.ALLOW_EXTRA)


def load_data(url=None, file=None, username=None, password=None):
    """Load photo/document into ByteIO/File container from a source."""
    try:
        if url is not None:
            # Load photo from URL
            if username is not None and password is not None:
                req = requests.get(url, auth=(username, password), timeout=15)
            else:
                req = requests.get(url, timeout=15)
            return io.BytesIO(req.content)

        elif file is not None:
            # Load photo from file
            return open(file, "rb")
        else:
            _LOGGER.warning("Can't load photo. No photo found in params!")

    except OSError as error:
        _LOGGER.error("Can't load photo into ByteIO: %s", error)

    return None


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_get_service(hass, config, discovery_info=None):
    """Get the Telegram notification service."""
    from telegram import Bot

    try:
        allowed_chat_ids = config.get(CONF_ALLOWED_CHAT_IDS)
        api_key = config.get(CONF_API_KEY)
        parser = config.get(ATTR_PARSER)

        bot = Bot(token=api_key)
        username = bot.getMe()['username']
        _LOGGER.debug("Telegram bot is '@%s', users allowed: %s, default=%s",
                      username, allowed_chat_ids, allowed_chat_ids[0])
    except HTTPError:
        _LOGGER.error("Please check your access token")
        return None

    return TelegramNotificationService(hass, api_key, allowed_chat_ids, parser)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the telegram bot component."""

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    @asyncio.coroutine
    def async_setup_platform(p_type, p_config=None, discovery_info=None):
        """Setup a telegram bot platform."""
        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown notification service specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)
        try:
            if hasattr(platform, 'async_setup_platform'):
                receiver_service = yield from \
                    platform.async_setup_platform(hass, p_config,
                                                  discovery_info)
            elif hasattr(platform, 'setup_platform'):
                receiver_service = yield from hass.loop.run_in_executor(
                    None, platform.setup_platform, hass, p_config,
                    discovery_info)
            else:
                raise HomeAssistantError("Invalid telegram bot platform.")

            if receiver_service is None:
                _LOGGER.error(
                    "Failed to initialize telegram bot %s", p_type)
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up platform %s', p_type)
            return

        notify_service = None
        try:
            notify_service = yield from \
                async_get_service(hass, p_config, discovery_info)

            if notify_service is None:
                _LOGGER.error(
                    "Failed to initialize notification services")
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up notification services')
            return

        notify_service.hass = hass

        @asyncio.coroutine
        def async_send_telegram_message(service):
            """Handle sending Telegram Bot message service calls."""

            def _render_template_attr(data, attribute):
                attribute_templ = data.get(attribute)
                if attribute_templ:
                    attribute_templ.hass = hass
                    attribute_templ.hass = hass
                    data[attribute] = attribute_templ.async_render()

            msgtype = service.service
            kwargs = dict(service.data)
            _render_template_attr(kwargs, ATTR_MESSAGE)
            _render_template_attr(kwargs, ATTR_TITLE)
            _LOGGER.debug('NEW telegram_message "%s": %s', msgtype, kwargs)

            if msgtype == SERVICE_SEND_MESSAGE:
                yield from notify_service.async_send_message(**kwargs)
            elif msgtype == SERVICE_SEND_PHOTO:
                yield from notify_service.async_send_file(True, **kwargs)
            elif msgtype == SERVICE_SEND_DOCUMENT:
                yield from notify_service.async_send_file(False, **kwargs)
            elif msgtype == SERVICE_SEND_LOCATION:
                yield from notify_service.async_send_location(**kwargs)
            elif msgtype == SERVICE_ANSWER_CALLBACK_QUERY:
                yield from notify_service.async_answer_callback_query(**kwargs)
            else:
                yield from notify_service.async_edit_message(msgtype, **kwargs)

        # Register notification services
        hass.services.async_register(
            DOMAIN, SERVICE_SEND_MESSAGE, async_send_telegram_message,
            descriptions.get(SERVICE_SEND_MESSAGE),
            schema=SERVICE_SCHEMA_SEND_MESSAGE)

        hass.services.async_register(
            DOMAIN, SERVICE_SEND_PHOTO, async_send_telegram_message,
            descriptions.get(SERVICE_SEND_PHOTO),
            schema=SERVICE_SCHEMA_SEND_FILE)
        hass.services.async_register(
            DOMAIN, SERVICE_SEND_DOCUMENT, async_send_telegram_message,
            descriptions.get(SERVICE_SEND_DOCUMENT),
            schema=SERVICE_SCHEMA_SEND_FILE)
        hass.services.async_register(
            DOMAIN, SERVICE_SEND_LOCATION, async_send_telegram_message,
            descriptions.get(SERVICE_SEND_LOCATION),
            schema=SERVICE_SCHEMA_SEND_LOCATION)

        hass.services.async_register(
            DOMAIN, SERVICE_EDIT_MESSAGE, async_send_telegram_message,
            descriptions.get(SERVICE_EDIT_MESSAGE),
            schema=SERVICE_SCHEMA_EDIT_MESSAGE)
        hass.services.async_register(
            DOMAIN, SERVICE_EDIT_CAPTION, async_send_telegram_message,
            descriptions.get(SERVICE_EDIT_CAPTION),
            schema=SERVICE_SCHEMA_EDIT_CAPTION)
        hass.services.async_register(
            DOMAIN, SERVICE_EDIT_REPLYMARKUP, async_send_telegram_message,
            descriptions.get(SERVICE_EDIT_REPLYMARKUP),
            schema=SERVICE_SCHEMA_EDIT_REPLYMARKUP)

        hass.services.async_register(
            DOMAIN, SERVICE_ANSWER_CALLBACK_QUERY, async_send_telegram_message,
            descriptions.get(SERVICE_ANSWER_CALLBACK_QUERY),
            schema=SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY)

        return True

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        # Only one platform (webhooks or polling) is allowed
        yield from asyncio.wait(setup_tasks[:1], loop=hass.loop)

    @asyncio.coroutine
    def async_platform_discovered(platform, info):
        """Callback to load a platform."""
        yield from async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True


class TelegramNotificationService(BaseNotificationService):
    """Implement the notification services for the Telegram Bot domain."""

    def __init__(self, hass, api_key, allowed_chat_ids, parser):
        """Initialize the service."""
        from telegram import Bot
        from telegram.parsemode import ParseMode

        self.allowed_chat_ids = allowed_chat_ids
        self._default_user = self.allowed_chat_ids[0]
        self._last_message_id = {user: None for user in self.allowed_chat_ids}
        self._parsers = {PARSER_HTML: ParseMode.HTML,
                         PARSER_MD: ParseMode.MARKDOWN}
        self._parse_mode = self._parsers.get(parser)
        self.bot = Bot(token=api_key)
        self.hass = hass

    def async_send_file(self, is_photo=True, **kwargs):
        """Send a photo or a document.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.loop.run_in_executor(
            None, partial(self.send_file, is_photo, **kwargs))

    def async_send_location(self, latitude, longitude, **kwargs):
        """Send a location.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.loop.run_in_executor(
            None, partial(self.send_location, latitude, longitude, **kwargs))

    def async_edit_message(self, type_edit, chat_id=None, **kwargs):
        """Edit a previously sent message.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.loop.run_in_executor(
            None, partial(self.edit_message, type_edit, chat_id, **kwargs))

    def async_answer_callback_query(self, message,
                                    callback_query_id, **kwargs):
        """Answer to a callback query.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.loop.run_in_executor(
            None, partial(self.send_answer_callback_query, message,
                          callback_query_id, **kwargs))

    def _get_msg_ids(self, msg_data, chat_id):
        """Get the message id to edit.

        This can be one of (message_id, inline_message_id) from a msg dict,
        returning a tuple.
        **You can use 'last' as message_id** to edit
        the last sended message in the chat_id.
        """
        message_id = inline_message_id = None
        if ATTR_MESSAGEID in msg_data:
            message_id = msg_data[ATTR_MESSAGEID]
            if (isinstance(message_id, str) and (message_id == 'last') and
                    (self._last_message_id[chat_id] is not None)):
                message_id = self._last_message_id[chat_id]
        else:
            inline_message_id = msg_data['inline_message_id']
        return message_id, inline_message_id

    def _get_target_chat_ids(self, target):
        """Validate chat_id targets or return default target (fist defined).

        :param target: optional list of strings or ints (['12234'] or [12234])
        :return list of chat_id targets (integers)
        """
        if target is not None:
            if isinstance(target, int):
                if target in self.allowed_chat_ids:
                    return [target]
                _LOGGER.warning('BAD TARGET "%s", using default: %s',
                                target, self._default_user)
            else:
                try:
                    chat_ids = [int(t) for t in target
                                if int(t) in self.allowed_chat_ids]
                    if len(chat_ids) > 0:
                        return chat_ids
                    _LOGGER.warning('ALL BAD TARGETS: "%s"', target)
                except (ValueError, TypeError):
                    _LOGGER.warning('BAD TARGET DATA "%s", using default: %s',
                                    target, self._default_user)
        return [self._default_user]

    def _get_msg_kwargs(self, data):
        """Get parameters in message data kwargs."""

        def _make_row_of_kb(row_keyboard):
            """Make a list of InlineKeyboardButtons from a list of tuples.

            :param row_keyboard: [(text_b1, data_callback_b1),
                                  (text_b2, data_callback_b2), ...]
            """
            from telegram import InlineKeyboardButton
            if isinstance(row_keyboard, str):
                return [InlineKeyboardButton(
                    key.strip()[1:].upper(),
                    callback_data=key)
                        for key in row_keyboard.split(",")]
            elif isinstance(row_keyboard, list):
                return [InlineKeyboardButton(
                    text_btn, callback_data=data_btn)
                        for text_btn, data_btn in row_keyboard]
            else:
                raise ValueError(str(row_keyboard))

        # Defaults
        params = dict(parse_mode=self._parse_mode,
                      disable_notification=False,
                      disable_web_page_preview=None,
                      reply_to_message_id=None,
                      reply_markup=None,
                      timeout=None)
        if data is not None:
            if ATTR_PARSER in data:
                params['parse_mode'] = self._parsers.get(data[ATTR_PARSER],
                                                         self._parse_mode)
            if CONF_TIMEOUT in data:
                params['timeout'] = data[CONF_TIMEOUT]
            if ATTR_DISABLE_NOTIF in data:
                params['disable_notification'] = data[ATTR_DISABLE_NOTIF]
            if ATTR_DISABLE_WEB_PREV in data:
                params[ATTR_DISABLE_WEB_PREV] = data[ATTR_DISABLE_WEB_PREV]
            if ATTR_REPLY_TO_MSGID in data:
                params[ATTR_REPLY_TO_MSGID] = data[ATTR_REPLY_TO_MSGID]
            # Keyboards:
            if ATTR_KEYBOARD in data:
                from telegram import ReplyKeyboardMarkup
                keys = data.get(ATTR_KEYBOARD)
                keys = keys if isinstance(keys, list) else [keys]
                params['reply_markup'] = ReplyKeyboardMarkup(
                    [[key.strip() for key in row.split(",")] for row in keys])
            elif ATTR_KEYBOARD_INLINE in data:
                from telegram import InlineKeyboardMarkup
                keys = data.get(ATTR_KEYBOARD_INLINE)
                keys = keys if isinstance(keys, list) else [keys]
                params['reply_markup'] = InlineKeyboardMarkup(
                    [_make_row_of_kb(row) for row in keys])
        _LOGGER.debug('data %s --> params %s.', data, params)
        return params

    def _send_msg(self, func_send, msg_error, *args_rep, **kwargs_rep):
        """Send one message."""
        from telegram.error import TelegramError
        try:
            out = func_send(*args_rep, **kwargs_rep)
            if not isinstance(out, bool) and hasattr(out, ATTR_MESSAGEID):
                chat_id = out.chat_id
                self._last_message_id[chat_id] = out[ATTR_MESSAGEID]
                _LOGGER.debug('LAST MSG ID: %s (from chat_id %s)',
                              self._last_message_id, chat_id)
            elif not isinstance(out, bool):
                _LOGGER.warning('UPDATE LAST MSG??: out_type:%s, out=%s',
                                type(out), out)
            return out
        except TelegramError:
            _LOGGER.exception(msg_error)

    def send_message(self, message="", target=None, **kwargs):
        """Send a message to one or multiple pre-allowed chat_ids."""
        title = kwargs.get(ATTR_TITLE)
        text = '{}\n{}'.format(title, message) if title else message
        params = self._get_msg_kwargs(kwargs)
        for chat_id in self._get_target_chat_ids(target):
            _LOGGER.debug('send_message in chat_id %s with params: %s',
                          chat_id, params)
            self._send_msg(self.bot.sendMessage,
                           "Error sending message",
                           chat_id, text, **params)

    def edit_message(self, type_edit, chat_id=None, **kwargs):
        """Edit a previously sent message."""
        chat_id = self._get_target_chat_ids(chat_id)[0]
        message_id, inline_message_id = self._get_msg_ids(kwargs, chat_id)
        params = self._get_msg_kwargs(kwargs)
        _LOGGER.debug('edit_message %s in chat_id %s with params: %s',
                      message_id or inline_message_id, chat_id, params)
        if type_edit == SERVICE_EDIT_MESSAGE:
            message = kwargs.get(ATTR_MESSAGE)
            title = kwargs.get(ATTR_TITLE)
            text = '{}\n{}'.format(title, message) if title else message
            _LOGGER.debug('editing message w/id %s.',
                          message_id or inline_message_id)
            return self._send_msg(self.bot.editMessageText,
                                  "Error editing text message",
                                  text, chat_id=chat_id, message_id=message_id,
                                  inline_message_id=inline_message_id,
                                  **params)
        elif type_edit == SERVICE_EDIT_CAPTION:
            func_send = self.bot.editMessageCaption
            params[ATTR_CAPTION] = kwargs.get(ATTR_CAPTION)
        else:
            func_send = self.bot.editMessageReplyMarkup
        return self._send_msg(func_send,
                              "Error editing message attributes",
                              chat_id=chat_id, message_id=message_id,
                              inline_message_id=inline_message_id,
                              **params)

    def send_answer_callback_query(self, message, callback_query_id,
                                   show_alert=False, **kwargs):
        """Send a message to one or multiple pre-defined users."""
        params = self._get_msg_kwargs(kwargs)
        _LOGGER.debug('answer_callback_query w/callback_id %s: %s, alert: %s.',
                      callback_query_id, message, show_alert)
        self._send_msg(self.bot.answerCallbackQuery,
                       "Error sending answer callback query",
                       callback_query_id,
                       text=message, show_alert=show_alert, **params)

    def send_file(self, is_photo=True, target=None, **kwargs):
        """Send a photo or a document."""
        file = load_data(
            url=kwargs.get(ATTR_URL),
            file=kwargs.get(ATTR_FILE),
            username=kwargs.get(ATTR_USERNAME),
            password=kwargs.get(ATTR_PASSWORD),
        )
        params = self._get_msg_kwargs(kwargs)
        caption = kwargs.get(ATTR_CAPTION)
        func_send = self.bot.sendPhoto if is_photo else self.bot.sendDocument
        for chat_id in self._get_target_chat_ids(target):
            _LOGGER.debug('send file %s to chat_id %s. Caption: %s.',
                          file, chat_id, caption)
            self._send_msg(func_send, "Error sending file",
                           chat_id, file, caption=caption, **params)

    def send_location(self, latitude, longitude, target=None, **kwargs):
        """Send a location."""
        latitude = float(latitude)
        longitude = float(longitude)
        params = self._get_msg_kwargs(kwargs)
        for chat_id in self._get_target_chat_ids(target):
            _LOGGER.debug('send location %s/%s to chat_id %s.',
                          latitude, longitude, chat_id)
            self._send_msg(self.bot.sendLocation,
                           "Error sending location",
                           chat_id=chat_id,
                           latitude=latitude, longitude=longitude, **params)


class BaseTelegramBotEntity:
    """The base class for the telegram bot."""

    def __init__(self, hass, allowed_chat_ids):
        """Initialize the bot base class."""
        self.allowed_chat_ids = allowed_chat_ids
        self.hass = hass

    def _get_message_data(self, msg_data):
        if (not msg_data
            or ('text' not in msg_data and 'data' not in msg_data)
            or 'from' not in msg_data
            or msg_data['from'].get('id') not in self.allowed_chat_ids):
            # Message is not correct.
            _LOGGER.error("Incoming message does not have required data (%s)",
                          msg_data)
            return None
        return {
            ATTR_USER_ID: msg_data['from']['id'],
            ATTR_FROM_FIRST: msg_data['from']['first_name'],
            ATTR_FROM_LAST: msg_data['from']['last_name']}

    def process_message(self, data):
        """Check for basic message rules and fire an event if message is ok."""
        if ATTR_MSG in data:
            event = EVENT_TELEGRAM_COMMAND
            data = data.get(ATTR_MSG)
            event_data = self._get_message_data(data)
            if event_data is None:
                return False

            if data['text'][0] == '/':
                pieces = data['text'].split(' ')
                event_data[ATTR_COMMAND] = pieces[0]
                event_data[ATTR_ARGS] = pieces[1:]
            else:
                event_data[ATTR_TEXT] = data['text']
                event = EVENT_TELEGRAM_TEXT

            self.hass.bus.async_fire(event, event_data)
            return True
        elif ATTR_CALLBACK_QUERY in data:
            event = EVENT_TELEGRAM_CALLBACK
            data = data.get('callback_query')
            event_data = self._get_message_data(data)
            if event_data is None:
                return False

            event_data[ATTR_DATA] = data[ATTR_DATA]
            event_data[ATTR_MSG] = data[ATTR_MSG]
            event_data[ATTR_CHAT_INSTANCE] = data[ATTR_CHAT_INSTANCE]
            event_data[ATTR_MSGID] = data[ATTR_MSGID]

            self.hass.bus.async_fire(event, event_data)
            return True
        else:
            # Some other thing...
            _LOGGER.warning('SOME OTHER THING RECEIVED --> "%s"', data)
            return False
