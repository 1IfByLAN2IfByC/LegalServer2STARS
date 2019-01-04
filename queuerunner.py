class QueueRunner(object):
    def __init__(self, collection, log):
        self._col = collection
        self.log = log

    async def add_to_queue(self, newrecords, updatedrecords):
        ''' add records to a queue collection with type and record

            inputs
            ------
                newrecords: list of dicts
                    records to be inserted into STARS

                updatedrecords: list of dict
                    records to be updated into STARS
        '''
        queue = []
        for record in newrecords:
            tmp = {
                'type': 'insert',
                'data': record['LShistory'][-1]['data'],
                'hash': record['lasthash']
            }
            queue.append(tmp)

        for record in updatedrecords:
            tmp = {
                'type': 'update',
                'fields': record['diff']
            }
            queue.append(tmp)
        
        await self._insert_records(queue)
        self.log.debug('{} items added to queue'.format(len(queue)))


    async def _insert_records(self, records):
        ''' insert multiple records into the database

            inputs
            ------
                records: list of dicts
                    records to be inserted
        '''
        try:
            for record in records:
                # not sure why i am having to manually do this
                if '_id' in record:
                    del record['_id']
                await self._col.insert_one(record)
        except:
            pass