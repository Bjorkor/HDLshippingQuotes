import pyodbc
import pandas as pd
import requests
import json
from graphqlclient import GraphQLClient
from __main__ import *
from gql import gql, Client
import logging
import re
from flask import Flask, render_template, request, url_for, flash, redirect, session
logger = logging.getLogger('quotes_logger')

def pull(orderno):
    print('conferring with the local spirits...')
    # Specifies the ODBC driver, server name, database, etc.
    # We can have this information from the DBA
    driver_name = ''
    driver_names = [x for x in pyodbc.drivers()]
    if driver_names:
        driver_name = driver_names[0]
    if driver_name:
        conn_str = 'DRIVER={}; ...'.format(driver_name)
        # then continue with ...
        # pyodbc.connect(conn_str)
        # ... etc.
        # print(conn_str)
        try:
            conn = pyodbc.connect(driver=driver_name, server="WIN-PBL82ADEL98.HDLUSA.LAN,49816,49816", database="HDL",
                                  trusted_connection='yes', timeout=30)
            cursor = conn.cursor()
        except pyodbc.Error as ex:
            msg = ex.args[1]
            logger.error(f"error occured in connection with local database; TRACEBACK: {msg}")
            if re.search('No Kerberos', msg):
                logger.error("Kerberos check has failed, check kerb.handler.service, or run kinit")
                print('You must login using kinit before using this script.')
                exit(1)
            else:
                raise

        # Creates a cursor from the connection

        # set sql commands as variables
        qparts = """SELECT  * FROM tblSoTransDetail"""
        qzip = """SELECT  * FROM tblSoTransHeader"""
        dimsq = """SELECT  * FROM dbo.tblSHQdims"""

        print('execute query...')
        try:
            # Execute command to pull data for inventory on hand

            # Assigns data retrieved by sql query to a pandas data-frame
            onhand = pd.read_sql(qparts, conn)
            zip = pd.read_sql(qzip, conn)
            dimsd = pd.read_sql(dimsq, conn)

        except pd.io.sql.DatabaseError as e:
            flash("An error occurred while trying to contact internal database. Please notify an administrator.")
            logger.error(f"An error occurred while trying to execute the SQL queries: {e}")
        except Exception as e:
            flash("An unexpected error has occurred. Please notify an administrator.")
            logger.error(f"An unexpected error occurred: {e}")
        # print(dimsd)
        # dimsd.to_csv('dipstick.csv')
        dimsd.rename(
            columns={"SKU": "sku", "WEIGHT": "weight", "LENGTH": "length", "WIDTH": "width", "HEIGHT": "height", "SHIPPINGGROUP": 'group'},
            inplace=True)
        #dimsd.to_csv('a;osdhnflahkj.csv')
        # dims = pd.read_excel('fdb.xls')
        #orderno = '14619388'

        onhand = onhand[onhand['TransID'] == orderno]
        onhand = onhand[['TransID', 'ItemId', 'QtyOrdSell']]
        zip = zip[['TransId', 'ShipToRegion', 'ShipToPostalCode']]
        zip.rename(columns={"TransId": "TransID"}, inplace=True)
        zip = zip[zip['TransID'] == orderno]
        cart = onhand[['ItemId', 'QtyOrdSell']]
        cart = cart.rename(columns={"ItemId": "sku", "QtyOrdSell": "qty"})
        dimsd['sku'] = dimsd['sku'].astype('str')
        cart.sku = cart.sku.astype(str, copy=False)
        # dimsd.sku = dimsd.sku.astype(str, copy=False)
        cart.reset_index(drop=True)
        dimsd.reset_index(drop=True)
        dimsd['sku'] = dimsd['sku'].apply(lambda x: x.strip())
        dimsd['weight'] = dimsd['weight'].apply(lambda x: x.strip())
        dimsd['length'] = dimsd['length'].apply(lambda x: x.strip())
        dimsd['width'] = dimsd['width'].apply(lambda x: x.strip())
        dimsd['height'] = dimsd['height'].apply(lambda x: x.strip())
        #dimsd['group'] = dimsd['group'].apply(lambda x: x.strip())

        final = cart.merge(right=dimsd, on='sku', how='left')
        print(final)
        final[['length', 'width', 'height', 'weight', 'group']] = final[['length', 'width', 'height', 'weight', 'group']].fillna(value=0)

        final = final.to_json(orient="records")
        final = json.loads(final)

        postcode = zip['ShipToPostalCode']

        postcode = postcode.to_string(index=False)

        statea = zip['ShipToRegion']
        statea = statea.to_string(index=False)
        if orderno.startswith('1'):
            entity = 'hdl'
        if orderno.startswith('2'):
            entity = 'ww'
        d = dict()
        d['cart'] = final
        d['state'] = statea
        d['zip'] = postcode
        d['entity'] = entity
        return d


