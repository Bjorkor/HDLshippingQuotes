from flask import Flask, render_template, request, url_for, flash, redirect, session
import string
import random
import os
import ship
import json
import pandas as pd
import flask_monitoringdashboard as dashboard
import logging
from logging.handlers import RotatingFileHandler




def id_generator(size=22, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


# Create a custom logger
file_name = "/logs/quotes.log"
# check if file exists
if not os.path.exists(file_name):
    # if not, create the file
    with open(file_name, 'w') as f:
        pass  # file is created but nothing is written to it
logger = logging.getLogger(file_name)

# Create handlers
c_handler = logging.StreamHandler()
f_handler = RotatingFileHandler('/logs/quotes.log', maxBytes=2000, backupCount=5)
c_handler.setLevel(logging.WARNING)
f_handler.setLevel(logging.ERROR)

# Create formatters and add it to handlers
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)

logger.warning('This is a warning')
logger.error('This is an error')



app = Flask(__name__)
dashboard.bind(app)
dashboard.config.init_from(file='config.cfg')
app.config['SECRET_KEY'] = '38db397cc271d9e04158d8738903e2'

messages = {}
sesh = os.urandom(32)


@app.route('/', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        print('received request')
        title = request.form['title']
        if not title:
            flash('Order Number is required!')
        elif len(title) != 8:
            flash('Traverse Order Numbers have 8 digits')
        else:
            print('request accepted')
            # session['ID'] = sesh
            global number
            session['ID'] = title
            number = dowork(title)
            logger.warning(f"running order {number}")
            if messages[number]['data']['retrieveShippingQuote']['carriers'] is None:
                logger.error(f'error found on order {number}')
                return redirect(url_for('whoops'))
            print('redirecting')
            return redirect(url_for('result'))
    return render_template('create.html')


def dowork(ordernum):
    print(type(ordernum))
    print(ordernum)

    info = ship.pull(ordernum)
    quote = json.loads(ship.ship(info['cart'], info['state'], info['zip'], info['entity']))
    messages[ordernum] = quote
    #print('this is the order number working: ' + str(messages[session['ID']]))
    return ordernum


@app.route('/result/', methods=('GET', 'POST'))
def result():
    print('transcribing Their Songs...')
    if request.method == 'POST':
        messages.clear()
        # session.pop('ID', None)
        return redirect(url_for('create'))

    return render_template('index.html', messages=messages[number])

@app.route('/whoops/', methods=('GET', 'POST'))
def whoops():
    return render_template('error.html')