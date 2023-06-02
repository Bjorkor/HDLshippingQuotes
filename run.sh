#!/bin/bash

# Author : Zara Ali
# Copyright (c) Tutorialspoint.com
# Script follows here:

echo 'boss makes a dollar, i make a dime, thats why i shit on company time :)'
activate="/home/ftp/flaskapp/venv/bin/activate"
source "$activate"
#kinit tbarker@hdlusa.lan -k -t '/home/ftp/downloads/tbarker.keytab';
cd /home/ftp/flaskapp
nohup waitress-serve --port=3000 app:app

