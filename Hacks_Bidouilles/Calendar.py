from typing import Dict, List

import httplib2
import os

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import datetime


class Calendar:
    SCOPES : Dict[str, str] = {
        'r' : 'https://www.googleapis.com/auth/calendar.readonly', 
        'w' : 'https://www.googleapis.com/auth/calendar'
    }


    def __init__(self, application_name : str, name : str='primary', client_secret_file : str ='client_secret.json', scope : str='r', verbose : bool = False): 
        if scope in Calendar.SCOPES:
            self.scope = Calendar.SCOPES[scope]
        else:
            print(f'Error : scope "{scope}" is not a valid scope (choose "r" or "w") !')
            exit(1)

        self.verbose=verbose
        self.credentials = Calendar.getCredentials(application_name, client_secret_file, scope, self.verbose)
        self.http = self.credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=self.http)
        self.events = None

        self.name = self.getIdFromName(name)


    @staticmethod
    def getCredentials(application_name : str, client_secret_file : str, permissions : str, verbose : bool = False) -> client.OAuth2Credentials:
        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(home_dir, '.anonymization')
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir, f'credential_{permissions}.json')

        store = Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            flow = client.flow_from_clientsecrets(client_secret_file, Calendar.SCOPES[permissions])
            flow.user_agent = application_name
            credentials = tools.run_flow(flow, store)
            if verbose:
                print(f'Storing credentials to {credential_path}')
        else:
            if verbose:
                print(f'Log : Credentials readed from {credential_path}')
        return credentials


    def getIdFromName(self, name : str) -> None:
        page_token = None
        while True:
            calendar_list = self.service.calendarList().list(pageToken=page_token).execute()
            for calendar_list_entry in calendar_list['items']:
                if calendar_list_entry['summary'] == name:
                    return calendar_list_entry['id']
            page_token = calendar_list.get('nextPageToken')
            if not page_token:
                break
        # Si on arrive ici : erreur pas d'id associé à name
        print(f'Error : Calendar "{name}" not found')
        exit(2)


    def getFutureEvents(self) -> bool:
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        eventsResult = self.service.events().list(
            calendarId=self.name, timeMin=now, singleEvents=True,
            orderBy='startTime').execute()
        self.events = eventsResult.get('items', [])

        # return bool(self.events) pour ^etre plus concis
        if not self.events:
            return False
        else:
            return True


    @staticmethod
    def cmpEvent(evt_1 : Dict[str, str], evt_2 : Dict[str, str]) -> bool:
        return evt_1['start']['dateTime'] == evt_2['start']['dateTime'] and evt_1['end']['dateTime'] == evt_2['end']['dateTime']


    def isEventInCalendar(self, evt : Dict[str, str]) -> bool:
        evt_date = datetime.datetime.strptime(evt['start']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
        for src_evt in self.events:
            if Calendar.cmpEvent(src_evt, evt):
                return True
            else:
                src_evt_date = datetime.datetime.strptime(src_evt['start']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                if src_evt_date > evt_date:
                    return False
        return False


    @staticmethod
    def anonymize(evt : Dict[str, str], share : List=None, generic_summary : str=None) -> Dict[str, str]:
        new_evt = {}
        if share == None or 'summary' not in share:
            new_evt['summary'] = generic_summary
        if 'location' in share:
            new_evt['location'] = evt['location']
        else:
            new_evt['description'] = evt['description']
        new_evt['start'] = {}
        new_evt['start']['dateTime'] = evt['start']['dateTime']
        new_evt['end'] = {}
        new_evt['end']['dateTime'] = evt['end']['dateTime']
        return new_evt


    def insertEvent(self, evt : Dict[str, str], share : List=None, generic_summary : str=None) -> None:
        copy_evt = Calendar.anonymize(evt, share, generic_summary)
        if self.verbose:
            print('---')
            print('Insert !')
            print(copy_evt)
        self.service.events().insert(calendarId=self.name, body=copy_evt).execute()


    def deleteEvent(self, evt : Dict[str, str]) -> None:
        if self.verbose:
            print('---')
            print('Delete !')
            print(evt)
        self.service.events().delete(calendarId=self.name, eventId=evt['id']).execute()


    @staticmethod
    def copyEvents(source : 'Calendar', target : 'Calendar', share : List=None, generic_summary : str=None) -> None:
        for evt in source.events:
            if not target.isEventInCalendar(evt):
                target.insertEvent(evt, share, generic_summary)

        for evt in target.events:
            if not source.isEventInCalendar(evt):
                target.deleteEvent(evt)


    @staticmethod
    def anonymizeCalendar(application_name : str, source_name : str, target_name : str, share : List=None, generic_summary : str=None, client_secret_file : str ='client_secret.json', verbose : bool =False) -> None:
        source = Calendar(application_name, source_name, scope='r', verbose=verbose)
        source.getFutureEvents()

        target = Calendar(application_name, target_name, scope='w', verbose=verbose)
        target.getFutureEvents()
    
        Calendar.copyEvents(source, target, share, generic_summary)
