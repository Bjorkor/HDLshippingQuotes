#!/bin/bash

# Find the PID of the waitress process(es)
pids=$(ps aux | grep '[w]aitress-serve' | awk '{print $2}')

# If the process is running, kill it
if [ ! -z "$pids" ]; then
    echo "Killing existing waitress processes..."
    kill -9 $pids
fi

git stash --all

gh repo sync

git stash pop

# Execute the provided command
echo "Executing command..."
k5start -f /home/ftp/downloads/findock.keytab -- tbarker@HDLUSA.LAN sh -c 'cd /home/ftp/HDLshippingQuotes && /home/tbarker/.local/bin/waitress-serve --port=3000 app:app'
k5start -f /home/ftp/downloads/findock.keytab -- tbarker@HDLUSA.LAN sh -c 'cd /home/ftp/etasFLASK && /home/tbarker/.local/bin/waitress-serve --port=3001 app:app'