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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import traceback
from dotenv import load_dotenv
import sqlite3
import subprocess
from collections import defaultdict


def shipcodes(input_entry):
    mapping = {
        "SPD": "SPD",
        "FEDEX_GROUND": "R02",
        "FEDEX_2_DAY": "F11",
        "PRIORITY_OVERNIGHT": "F01",
        "FIRST_OVERNIGHT": "F15",
        "STANDARD_OVERNIGHT": "F06",
        "Priority Mail": "M02",
        "USPS Ground Advantage": "M05",
        "collect": "WC",
        "DELIVERY": "PDS Run",
        "1DA": "U01",
        "3DS": "U21",
        "1DM": "U60",
        "1DP": "U43",
        "2DA": "U07",
        "GND": "U11",
        "MSN": "MSN",
        "GRB": "GRB",
        "EAU": "EAU",
        "MKE": "MKE",
        "CWA": "CWA",
        "CS6": "CS6",
        "TRUCK": "Truck",
        "STPPOSPS": "M05",
        "USG": "SUP"
    }

    return mapping.get(input_entry, "Unknown")

#init DB
script_directory = os.path.dirname(os.path.abspath(__file__))
relative_db_directory = 'DB'
db_directory = os.path.join(script_directory, relative_db_directory)
if not os.path.exists(db_directory):
    os.makedirs(db_directory)