def ship(cart, state, zip, entity):
    if len(zip) > 5:
        trimzip = str(zip)[:5]
    else:
        trimzip = zip


    print('conferring with the remote spirits...')
    client = GraphQLClient('https://api.shipperhq.com/v2/graphql')
    client.inject_token(
        'eyJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE2NjE0NTU0NDIsImV4cCI6MTY2NDA0NzQ0MiwiYXBpX2tleSI6ImYyMWViZjc1ZTU1Nzc0YWUyNGEyNzNhZWFiZmJiMjNjIiwicHVibGljX3Rva2VuIjoiOTY2YzQzMDZiNGU5NzQwNTkyNzUxMTUyNzA1MmYzZWQifQ.SX1_TMt-a11qZPYA5CDEHCvz4nEcZKV5KjiROWMXgfM',
        'X-ShipperHQ-Secret-Token')
    headers = {
        'X-ShipperHQ-Secret-Token': 'eyJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE2NjE0NTU0NDIsImV4cCI6MTY2NDA0NzQ0MiwiYXBpX2tleSI6ImYyMWViZjc1ZTU1Nzc0YWUyNGEyNzNhZWFiZmJiMjNjIiwicHVibGljX3Rva2VuIjoiOTY2YzQzMDZiNGU5NzQwNTkyNzUxMTUyNzA1MmYzZWQifQ.SX1_TMt-a11qZPYA5CDEHCvz4nEcZKV5KjiROWMXgfM'
    }
    # Provide a GraphQL query

    list = []


    for x in cart:

        sku = x['sku']
        qty = int(x['qty'])
        # t = item.objects.get(sku__startswith=sku)
        length = x['length']
        width = x['width']
        height = x['height']
        weight = x['weight']
        weight = "{:.2f}".format(weight)
        group = x['group']

        if str(sku).startswith('X') or str(sku).startswith('Y'):
            pass
        if isinstance(group, int):
            uhh = '''{
                        sku:"''' + sku + '''"
                        qty:''' + str(qty) + '''
                        type:SIMPLE
                        weight:''' + str(weight) + '''
                        attributes : [
                          {
                          name : "ship_width",
                          value : "''' + str(width) + '''"
                        }, {
                          name : "ship_length",
                          value : "''' + str(length) + '''"
                        }, {
                          name : "ship_height",
                          value : "''' + str(height) + '''"
                        }
                            ],
                    }'''
        if isinstance(group, str):
            group = group.strip()


            uhh = '''{
                        sku:"''' + sku + '''"
                        qty:''' + str(qty) + '''
                        type:SIMPLE
                        weight:''' + str(weight) + '''
                        attributes : [
                        {
                          name : "shipperhq_shipping_group",
                          value : "''' + str(group) + '''"
                        }, {
                          name : "ship_width",
                          value : "''' + str(width) + '''"
                        }, {
                          name : "ship_length",
                          value : "''' + str(length) + '''"
                        }, {
                          name : "ship_height",
                          value : "''' + str(height) + '''"
                        }
                            ],
                    }'''
        else:
            uhh = '''{
                        sku:"''' + sku + '''"
                        qty:''' + str(qty) + '''
                        type:SIMPLE
                        weight:''' + str(weight) + '''
                        attributes : [
                          {
                          name : "ship_width",
                          value : "''' + str(width) + '''"
                        }, {
                          name : "ship_length",
                          value : "''' + str(length) + '''"
                        }, {
                          name : "ship_height",
                          value : "''' + str(height) + '''"
                        }
                            ],
                    }'''
        list.append(uhh)
    insert = ''
    count = 0
    for x in list:
        if count == 0:
            insert = str(x)
            count += 1
        else:
            insert = insert + ',' + str(x)
    query = '''query retrieveShippingQuote {
                   retrieveShippingQuote(ratingInfo: {
                    cart: {
                      items: [''' + f'{insert}' + '''
                    ]
                    },
                    destination: {
                        country: "US"
                        region: "''' + state + '''"

                        zipcode: "''' + str(trimzip) + '''"

                     },
                    siteDetails: {
                        appVersion: "1.0.0",
                        ecommerceCart: "HDL Shipping Quote",
                        ecommerceVersion: "1.0.0",
                        websiteUrl: "www.hdlusa.com",
                        ipAddress: "0.0.0.0"
                        }
                  }) {
                    transactionId
                    carriers {
                      carrierCode
                      carrierTitle
                      carrierType
                      error {
                        errorCode
                        internalErrorMessage
                        externalErrorMessage
                        priority
                      }

                      shippingRates {
                        code
                        title
                        totalCharges
                      }
                    }
                    errors {
                      errorCode
                      internalErrorMessage
                      externalErrorMessage
                      priority
                    }
                  }
                }'''

    print(query)
    # Execute the query on the transport
    # result = json.loads(client.execute(query))
    # print(query)
    answer = reqtest(query, entity)
    print('we are blessed...')
    return answer


