#!/bin/sh
# disconnects a bt device from the nesthub

LOCAL_AUTH_TOKEN=$(cat /config/nogit_scripts/token.google)
curl --insecure -H "cast-local-authorization-token: $LOCAL_AUTH_TOKEN" \
-H "Content-Type: application/json" \
-X POST -d '{"mac_address":"ef:ef:ef:ef:ef:ef","connect": false,"profile": 2}' https://0.0.0.0:8443/setup/bluetooth/connect
