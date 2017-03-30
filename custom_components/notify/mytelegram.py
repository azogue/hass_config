# -*- coding: utf-8 -*-
"""
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram/

Changes:
- Customized for using any of both parsers (`markdown` and `html`) in any
message with: `data: {'parse_mode': 'html'}`, with markdown as default,
but can be globally customized with 'parse_mode' in yaml config.
- Inline keyboards with `data: {'inline_keyboard':
                                [(text_btn1, data_callback_btn1), ...]}`
- Custom reply_markup (keyboard or inline_keyboard) for every type of message
(message, photo, location & document).
- `disable_notification`, `disable_web_page_preview` and
`reply_to_message_id` optional keyword args.
- Callback replies for edit messages, reply_markup keyboards and captions,
and for answering callback queries.
with: `data: {'callback_query'|'edit_message'|
              'edit_caption'|'edit_replymarkup': ...}`
- Line break between title and message fields: `'{}\n{}'.format(title, message)`

- BREAKING CHANGE: use array of `user_id` to allow one notifier
to comunicate with multiple users (first user is the default, but you
can pass a `ATTR_TARGET=chat_id_X` to send a message to other recipient).
(Reading `chat_id` as User1 to work with old configuration)

"""
import io
import logging
from urllib.error import HTTPError

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_API_KEY, CONF_TIMEOUT, ATTR_LOCATION, ATTR_LATITUDE, ATTR_LONGITUDE)


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-telegram-bot==5.3.0']

ATTR_PARSER = 'parse_mode'
PARSER_MD = 'markdown'
PARSER_HTML = 'html'
ATTR_DISABLE_NOTIFICATION = 'disable_notification'
ATTR_DISABLE_WEB_PAGE_PREVIEW = 'disable_web_page_preview'
ATTR_REPLY_TO_MESSAGE_ID = 'reply_to_message_id'

ATTR_PHOTO = 'photo'
ATTR_KEYBOARD = 'keyboard'
ATTR_KEYBOARD_INLINE = 'inline_keyboard'
ATTR_DOCUMENT = 'document'
ATTR_CAPTION = 'caption'
ATTR_CALLBACK_QUERY = 'callback_query'
ATTR_EDIT_MSG = 'edit_message'
ATTR_EDIT_CAPTION = 'edit_caption'
ATTR_EDIT_REPLYMARKUP = 'edit_replymarkup'
ATTR_URL = 'url'
ATTR_FILE = 'file'
ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'
ATTR_TARGET = 'target'

CONF_USER_ID = 'user_id'
CONF_CHAT_ID = 'chat_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_CHAT_ID, default=None): cv.string,
    vol.Optional(CONF_USER_ID, default=None): {cv.string: cv.positive_int},
    vol.Optional(ATTR_PARSER, default=PARSER_MD): cv.string,
})


# noinspection PyUnusedLocal
def get_service(hass, config, discovery_info=None):
    """Get the Telegram notification service."""
    import telegram

    try:
        chat_id = config.get(CONF_CHAT_ID)
        if chat_id is not None:
            user_id_array = {'User1': chat_id}
        else:
            user_id_array = config.get(CONF_USER_ID)
        api_key = config.get(CONF_API_KEY)
        default_parser = config.get(ATTR_PARSER)
        bot = telegram.Bot(token=api_key)
        username = bot.getMe()['username']
        _LOGGER.info("Telegram bot is '@%s'", username)
    except HTTPError:
        _LOGGER.error("Please check your access token")
        return None

    return TelegramNotificationService(api_key, user_id_array, default_parser)


def load_data(url=None, file=None, username=None, password=None):
    """Load photo/document into ByteIO/File container from a source."""
    try:
        if url is not None:
            # load photo from url
            if username is not None and password is not None:
                req = requests.get(url, auth=(username, password), timeout=15)
            else:
                req = requests.get(url, timeout=15)
            return io.BytesIO(req.content)

        elif file is not None:
            # load photo from file
            return open(file, "rb")
        else:
            _LOGGER.warning("Can't load photo no photo found in params!")

    except OSError as error:
        _LOGGER.error("Can't load photo into ByteIO: %s", error)

    return None


