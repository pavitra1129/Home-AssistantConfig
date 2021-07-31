#!/bin/sh
# checks if soundbar is connected, exit code 0 will signal that the switch is on
# so homeassistant has an easy time to create a commandline switch
# https://www.home-assistant.io/integrations/switch.command_line/

LOCAL_AUTH_TOKEN=$(cat /config/nogit_scripts/token.google)
curl --insecure -s -H "cast-local-authorization-token: $LOCAL_AUTH_TOKEN" \
https://0.0.0.0:8443/setup/bluetooth/get_bonded | jq '.[] | select(.name == "My Cool Soundbar") | {connected} | .[]' > /config/tmp/switch_state.log;
if grep 'true' /config/tmp/switch_state.log
 then
  exit 0
 else
  exit 1
fi
