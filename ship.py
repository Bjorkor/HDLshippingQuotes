import pyodbc

import pandas as pd
import requests
import json
from graphqlclient import GraphQLClient
from __main__ import *
from gql import gql, Client
import concurrent.futures




def pull(orderno):
    def query_db(query, conn):
        return pd.read_sql(query, conn)
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
                                  trusted_connection='yes')
            cursor = conn.cursor()
        except pyodbc.Error as ex:
            msg = ex.args[1]
            if re.search('No Kerberos', msg):
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

        # Create ThreadPoolExecutor
        executor = concurrent.futures.ThreadPoolExecutor()

        # Submit tasks to executor
        fut_onhand = executor.submit(query_db, qparts, conn)
        fut_zip = executor.submit(query_db, qzip, conn)
        fut_dimsd = executor.submit(query_db, dimsq, conn)

        try:
            onhand = fut_onhand.result(timeout=30)
        except concurrent.futures.TimeoutError:
            return "TIMEOUT"

        try:
            zip = fut_zip.result(timeout=30)
        except concurrent.futures.TimeoutError:
            return "TIMEOUT"

        try:
            dimsd = fut_dimsd.result(timeout=30)
        except concurrent.futures.TimeoutError:
            return "TIMEOUT"

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
        request = requests.post(url=aurl, json=q)
        answer = json.loads(request.text)
        key = answer['data']['createSecretToken']['token']
        return key

    url = 'https://api.shipperhq.com/v2/graphql'
    headers = {
        'X-ShipperHQ-Secret-Token': f'{auth(entity)}'
    }
    q = {'query': x}
    request = requests.post(url=url, json=q, headers=headers)
    print(request.status_code)
    print(request.text)

    return request.text



