#!/bin/bash
KODI_URL="http://192.168.1.56:8080/jsonrpc"

# Envía la orden a KODI de ejecutar el add-on "plugin.audio.lacafetera" con argumentos: mode=playlast,
# que inicia dicho plugin reproduciendo el último episodio disponible de La Cafetera de Radiocable.com
curl -s --user osmc:osmc --header "Content-Type: application/json" --data-binary '{"id": 1, "params": {"params": {"mode": "playlast"}, "addonid": "plugin.audio.lacafetera"}, "jsonrpc": "2.0", "method": "Addons.ExecuteAddon"}' $KODI_URL
exit 0