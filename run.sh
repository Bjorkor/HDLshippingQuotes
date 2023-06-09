#!/bin/bash

# Execute the provided command
echo "Executing command..."
k5start -f /home/ftp/downloads/findock.keytab -- tbarker@HDLUSA.LAN sh -c 'cd /home/ftp/HDLshippingQuotes && /home/ftp/HDLshippingQuotes/venv/bin/waitress-serve --port=3000 app:app'

