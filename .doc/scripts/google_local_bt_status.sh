#!/bin/sh
# gets all bluetooth bonded devices
LOCAL_AUTH_TOKEN=$(cat /config/nogit_scripts/token.google)
curl --insecure -s -H "cast-local-authorization-token: $LOCAL_AUTH_TOKEN" https://0.0.0.0:8443/setup/bluetooth/get_bonded | jq 