class TelegramNotificationService(BaseNotificationService):
    """Implement the notification service for Telegram."""

    def __init__(self, api_key, user_id_array, parser):
        """Initialize the service."""
        import telegram
        from telegram.parsemode import ParseMode

        self._api_key = api_key
        self._default_user = None
        self._users = {}
        for i, (dev_id, user_id) in enumerate(user_id_array.items()):
            if i == 0:
                self._default_user = user_id
            self._users[user_id] = dev_id
        self._parsers = {PARSER_HTML: ParseMode.HTML,
                         PARSER_MD: ParseMode.MARKDOWN}
        self._parse_mode = self._parsers.get(parser)
        self.bot = telegram.Bot(token=self._api_key)

    @staticmethod
    def _get_msg_ids(msg_data):
        """Get one of (message_id, inline_message_id) from a msg dict,
        returning a tuple."""
        message_id = inline_message_id = None
        if 'message_id' in msg_data:
            message_id = msg_data['message_id']
        else:
            inline_message_id = msg_data['inline_message_id']
        return message_id, inline_message_id

    @staticmethod
    def _send_msg(func_send, msg_error, *args_rep, **kwargs_rep):
        """Send a message."""
        import telegram

        try:
            out = func_send(*args_rep, **kwargs_rep)
            _LOGGER.debug('fsend={}; OUT={}'.format(str(func_send), out))
            return out
        except telegram.error.TelegramError:
            _LOGGER.exception(msg_error)

    def _chat_id(self, target):
        """Validate chat_id target, which comes as list of strings (['12234'])
        or get the default chat_id."""
        if target is not None:
            if isinstance(target, int):
                if target in self._users:
                    return target
                _LOGGER.warning('BAD TARGET "{}", using default: {}'
                                .format(target, self._default_user))
            else:
                # TODO multiple targets!
                try:
                    chat_id = int(target[0])
                    if len(target) > 1:
                        _LOGGER.warning('MULTIPLE TARGET NOT IMPLEMENTED: "{}"'
                                        .format(target[1:]))
                    if chat_id in self._users:
                        return chat_id
                except (ValueError, TypeError):
                    _LOGGER.warning('BAD TARGET "{}", using default: {}'
                                    .format(target, self._default_user))
        return self._default_user

    def send_message(self, message="", target=None, **kwargs):
        """Send a message to a user."""

        def _make_row_of_kb(row_keyboard):
            """Espera un str de texto en botones separados por comas,
            o una lista de tuplas de la forma: [(texto_b1, data_callback_b1),
                                                (texto_b2, data_callback_b2), ]
            Devuelve una lista de InlineKeyboardButton.
            """
            if isinstance(row_keyboard, str):
                return [telegram.InlineKeyboardButton(
                    key.strip()[1:].upper(),
                    callback_data=key)
                        for key in row_keyboard.split(",")]
            elif isinstance(row_keyboard, list):
                return [telegram.InlineKeyboardButton(
                    text_btn, callback_data=data_btn)
                        for text_btn, data_btn in row_keyboard]
            else:
                raise ValueError(str(row_keyboard))

        import telegram

        title = kwargs.get(ATTR_TITLE)
        data = kwargs.get(ATTR_DATA)
        chat_id = self._chat_id(target)
        if title:
            text = '{}\n{}'.format(title, message)
        else:
            text = message

        # defaults
        parser = self._parse_mode
        disable_notification = False
        reply_markup = disable_webprev = reply_to_message_id = timeout = None

        if data is not None:
            if ATTR_PARSER in data:
                parser = self._parsers.get(data[ATTR_PARSER], self._parse_mode)
            if CONF_TIMEOUT in data:
                timeout = data[CONF_TIMEOUT]
            if ATTR_DISABLE_NOTIFICATION in data:
                disable_notification = data[ATTR_DISABLE_NOTIFICATION]
            if ATTR_DISABLE_WEB_PAGE_PREVIEW in data:
                disable_webprev = data[ATTR_DISABLE_WEB_PAGE_PREVIEW]
            if ATTR_REPLY_TO_MESSAGE_ID in data:
                reply_to_message_id = data[ATTR_REPLY_TO_MESSAGE_ID]

            if ATTR_KEYBOARD in data:
                keys = data.get(ATTR_KEYBOARD)
                keys = keys if isinstance(keys, list) else [keys]
                reply_markup = telegram.ReplyKeyboardMarkup(
                    [[key.strip() for key in row.split(",")] for row in keys])
            elif ATTR_KEYBOARD_INLINE in data:

                keys = data.get(ATTR_KEYBOARD_INLINE)
                keys = keys if isinstance(keys, list) else [keys]
                reply_markup = telegram.InlineKeyboardMarkup(
                    [_make_row_of_kb(row) for row in keys])

            # exists data for send a photo/location
            if ATTR_PHOTO in data:
                photos = data.get(ATTR_PHOTO)
                photos = photos if isinstance(photos, list) else [photos]
                for photo_data in photos:
                    self.send_photo(photo_data, chat_id=chat_id,
                                    reply_markup=reply_markup)
                return
            elif ATTR_LOCATION in data:
                return self.send_location(data.get(ATTR_LOCATION),
                                          chat_id=chat_id,
                                          reply_markup=reply_markup)
            elif ATTR_DOCUMENT in data:
                return self.send_document(data.get(ATTR_DOCUMENT),
                                          chat_id=chat_id,
                                          reply_markup=reply_markup)
            elif ATTR_CALLBACK_QUERY in data:
                # send answer to callback query
                callback_data = data.get(ATTR_CALLBACK_QUERY)
                callback_query_id = callback_data.pop('callback_query_id')
                _LOGGER.debug('sending answer_callback_query id {}: "{}" ({})'
                              .format(callback_query_id, text, callback_data))
                return self._send_msg(self.bot.answerCallbackQuery,
                                      "Error sending answer to callback query",
                                      callback_query_id,
                                      text=text, **callback_data)
            elif ATTR_EDIT_MSG in data:
                message_id, inline_message_id = self._get_msg_ids(
                    data.get(ATTR_EDIT_MSG))
                _LOGGER.debug('editing message w/id {}: "{}" ({})'
                              .format(message_id or inline_message_id, text,
                                      data.get(ATTR_EDIT_MSG)))
                return self._send_msg(self.bot.editMessageText,
                                      "Error editing text message",
                                      text,
                                      chat_id=chat_id,
                                      message_id=message_id,
                                      inline_message_id=inline_message_id,
                                      parse_mode=parser,
                                      disable_web_page_preview=disable_webprev,
                                      reply_markup=reply_markup,
                                      timeout=timeout)
            elif ATTR_EDIT_CAPTION in data:
                caption = data.get(ATTR_EDIT_CAPTION)['caption']
                message_id, inline_message_id = self._get_msg_ids(
                    data.get(ATTR_EDIT_CAPTION))
                _LOGGER.debug('editing message caption w/id {}: "{}" ({})'
                              .format(message_id or inline_message_id, text,
                                      data.get(ATTR_EDIT_CAPTION)))
                return self._send_msg(self.bot.editMessageCaption,
                                      "Error editing message caption",
                                      chat_id=chat_id,
                                      message_id=message_id,
                                      inline_message_id=inline_message_id,
                                      caption=caption,
                                      reply_markup=reply_markup,
                                      timeout=timeout)
            elif ATTR_EDIT_REPLYMARKUP in data:
                message_id, inline_message_id = self._get_msg_ids(
                    data.get(ATTR_EDIT_REPLYMARKUP))
                _LOGGER.debug('editing reply_markup w/id {}: "{}" ({})'
                              .format(message_id or inline_message_id, text,
                                      data.get(ATTR_EDIT_REPLYMARKUP)))
                return self._send_msg(self.bot.editMessageReplyMarkup,
                                      "Error editing reply_markup",
                                      chat_id=chat_id,
                                      message_id=message_id,
                                      inline_message_id=inline_message_id,
                                      reply_markup=reply_markup,
                                      timeout=timeout)

        # send text message
        _LOGGER.debug('sending message: "{}"'.format(text))
        return self._send_msg(self.bot.sendMessage,
                              "Error sending message",
                              chat_id, text,
                              parse_mode=parser, reply_markup=reply_markup,
                              disable_web_page_preview=disable_webprev,
                              disable_notification=disable_notification,
                              reply_to_message_id=reply_to_message_id,
                              timeout=timeout)

    def send_photo(self, data, chat_id=None,
                   reply_markup=None,
                   disable_notification=False,
                   reply_to_message_id=None, timeout=None):
        """Send a photo."""
        caption = data.get(ATTR_CAPTION)
        chat_id = self._chat_id(chat_id)

        # send photo
        photo = load_data(
            url=data.get(ATTR_URL),
            file=data.get(ATTR_FILE),
            username=data.get(ATTR_USERNAME),
            password=data.get(ATTR_PASSWORD),
        )
        return self._send_msg(self.bot.sendPhoto,
                              "Error sending photo",
                              chat_id, photo, caption=caption,
                              reply_markup=reply_markup,
                              disable_notification=disable_notification,
                              reply_to_message_id=reply_to_message_id,
                              timeout=timeout)

    def send_document(self, data, chat_id=None,
                      reply_markup=None,
                      disable_notification=False,
                      reply_to_message_id=None, timeout=None):
        """Send a document."""
        caption = data.get(ATTR_CAPTION)
        chat_id = self._chat_id(chat_id)

        # send document
        document = load_data(
            url=data.get(ATTR_URL),
            file=data.get(ATTR_FILE),
            username=data.get(ATTR_USERNAME),
            password=data.get(ATTR_PASSWORD),
        )
        return self._send_msg(self.bot.sendDocument,
                              "Error sending document",
                              chat_id, document,
                              caption=caption,
                              reply_markup=reply_markup,
                              disable_notification=disable_notification,
                              reply_to_message_id=reply_to_message_id,
                              timeout=timeout)

    def send_location(self, gps, chat_id=None,
                      reply_markup=None,
                      disable_notification=False,
                      reply_to_message_id=None, timeout=None):
        """Send a location."""
        latitude = float(gps.get(ATTR_LATITUDE, 0.0))
        longitude = float(gps.get(ATTR_LONGITUDE, 0.0))
        chat_id = self._chat_id(chat_id)

        # send location
        return self._send_msg(self.bot.sendLocation,
                              "Error sending location",
                              chat_id=chat_id,
                              latitude=latitude, longitude=longitude,
                              reply_markup=reply_markup,
                              disable_notification=disable_notification,
                              reply_to_message_id=reply_to_message_id,
                              timeout=timeout)
