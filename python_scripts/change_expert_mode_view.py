"""
* Use an input_boolean to change between views, showing or hidding groups.
* Check some groups with a connectivity binary_sensor to hide offline devices.

"""

# Groups visibility (expert_view group / normal view group):
GROUPS_EXPERT_MODE = {
    'group.salon': 'group.salon_simple',
    'group.estudio_rpi2h': 'group.estudio_rpi2h_simple',
    'group.dormitorio_rpi2mpd': 'group.dormitorio_rpi2mpd_simple',
    'group.cocina': 'group.cocina_simple',
    'group.caldera': 'group.caldera_simple',
    'group.links': 'group.links_simple',
    'group.cacharros': 'group.cacharros_simple',
    'group.hass_control': 'group.hass_control_simple',
    'group.weather': 'group.weather_simple',
    'group.esp8266_3': 'group.esp8266_3_simple',
    'group.enerpi_max_power_control': None,
    'group.scripts': None,
    'group.host_rpi3': None,
    'group.host_rpi2_hat': None,
    'group.host_rpi2_mpd': None,
    'group.conectivity': None,
    'group.esp8266_2': None,
    'group.menu_automations_1': None,
    'group.menu_automations_2': None,
    'group.menu_automations_3': None,
}

GROUPS_WITH_BINARY_STATE = {
    'group.esp8266_2': 'binary_sensor.esp2_online',
    'group.esp8266_3': 'binary_sensor.esp3_online',
    'group.cocina': 'binary_sensor.cocina_online'
}

# Get new value of 'expert mode'
expert_mode = data.get(
    'expert_mode_state',
    hass.states.get('input_boolean.show_expert_mode').state) == 'on'

for g_expert in GROUPS_EXPERT_MODE:
    visible_expert = expert_mode
    visible_normal = not expert_mode
    g_normal = GROUPS_EXPERT_MODE.get(g_expert)

    # Hide groups of devices offline
    if g_expert in GROUPS_WITH_BINARY_STATE:
        bin_sensor = GROUPS_WITH_BINARY_STATE.get(g_expert)
        bin_state = hass.states.get(bin_sensor).state
        if bin_state is None or bin_state == 'off':
            visible_expert = visible_normal = False

    # Show and hide
    hass.services.call(
        'group', 'set_visibility',
        {"entity_id": g_expert, "visible": visible_expert})
    if g_normal is not None:
        hass.services.call(
            'group', 'set_visibility',
            {"entity_id": g_normal, "visible": visible_normal})
