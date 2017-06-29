"""
# Startup script

Python script to set certain states at HA start and notify.
This unifies various automations and HA scripts in a simpler one.

"""

# noinspection PyUnresolvedReferences
hass = hass
# noinspection PyUnresolvedReferences
logger = logger
# noinspection PyUnresolvedReferences
data = data

SWITCH_EXPERT_MODE = 'input_boolean.show_expert_mode'

# 'expert mode' for filtering groups and visibility control for ESP modules
expert_mode_on = data.get(
    'expert_mode_state',
    hass.states.get(SWITCH_EXPERT_MODE).state)

# Call other python_script to change visibility states
# hass.services.call('python_script', 'change_expert_mode_view',
#                    {"expert_mode_state": expert_mode_on})
hass.states.set(SWITCH_EXPERT_MODE, expert_mode_on)

# Anyone at home?
family_home = hass.states.get('group.family').state == 'home'

# Turn on default outlets
if family_home:
    hass.services.call(
        'switch', 'turn_on',
        {"entity_id": "switch.camara,switch.caldera,switch.esp_plancha"})

# Sync HA dev trackers with manual HomeKit input_booleans
dev_tracking = {'group.eugenio': 'input_boolean.eu_presence',
                'group.mary': 'input_boolean.carmen_presence'}
for group in dev_tracking:
    input_b = dev_tracking.get(group)
    b_in_home = hass.states.get(group).state == 'home'
    b_in_house = hass.states.get(input_b).state == 'on'
    if b_in_house != b_in_home:
        logger.warning('SYNC error %s: dev_tracker=%s, HomeKit=%s',
                       group.lstrip('group.'), b_in_home, b_in_house)
        hass.states.set(input_b, "on" if b_in_home else "off")

# Notify HA init with iOS
hass.services.call(
    'notify', 'ios_iphone',
    {"title": "Home-assistant started",
     "message": "Hass is now ready for you",
     "data": {"push": {"badge": 5,
                       "sound": "US-EN-Morgan-Freeman-Welcome-Home.wav",
                       "category": "CONFIRM"}}})
