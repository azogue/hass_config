"""
# Python script to select light scenes from an input_select.

Hue profiles (x, y, bright):
- relax	0.5119	0.4147	144
- energize	0.368	0.3686	203
- reading	0.4448	0.4066	240
- concentrate	0.5119	0.4147	219 <--BAD
    --> brightness: 254
        xy_color: [0.3151, 0.3251]
"""

INPUT_SELECT = 'input_select.salon_light_scene'
LIGHTS_TO_CONTROL = 'light.bola_grande,light.bola_pequena,light.cuenco,' \
                    'light.pie_sofa,light.pie_tv'

scene_selection = data.get("scene")

if scene_selection == 'OFF':
    hass.services.call('light', 'turn_off',
                       {"entity_id": LIGHTS_TO_CONTROL})
elif scene_selection == 'Lectura':
    hass.services.call('light', 'turn_on',
                       {"entity_id": LIGHTS_TO_CONTROL,
                        "profile": "reading"})
elif scene_selection == 'Relax':
    hass.services.call('light', 'turn_on',
                       {"entity_id": LIGHTS_TO_CONTROL,
                        "profile": "relax"})
elif scene_selection == 'Energía':
    hass.services.call('light', 'turn_on',
                       {"entity_id": LIGHTS_TO_CONTROL,
                        "profile": "energize",
                        "brightness": 254})
elif scene_selection == 'Concentración':
    hass.services.call('light', 'turn_on',
                       {"entity_id": LIGHTS_TO_CONTROL,
                        "xy_color": [0.3151, 0.3251],
                        "brightness": 254})
else:
    logger.error("SCENE not recognized: %s", scene_selection)


