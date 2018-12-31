import json
import logging
import logging.config


class STARSException(Exception):
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
        
        startechspec: string
            file location of the STAR tech spec YAML. Used
            to typecheck and validate input
        
        log: logging handler
    '''
    
    def __init__(self, apikey, auth, startechspec, log):
        self.apikey = apikey
        self.auth = auth
        self.startechspec = startechspec
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

    def upload_to_STARS(self, lsdata):
        '''
        do we need to upload as a list or as indivual items? 
        
        inputs:
        -------
            lsdata: list of dicts
                scrubbed Legal Server data of new cases to upload
        '''
        
        for row in lsdata:
            try:
                self._validate_input(row)
            except STARSException as e:
                self.log.error('Legal Server data is invalid', e)
            
        
    