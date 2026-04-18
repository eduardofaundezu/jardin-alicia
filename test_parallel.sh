#!/bin/bash
echo "Iniciando servidor..."
python servidor.py &
SERVER_PID=$!

echo "Iniciando bot..."
python bot_local.py &
BOT_PID=$!

echo "Servidor PID: $SERVER_PID"
echo "Bot PID: $BOT_PID"

wait $SERVER_PID $BOT_PID
