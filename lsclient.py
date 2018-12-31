import requests as rq
import json
import xmltodict as xml
import logging
import logging.config


class LSClient(object):
    def __init__(self, apikey, auth, permstore, log):
        
        '''
        inputs:
        -------
            apikey: string
                url corresponding to the report XML API
            
            auth: tuple of strings
                (username, password) for http authentication
                
            permstore: string
                filelocation where the uploaded ids can be stored 
                persistently in case of shutdown
            
            log: logging log
                log to store runs and id updates
            
        parameters:
        -----------
            reportids: list of ints
                all the report IDs that have already been uploaded
                
            toupload: list of dicts
                row object returned by requests that are not in reportids
                (i.e. the need to be uploaded)      
        '''
        
        self.apikey = apikey
        self.auth = auth
        self.permstore = permstore
        self.log = log
    
        self.reportids = []
        self.toupload = []
    
    def _id_check(self):
        '''open the file where the permstore is and check if it is empty'''
        
        try:
            with open(self.permstore, 'r') as f:
                tmp = f.readlines()

            self.reportids = [int(line) for line in tmp]
        except OSError:
            self.log.debug('File Not Found Error. Creating file at {}'.format(self.permstore))
            
            with open(self.permstore, 'w+') as f:
                pass
 
    def _pull_report(self):
        '''
        pull the report using requesets. authentication handled using http auth
        '''
        # pull
        self.log.debug('Attempting to make request')
        datareturn = rq.get(self.apikey, auth=(self.auth[0], self.auth[1]))
        
        # check datareturn error codes
        if datareturn.status_code != 200:
            self.log.debug('Bad request. Error code: {}'.format(datareturn.status_code))
            # raise some error
            raise ValueError
            
        else:
            self.log.debug('Request made successfully')
            # reconfigure the data to a nice format
            datareturn = json.dumps(xml.parse(datareturn.text))
            datareturn = json.loads(datareturn)
            if isinstance(datareturn['report']['row'], dict):
                # only a single record was found, transfrom to list
                datareturn['report']['row'] = [datareturn['report']['row']]
            for row in datareturn['report']['row']:
                if int(row['id']) not in self.reportids:
                    # append to list of completed ids
                    self.reportids.append(int(row['id']))
                    self.toupload.append(row)
                    self.log.info('New case: {}'.format(row['id']))
            
            self.log.info(
                '\n --------------------------------------------- \n \
                Found {n} new values to be uploaded \n \
                ---------------------------------------------'.format(n=len(self.toupload)))
            
            with open(self.permstore, 'a') as f:
                for line in self.reportids:
                    f.write(str(line))
            
            self.log.debug('Permanet storage updated')