db_file_path = os.path.join(db_directory, 'quotes_history.db')
conn = sqlite3.connect(db_file_path)
cursor = conn.cursor()
cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='quotes'")
result = cursor.fetchone()
conn.commit()
if result is None:

    cursor.execute('''
            CREATE TABLE quotes (
                id INTEGER PRIMARY KEY,
                orderNumber INTEGER NOT NULL,
                quote TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
    conn.commit()
    conn.close()

def collectData(order, quote, date):
    logger.info('saving quote to local DB')
    try:
        colconn = sqlite3.connect(db_file_path)
        colcursor = colconn.cursor()
        colcursor.execute("INSERT INTO quotes (orderNumber, quote, date) VALUES (?, ?, ?)",
                       (order, quote, date))
        colconn.commit()
        colconn.close()
    except Exception as e:
        logger.error(f'The following error occurred while saving quote to local DB: {e}')

def id_generator(size=22, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


load_dotenv()

# Create 'logs' directory if it does not exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Creating a dedicated logger
logger = logging.getLogger('quotes_logger')

# Defining logging level from configuration
log_level = os.environ.get('LOG_LEVEL', 'DEBUG')
logger.setLevel(logging.getLevelName(log_level))

# Create handlers
c_handler = logging.StreamHandler()
f_handler = RotatingFileHandler('logs/quotes.log', maxBytes=20000000, backupCount=5)

# Set levels for handlers (optional)
c_handler.setLevel(logging.WARNING)
f_handler.setLevel(logging.DEBUG)

# Create formatters and add it to handlers
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
try:
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)
except Exception as e:
    logger.warning(f"Failed to add handler: {str(e)}")



# Adding context information using LoggerAdapter
context = {'app_name': 'HDL Shipping Quotes'}
logger = logging.LoggerAdapter(logger, context)




app = Flask(__name__)
dashboard.bind(app)
dashboard.config.init_from(file='config.cfg')
app.config['SECRET_KEY'] = '38db397cc271d9e04158d8738903e2'

messages = {}
sesh = os.urandom(32)


@app.route('/', methods=('GET', 'POST'))
def create():
    branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode('utf-8')
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
            logger.info(f"running order")
            try:
                number = dowork(title)
                logger.info(f"running order {number}")
                logger.info(messages[number])
                if messages[number]['data']['retrieveShippingQuote']['carriers'] is None:
                    logger.error(f'error found on order {number}')
                    return redirect(url_for('whoops'))
                print('redirecting')
                return redirect(url_for('result'))
            except Exception as e:
                logger.error(f"Unexpected Error: {str(e)}")
                flash("An unexpected error occurred. Please wait a few minutes, and try again.")
    return render_template('create.html', branch=branch)


def dowork(ordernum):
    now = str(datetime.datetime.utcnow())
    logger.info('begin pulling local order')
    info = ship.pull(ordernum)
    logger.info('local order pulled')
    logger.info('reaching out to shipperhq api')
    quote = json.loads(ship.ship(info['cart'], info['state'], info['zip'], info['entity']))
    logger.info('response from shipperhq recieved')
    messages[ordernum] = quote
    collectData(int(ordernum), str(quote), str(now))
    #print('this is the order number working: ' + str(messages[session['ID']]))
    return ordernum


@app.route('/result/', methods=('GET', 'POST'))
def result():
    print('transcribing Their Songs...')
    if request.method == 'POST':
        messages.clear()
        # session.pop('ID', None)
        return redirect(url_for('create'))
    if messages[number]['data']['retrieveShippingQuote']['carriers'] is not None:
        book = defaultdict()
        for x in messages[number]['data']['retrieveShippingQuote']['carriers']:
            carrierTitle = x['carrierTitle']
            charges = []
            if len(x['shippingRates']) is not 0:
                for z in x['shippingRates']:
                    code = shipcodes(z['code'])
                    qcharge = z['totalCharges']
                    service = z['title']
                    charge = {'qcode': code, 'qcharge': qcharge, 'qservice': service}
                    charges.append(charge)
            else:
                charge = {'qcode': 'No Rates Available', 'qcharge': 0, 'qservice': 'No Rates Available'}
                charges.append(charge)
            book[carrierTitle] = charges
    return render_template('index.html', messages=book)

@app.route('/whoops/', methods=('GET', 'POST'))
def whoops():
    return render_template('error.html')

@app.route('/ticket/', methods=('GET', 'POST'))
def ticket():
    if request.method == 'POST':
        logger.info('submitting support ticket')
        now = str(datetime.datetime.utcnow())
        ordernumber = request.form['ordernumber']
        email = request.form['email']
        description = request.form['description']
        try:
            logger.info('running test...')
            dowork(ordernumber)
            if messages[ordernumber]:
                response = messages.get(ordernumber, 'Unable to retrieve response')
                logger.info('test passed')
        except:
            logger.info('test failed')
            response = 'Unable to retrieve response'
        if not ordernumber:
            flash('Please complete the form if you wish to submit a ticket.')
        elif not email:
            flash('Please complete the form if you wish to submit a ticket.')
        elif not description:
            flash('Please complete the form if you wish to submit a ticket.')
        #send message to admins
        try:
            logger.info('sending message to admins')
            from_email = "alerts@hdlusa.com"
            from_password = os.getenv('EMAIL_CRED')
            to_emails = ["tbarker@hdlusa.com", "ckirchner@hdlusa.com", "bbeaman@hdlusa.com"]

            # Create the message
            subject = f"[AUTOMATIC] HDL Quotes Support Ticket {now}"

            port = 465

            body = f"""Hello, please find the attached ticket:
            
            Sender Email: {email}
            Affected Order: {ordernumber}
            Description of problem: {description}
            Time Sent: {now}
            ShipperHQ Response: {response}"""




            # Create a MIMEMultipart message
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject

            # Attach the email body

            msg.attach(MIMEText(body, 'plain'))


            # Connect to the SMTP server and send the email
            try:
                server = smtplib.SMTP_SSL("mail.runspot.net", 465)
                server.login(from_email, from_password)
                server.sendmail(from_email, to_emails, msg.as_string())
                server.quit()
                print("Email sent successfully!")
                logger.info('Email sent successfully')
            except Exception as e:
                flash(f"Error submitting ticket, please see admin")
                logger.error(f'Error submitting ticket: {e}')
                full_traceback = traceback.format_exc()
                logger.error(f"Full traceback: {full_traceback}")
        except Exception as e:
            flash(f"Error submitting ticket, please see admin")
            logger.error(f'Error submitting ticket: {e}')
            full_traceback = traceback.format_exc()
            logger.error(f"Full traceback: {full_traceback}")
        #send confirmation to sender
        try:
            logger.info('sending confirmation to sender')
            from_email = "alerts@hdlusa.com"
            from_password = os.getenv('EMAIL_CRED')
            to_emails = [email]

            # Create the message
            subject = f"[AUTOMATIC] HDL Quotes Support Ticket {now}"

            port = 465

            body = f"""Hello, your support ticket has been received, a copy has been provided for your records down below:

            Sender Email: {email}
            Affected Order: {ordernumber}
            Description of problem: {description}
            Time Sent: {now}"""
            logger.info(body)
            # Create a MIMEMultipart message
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject

            # Attach the email body

            msg.attach(MIMEText(body, 'plain'))

            # Connect to the SMTP server and send the email
            try:
                server = smtplib.SMTP_SSL("mail.runspot.net", 465)
                server.login(from_email, from_password)
                server.sendmail(from_email, to_emails, msg.as_string())
                server.quit()
                print("Email sent successfully!")
                logger.info('confirmation sent successfully')
                return redirect(url_for('create'))
            except Exception as e:
                flash(f"Error submitting ticket, please see admin")
                logger.error(f'Error submitting ticket: {e}')
                full_traceback = traceback.format_exc()
                logger.error(f"Full traceback: {full_traceback}")
        except Exception as e:
            flash(f"Error submitting ticket, please see admin")
            logger.error(f'Error submitting ticket: {e}')
            full_traceback = traceback.format_exc()
            logger.error(f"Full traceback: {full_traceback}")
    return render_template('ticket.html')