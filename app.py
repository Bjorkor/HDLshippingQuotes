from flask import Flask, render_template, request, url_for, flash, redirect, session
import string
import random
import os
import ship
import json
import pandas as pd
import flask_monitoringdashboard as dashboard



def id_generator(size=22, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


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
            if messages[number]['data']['retrieveShippingQuote']['carriers'] is None:
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