# quote = ship(final, statea, postcode)
def reqtest(x, entity):
    def auth(aentity):
        aurl = 'https://rms.shipperhq.com'

        if aentity == 'ww':
            package = '''
            mutation CreateSecretToken {
                createSecretToken(
                    api_key: "90516ed417297acac50cb8a3efde8a96",
                    auth_code: "9337fe6ba4e8d3488f0ceb599f3957d6abb5cdf66c3bfa48e8"
                    )
                    {
                    token
                    }
            }'''
        if aentity == 'hdl':
            package = '''
            mutation CreateSecretToken {
                createSecretToken(
                    api_key: "f21ebf75e55774ae24a273aeabfbb23c",
                    auth_code: "38fc75bd58aa341d7747ed7d3b78c55ca877df83a23a08f749"
                    )
                    {
                    token
                    }
            }'''


        q = {'query': package}
        logger.info("Requesting AUTH token from ShipperHQ...")
        try:
            request = requests.post(url=aurl, json=q)
            answer = json.loads(request.text)
            key = answer['data']['createSecretToken']['token']
            logger.info("AUTH token received!")
            return key
        except Exception as e:
            flash("An error occurred while contacting ShipperHQ, please try again in a few moments.")
            logger.error(f"An error occurred while requesting AUTH token from ShipperHQ: {e}")
    url = 'https://api.shipperhq.com/v2/graphql'
    headers = {
        'X-ShipperHQ-Secret-Token': f'{auth(entity)}'
    }
    q = {'query': x}
    try:
        logger.info("Requesting Quote from ShipperHQ...")
        request = requests.post(url=url, json=q, headers=headers)
        logger.info("Quote Received")
    except Exception as e:
        flash("An error occurred while contacting ShipperHQ, please try again in a few moments.")
        logger.error(f"An error occurred while requesting Quote from ShipperHQ: {e}")


    return request.text



