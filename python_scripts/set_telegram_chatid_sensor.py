"""Python script to set the default chat id for the Telegram Bot."""
SENSOR_CHATID = 'sensor.telegram_default_chatid'
SENSOR_ATTRS = {"friendly_name": "Telegram default chatID",
                "homebridge_hidden": True, "icon": "mdi:telegram"}
                # "icon": "mdi:telegram", "visible": True}

last_chat_id = hass.states.get(SENSOR_CHATID)
chat_id = data.get('chat_id')

if chat_id is not None:
    if last_chat_id is None: # Init
        logger.info("Telegram default chat_id: %s", chat_id)
        hass.states.set(SENSOR_CHATID, chat_id, attributes=SENSOR_ATTRS)
    else:
        last_chat_id = last_chat_id.state
        if last_chat_id != chat_id:
            logger.info("Telegram chat_id: %s -> %s", last_chat_id, chat_id)
            hass.states.set(SENSOR_CHATID, chat_id, attributes=SENSOR_ATTRS)
        else:
            logger.info("Telegram chat_id: no change (%s)", chat_id)
else:
    logger.error("Telegram new chat_id: %s!", chat_id)
