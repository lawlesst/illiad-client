# -*- coding: utf-8 -*-

from __future__ import unicode_literals
"""
ILLiad account handling.
"""

import logging, pprint, re
import requests
import parsers

#By default SSL verification will be set to false.
#This is likely to be run against a local service where
#trust has already been established.
SSL_VERIFICATION = False


class IlliadSession():

    def __init__(self, url, auth_header, username):
        self.username = username
        self.session_id = None
        self.url = url
        self.auth_header = auth_header
        self.registered = False
        self.blocked_patron = False
        #Requests module doesn't like unicode for header values.
        self.header={self.auth_header: str(self.username)}
        self.cookies = dict(ILLiadSessionID=self.session_id)

    def login(self):
        """
        Logs the user in to Illiad and sets the session id.
        """
        out = {'authenticated': False,
               'session_id': None,
               'new_user': False}
        resp = requests.get(self.url,
                         headers=self.header,
                         verify=SSL_VERIFICATION)
        parsed_login = parsers.main_menu(resp.content)
        out.update(parsed_login)
        self.session_id = parsed_login['session_id']
        self.registered = parsed_login['registered']
        logging.info("ILLiad session %s established for %s.  Registered: %s" %\
                        (self.session_id, self.username, self.registered))
        return out

    def logout(self):
        """
        Logs the user out of the given session.

        The logout process just takes the user back to the login screen.
        We will assume that the logout has been processed after issuing the POST.
        """
        out = {}
        resp = requests.get("%s?SessionID=%s&Action=99" % (self.url, self.session_id),
                            verify=SSL_VERIFICATION)
        logging.info("ILLiad session %s ended for %s." % (self.session_id, self.username))
        out['authenticated'] = False
        return out

    def get_request_key(self, open_url):
        """
        Get the submission key necessary by hitting the Illiad form and
        parsing the input elements.
        """
        submit_key = {'errors': None,
                      'blocked': False}
        ill_url = "%s/OpenURL?%s" % (self.url,
                                     open_url)
        logging.info("ILLiad request form URL %s." % ill_url)
        resp = requests.get(ill_url,
                         headers=self.header,
                         cookies=self.cookies,
                         verify=SSL_VERIFICATION)
        if resp.status_code == 400:
            submit_key['errors'] = True
            submit_key['message'] = 'Invalid request'
        rkey = parsers.request_form(resp.content)
        submit_key.update(rkey)
        if submit_key['blocked']:
            self.blocked_patron = True
        if submit_key['ILLiadForm'] == 'BookChapterRequest':  # check required fields
            submit_key.setdefault( 'PhotoJournalTitle', '(title-not-found)' )  # form label, 'Book Title'
            submit_key.setdefault( 'PhotoJournalInclusivePages', '(pages-not-found)' )  # form label, 'Inclusive Pages'
        return submit_key

    def make_request(self, submit_key):
        """
        Place the request in Illiad.
        """
        #ensure submit_key has proper button value
        submit_key['SubmitButton'] ='Submit Request'
        out = {}
        resp = requests.post(self.url,
                          data=submit_key,
                          headers=self.header,
                          cookies=self.cookies,
                          verify=SSL_VERIFICATION)
        submit_resp = parsers.request_submission(resp.content)
        out.update(submit_resp)
        return out

    def register_user(self, user_dict, **kwargs):
        """
        user_dict contains the required information about the patron.

        Pass in alternate keywords to specify other user attributes,
        e.g: site="Medical Library"

        """
        #pull appropriate user dict variables.  Set some defaults.
        first_name = user_dict.get('first_name', None)
        last_name = user_dict.get('last_name', None)
        email = user_dict.get('email', None)
        #Faculty, staff, student, etct
        status = user_dict.get('status', 'Student')
        address = user_dict.get('address', 'See campus directory')
        phone = user_dict.get('phone', 'N/A')
        reg_key = {}
        reg_key['SessionID'] = self.session_id
        reg_key['ILLiadForm'] = 'ChangeUserInformation'
        reg_key['Username'] = self.username
        reg_key['FirstName'] = first_name
        reg_key['LastName'] = last_name
        reg_key['EMailAddress'] = email
        reg_key['StatusGroup'] = status
        reg_key['Phone'] = phone
        reg_key['Address'] = address
        #defaults
        reg_key['NotifyGroup'] = 'E-Mail'
        reg_key['DeliveryGroup'] = 'Electronic Delivery if Possible'
        reg_key['LoanDeliveryGroup'] = 'Hold for Pickup'
        reg_key['WebDeliveryGroup'] = 'Yes'
        reg_key['Site'] = kwargs.get('site', 'Rockefeller Circ. Desk')
        reg_key['NVTGC'] = 'ILL'
        reg_key['SubmitButton'] = 'Submit Information'
        reg_key['Department'] = kwargs.get('department', 'Other - Unlisted')

        logging.info("Registering %s with ILLiad as %s." % (self.username, status))

        resp = requests.post(self.url,
                          data=reg_key,
                          headers=self.header,
                          cookies=self.cookies,
                          verify=SSL_VERIFICATION)
        out = {}
        #out['meta'] = r.content
        out['status_code'] = resp.status_code
        self.registered = True
        out['status'] = 'Registered'
        return out




