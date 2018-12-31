import json
import logging
import logging.config

class TLSCRequestScrubber(object):
    def __init__(self, keymapping, errorfile, log):
        self.keyfile = keymapping
        self.log = log
        self.errorfile = errorfile
        
        self._get_mapping()
        
    def _get_mapping(self):
        try:
            with open(self.keyfile, 'r') as f:
                self.keymap = json.loads(f)
        except OSError:
            self.log.error('No key file found at: {}'.format(self.keyfile))
        
    def request_mapper(self, request):
        '''
        map the request objects onto the key values given by the map file
        
        inputs:
        -------
            request: list of dicts
                list of request objects
        '''
        
        reformatted = []
        errors = []
        
        for row in reqeuest:
            stardata = {}
            for k in row.keys():
                try:
                    stardata[self.keymap[row[k]]['starkey']] =  self.keymap[row[k]['starvalue']]
                    reformatted.append(stardata)
                except KeyError:
                    self.log.error('Key pulled from TLSC database not found. Key: {}'.format(
                        k))
                    errors.append(row)
                    
        if len(errors) != 0:            
            with open(self.errorfile, 'a') as f:
                json.dump(errors, f)
            
        self.log.info('{} matters reformatted'.format(len(reformatted)))
        self.log.info('{n} matters had errors. View them here: {e}'.format(
            n=len(errors), e=self.errorfile))
        
        return reformatted

