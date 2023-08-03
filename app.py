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


def id_generator(size=22, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))




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
    return render_template('create.html')


def dowork(ordernum):

    logger.info('begin pulling local order')
    info = ship.pull(ordernum)
    logger.info('local order pulled')
    logger.info('reaching out to shipperhq api')
    quote = json.loads(ship.ship(info['cart'], info['state'], info['zip'], info['entity']))
    logger.info('response from shipperhq recieved')
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
                response = messages[ordernumber]
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
            from_email = "sales@hdlusa.com"
            from_password = os.getenv('EMAIL_CRED')
            to_emails = ["tbarker@hdlusa.com", "ckirchner@hdlusa.com"]

            # Create the message
            subject = f"[AUTOMATIC] HDL Quotes Support Ticket {now}"

            port = 465

            body = f"""Hello, please find the attached ticket:
            
            Sender Email: {email}
            Affected Order: {ordernumber}
            Description of problem: {description}
            ShipperHQ Response: {response}
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
                logger.info('Email sent successfully')
            except Exception as e:
                flash(f"Error submitting ticket, please see admin")
                logger.error(f'Error submitting ticket: {e}')
        except Exception as e:
            flash(f"Error submitting ticket, please see admin")
            logger.error(f'Error submitting ticket: {e}')
        #send confirmation to sender
        try:
            logger.info('sending confirmation to sender')
            from_email = "sales@hdlusa.com"
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
        except Exception as e:
            flash(f"Error submitting ticket, please see admin")
            logger.error(f'Error submitting ticket: {e}')
    return render_template('ticket.html')