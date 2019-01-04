import json
import logging
import logging.config
from hashlib import sha224
from jsonrpcclient.clients.http_client import HTTPClient
from jsonrpcclient.exceptions import ErrorResponse, ReceivedErrorResponseError
import jsonrpcclient as jsonrpc

class STARSException(Exception):
    pass


class STARSAPIKeyInvalid(Exception):
    # to be raised when the token is invalid
    pass


class STARSClient(object):
    '''
    Client for connecting to the STAR database and uploading scrubbed Legal Server 
    reports.
    
    inputs:
    -------
        apikey: str
            url of the STARS api 
        
        auth: tuple of strings
            (username, password) for STARS
            
        secret: str
            client secret key
        
        startechspec: str
            file location of the STAR tech spec YAML. Used
            to typecheck and validate input
        
        permstore: str
            file location where record confirmation should be stored
            
        log: logging handler
    '''
    
    def __init__(self, apikey, clientid, secret, startechspec, permstore, log):
        self.apikey = apikey
        self.clientid = clientid
        self.secret = secret
        self.startechspec = startechspec
        self.permstore = permstore
        self.log = log
    
        self._load_tech_spec()
        
    def _typemapping(self):
        '''generate type map. removed for claritys sake '''
        self.typemap = {
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict,
            'string': str
        }
        
    def _load_tech_spec(self):
        try:
            with open(self.startechspec, 'r') as f:
                self.startechspec = yaml.load(f)
        except OSError:
            self.log.error('No tech spec file found. Address given: {}'.format(
                self.startechspec))
     
    def _validate_input(self, lsdata):
        '''
        validate the type of each row against the STAR tech spec
        
        inputs:
        -------
            lsdata: dict
                individual row in the report to be validated
        '''

        for key, value in lsdata.itmes():   
            try:
                validate = self.startechspec['definitions']['SHIP_Beneficiary_Data']['properties'][key]['type'] 
                if validate != value:
                    self.log.error('Reformatted data has does not match TYPE in tech spec. Value: {}'.format(value))
                    raise STARSException('Reformatted data has does not match TYPE in tech spec. Value: {}'.format(value))

            except KeyError:
                self.log.error('Reformatted data has key not in tech spec. Key: {}'.format(key))
                raise STARSException('Reformatted data has key not in tech spec. Key: {}'.format(key))
    
    def _request_key(self):
        # from API Authentication doc
        apipath = '/auth/oauth/token?grant_type=client_credentials'
        key = self.clientid + ":"+ self.secret
        header = {"Authorization" : "Basic Base64Encoded("+ key + ")"}
        request = {"grant_type": "client_credentials"}

        client = HTTPClient(apipath)
        client.session.headers.update(header)
    
        # response body will be new client token
        response = client.request(request)
        self.token = response.data.result
        
        # update the record update session
        self._configure_session()
        
    def _configure_session(self):
        if self.token:
            self.client = HTTPClient(self.apikey)
            # self.client.session.auth = self.token
            self.client.headers.update('"Authorization" : "Bearer "'+ 
            access_token + '"')
        else:
            self._request_key()
            self._configure_session()
            
    def _confirmation_record(self, record):
        ''' store confirmation receipt as received by STARS'''
        
        try:
            with open(self.permstore, 'a') as f:
                f.write('{}\n'.format(record))
                
        except OSError:
            self.log.debug('STARS storage not found. Creating file at {}'.format(self.permstore))
            
            with open(self.permstore, 'w+') as f:
                pass
            
            self._confirmation_record(record)
    
    def _stars_post(self, body):
        '''
        format post based on header format per ACL API Authentication
        
        inputs
        ------
            body: dict
                body of post
        '''
        
        try:
            response = self.client.request(body)
            
            if response.data.ok:
                # message was sent correctly
                # send up to save 
                return response.data
            
        except rq.ConnectionError:
            # server refused the connection
            self.log.error('Could not connect to STARS server')
            raise STARSException('Could not connect to STARS server')
            
        except jsonrpc.exceptions.ReceivedNon2xxResponseError as e:
            errorcode = int(''.join(x for x in str(e) if x.isdigit()))
            if errorcode == 401:
                # token is old. request new one
                self._request_key()
                # try again
                self._stars_post(body)

    def upload_to_STARS(self, lsdata):
        '''
        wrapper for uploading a list of records to STARS. 
        inputs:
        -------
            lsdata: list of dicts
                scrubbed Legal Server data of new cases to upload
        '''
        for row in lsdata:
            try:
                self._validate_input(row)
            except STARSException as e:
                self.log.error('Legal Server data is not in accordance w/ tech spec: RECORD ID: {}'.format(
                    row['id'], e))
                
            # upload to STARS
            confirm = self._stars_post(row)
            
            # TODO: parse the RPC response to get some type of record
            self._confirmation_record(confirm)    

                               