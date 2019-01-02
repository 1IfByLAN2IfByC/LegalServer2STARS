import tornado.ioloop
import tornado.web
import tornado.auth
from tornado import autoreload
from datetime import datetime
import motor
import json
import os
import pprint

from lsclient import LSClient


class IndexHandler(tornado.web.RequestHandler):
    async def get(self):
        if self.get_current_user():
            print(self.get_current_user())
            self.redirect("/home")
        
        else:
            self.render('index.html', admin=False)


class Uploader(object):
    def __init__(self, lsclient):
        self.lsclient = lsclient
        pass

    def _check_new_LS(self):
        '''
        connect to LS, check for new requests

        returns
        -------
            newLSreports: list of dicts
                list of json-style reports that are new or updated
        '''
    
        newLSreports = self.lsclient.check_new()
        if not newLSreports: # there are no new files
            return None

        else: # no 

