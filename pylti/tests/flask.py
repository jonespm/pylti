# -*- coding: utf-8 -*-
"""
Test pylti/flask.py module
"""
from __future__ import absolute_import
import unittest
from pylti.common import LTIException, LTI_SESSION_KEY, LTIOAuthDataStore
from pylti.flask import lti
from flask import Flask, session, request
import httpretty

app = Flask(__name__)

state = dict()


def error(exception):
    state['exception'] = exception
    return "error"


@app.route("/unknown_protection")
@lti(error=error, app=app)
def unknown_protection(self):
    return "hi" #pragma: no cover


@app.route("/any")
@lti(error=error, request='any', app=app)
def any_route(lti):
    return "hi"


@app.route("/session")
@lti(error=error, request='session', app=app)
def session_route(lti):
    return "hi"


@app.route("/initial", methods=['GET', 'POST'])
@lti(error=error, request='initial', app=app)
def initial_route(lti):
    return "hi"


@app.route("/setup_session")
def setup_session():
    session[LTI_SESSION_KEY] = True
    session['oauth_consumer_key'] = '__consumer_key__'
    return "session set"


@app.route("/close_session")
@lti(error=error, request='session', app=app)
def logout_route(lti):
    lti.close_session()
    return "session closed"


@app.route("/post_grade/<float:grade>")
@lti(error=error, request='session', app=app)
def post_grade(grade, lti):
    ret = lti.post_grade(grade)
    return "grade={}".format(ret)


class TestFlask(unittest.TestCase):
    consumers = {
        "__consumer_key__": {"secret": "__lti_secret__"}
    }


    def setUp(self):
        app.config['TESTING'] = True
        app.config['SERVER_NAME'] = 'localhost'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'you-will-never-guess'
        app.config['PYLTI_CONFIG'] = {'consumers': self.consumers}
        app.config['PYLTI_URL_FIX'] = {
            "https://localhost:8000/": {
                "https://localhost:8000/": "http://localhost:8000/"
            }
        }
        self.app = app.test_client()


    def reset_exception(self):
        if state.has_key('exception'):
            del state['exception']
        self.assertFalse(state.has_key('exception'))


    def get_exception(self):
        return state['exception']['exception']


    def has_exception(self):
        return state.has_key('exception') and state['exception'].has_key('exception')


    def get_exception_as_string(self):
        return "{}".format(self.get_exception())

    def test_access_to_oauth_resource_unknown_protection(self):
        self.reset_exception()
        ret = self.app.get('/unknown_protection')
        self.assertTrue(self.has_exception())
        self.assertIsInstance(self.get_exception(), LTIException)
        self.assertEqual(self.get_exception_as_string(), 'Unknown request type')

    def test_access_to_oauth_resource_without_authorization_any(self):
        self.reset_exception()
        ret = self.app.get('/any')
        self.assertTrue(self.has_exception())
        self.assertIsInstance(self.get_exception(), LTIException)
        self.assertEqual(self.get_exception_as_string(), 'This page requires a valid oauth session or request')

    def test_access_to_oauth_resource_without_authorization_session(self):
        self.reset_exception()
        ret = self.app.get('/session')
        self.assertTrue(self.has_exception())
        self.assertIsInstance(self.get_exception(), LTIException)
        self.assertEqual(self.get_exception_as_string(), 'Session expired or unavailable')

    def test_access_to_oauth_resource_without_authorization_initial_get(self):
        self.reset_exception()
        ret = self.app.get('/initial')
        self.assertTrue(self.has_exception())
        self.assertIsInstance(self.get_exception(), LTIException)
        self.assertEqual(self.get_exception_as_string(), 'This page requires a valid oauth session or request')

    def test_access_to_oauth_resource_without_authorization_initial_post(self):
        self.reset_exception()
        ret = self.app.post('/initial')
        self.assertTrue(self.has_exception())
        self.assertIsInstance(self.get_exception(), LTIException)
        self.assertEqual(self.get_exception_as_string(), 'This page requires a valid oauth session or request')


    def test_access_to_oauth_resource_in_session(self):
        self.reset_exception()
        ret = self.app.get('/setup_session')
        ret = self.app.get('/session')
        self.assertFalse(self.has_exception())

    def test_access_to_oauth_resource_in_session_with_close(self):
        self.reset_exception()
        self.app.get('/setup_session')
        self.app.get('/session')
        self.assertFalse(self.has_exception())
        self.app.get('/close_session')
        self.app.get('/session')
        self.assertTrue(self.has_exception())

    def test_access_to_oauth_resource(self):
        self.reset_exception()
        consumers = self.consumers
        url = 'http://localhost/initial?'
        method = 'GET'
        headers = dict()
        params = {'resource_link_id': u'edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8',
                  'user_id': u'008437924c9852377e8994829aaac7a1',
                  'roles': u'Instructor',
                  'lis_result_sourcedid': u'MITx/ODL_ENG/2014_T1:edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8:008437924c9852377e8994829aaac7a1',
                  'context_id': u'MITx/ODL_ENG/2014_T1',
                  'lti_version': u'LTI-1p0',
                  'launch_presentation_return_url': u'',
                  'lis_outcome_service_url': u'https://edge.edx.org/courses/MITx/ODL_ENG/2014_T1/xblock/i4x:;_;_MITx;_ODL_ENG;_lti;_94173d3e79d145fd8ec2e83f15836ac8/handler_noauth/grade_handler',
                  'lti_message_type': u'basic-lti-launch-request',
        }
        store = LTIOAuthDataStore(consumers)
        import urllib

        urlparams = urllib.urlencode(params)
        import oauthlib.oauth1

        client = oauthlib.oauth1.Client('__consumer_key__', client_secret='__lti_secret__',
                                        signature_method=oauthlib.oauth1.SIGNATURE_HMAC,
                                        signature_type=oauthlib.oauth1.SIGNATURE_TYPE_QUERY)
        signature = client.sign("{}{}".format(url, urlparams))
        print signature[0]
        signed_url = signature[0]
        new_url = signed_url[len('http://localhost'):]
        ret = self.app.get(new_url)
        self.assertFalse(self.has_exception())

    def test_access_to_oauth_resource_any(self):
        self.reset_exception()
        consumers = self.consumers
        url = 'http://localhost/any?'
        method = 'GET'
        headers = dict()
        params = {'resource_link_id': u'edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8',
                  'user_id': u'008437924c9852377e8994829aaac7a1',
                  'roles': u'Instructor',
                  'lis_result_sourcedid': u'MITx/ODL_ENG/2014_T1:edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8:008437924c9852377e8994829aaac7a1',
                  'context_id': u'MITx/ODL_ENG/2014_T1',
                  'lti_version': u'LTI-1p0',
                  'launch_presentation_return_url': u'',
                  'lis_outcome_service_url': u'https://edge.edx.org/courses/MITx/ODL_ENG/2014_T1/xblock/i4x:;_;_MITx;_ODL_ENG;_lti;_94173d3e79d145fd8ec2e83f15836ac8/handler_noauth/grade_handler',
                  'lti_message_type': u'basic-lti-launch-request',
        }
        store = LTIOAuthDataStore(consumers)
        import urllib

        urlparams = urllib.urlencode(params)
        import oauthlib.oauth1

        client = oauthlib.oauth1.Client('__consumer_key__', client_secret='__lti_secret__',
                                        signature_method=oauthlib.oauth1.SIGNATURE_HMAC,
                                        signature_type=oauthlib.oauth1.SIGNATURE_TYPE_QUERY)
        signature = client.sign("{}{}".format(url, urlparams))
        print signature[0]
        signed_url = signature[0]
        new_url = signed_url[len('http://localhost'):]
        ret = self.app.get(new_url)
        self.assertFalse(self.has_exception())


    def test_access_to_oauth_resource_invalid(self):
        self.reset_exception()
        consumers = self.consumers
        url = 'http://localhost/initial?'
        method = 'GET'
        headers = dict()
        params = {'resource_link_id': u'edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8',
                  'user_id': u'008437924c9852377e8994829aaac7a1',
                  'roles': u'Instructor',
                  'lis_result_sourcedid': u'MITx/ODL_ENG/2014_T1:edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8:008437924c9852377e8994829aaac7a1',
                  'context_id': u'MITx/ODL_ENG/2014_T1',
                  'lti_version': u'LTI-1p0',
                  'launch_presentation_return_url': u'',
                  'lis_outcome_service_url': u'https://edge.edx.org/courses/MITx/ODL_ENG/2014_T1/xblock/i4x:;_;_MITx;_ODL_ENG;_lti;_94173d3e79d145fd8ec2e83f15836ac8/handler_noauth/grade_handler',
                  'lti_message_type': u'basic-lti-launch-request',
        }
        store = LTIOAuthDataStore(consumers)
        import urllib

        urlparams = urllib.urlencode(params)
        import oauthlib.oauth1

        client = oauthlib.oauth1.Client('__consumer_key__', client_secret='__lti_secret__',
                                        signature_method=oauthlib.oauth1.SIGNATURE_HMAC,
                                        signature_type=oauthlib.oauth1.SIGNATURE_TYPE_QUERY)
        signature = client.sign("{}{}".format(url, urlparams))
        print signature[0]
        signed_url = signature[0]
        new_url = signed_url[len('http://localhost'):]
        ret = self.app.get("{}&FAIL=TRUE".format(new_url))
        self.assertTrue(self.has_exception())
        self.assertIsInstance(self.get_exception(), LTIException)
        self.assertEqual(self.get_exception_as_string(), 'OAuth error: Please check your key and secret')


    def test_access_to_oauth_resource_invalid_after_session_setup(self):
        self.reset_exception()
        self.app.get('/setup_session')
        self.app.get('/session')
        self.assertFalse(self.has_exception())

        consumers = self.consumers
        url = 'http://localhost/initial?'
        method = 'GET'
        headers = dict()
        params = {'resource_link_id': u'edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8',
                  'user_id': u'008437924c9852377e8994829aaac7a1',
                  'roles': u'Instructor',
                  'lis_result_sourcedid': u'MITx/ODL_ENG/2014_T1:edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8:008437924c9852377e8994829aaac7a1',
                  'context_id': u'MITx/ODL_ENG/2014_T1',
                  'lti_version': u'LTI-1p0',
                  'launch_presentation_return_url': u'',
                  'lis_outcome_service_url': u'https://edge.edx.org/courses/MITx/ODL_ENG/2014_T1/xblock/i4x:;_;_MITx;_ODL_ENG;_lti;_94173d3e79d145fd8ec2e83f15836ac8/handler_noauth/grade_handler',
                  'lti_message_type': u'basic-lti-launch-request',
        }
        store = LTIOAuthDataStore(consumers)
        import urllib

        urlparams = urllib.urlencode(params)
        import oauthlib.oauth1

        client = oauthlib.oauth1.Client('__consumer_key__', client_secret='__lti_secret__',
                                        signature_method=oauthlib.oauth1.SIGNATURE_HMAC,
                                        signature_type=oauthlib.oauth1.SIGNATURE_TYPE_QUERY)
        signature = client.sign("{}{}".format(url, urlparams))
        print signature[0]
        signed_url = signature[0]
        new_url = signed_url[len('http://localhost'):]
        ret = self.app.get("{}&FAIL=TRUE".format(new_url))
        self.assertTrue(self.has_exception())
        self.assertIsInstance(self.get_exception(), LTIException)
        self.assertEqual(self.get_exception_as_string(), 'OAuth error: Please check your key and secret')

    @httpretty.activate
    def test_access_to_oauth_resource_post_grade(self):
        uri = 'https://edge.edx.org/courses/MITx/ODL_ENG/2014_T1/xblock/i4x:;_;_MITx;_ODL_ENG;_lti;_94173d3e79d145fd8ec2e83f15836ac8/handler_noauth/grade_handler'

        def request_callback(request, uri, headers):
            return (200, headers, "success")

        httpretty.register_uri(httpretty.POST, uri, body=request_callback)

        self.reset_exception()
        consumers = self.consumers
        url = 'http://localhost/initial?'
        method = 'GET'
        headers = dict()
        params = {'resource_link_id': u'edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8',
                  'user_id': u'008437924c9852377e8994829aaac7a1',
                  'roles': u'Instructor',
                  'lis_result_sourcedid': u'MITx/ODL_ENG/2014_T1:edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8:008437924c9852377e8994829aaac7a1',
                  'context_id': u'MITx/ODL_ENG/2014_T1',
                  'lti_version': u'LTI-1p0',
                  'launch_presentation_return_url': u'',
                  'lis_outcome_service_url': u'https://edge.edx.org/courses/MITx/ODL_ENG/2014_T1/xblock/i4x:;_;_MITx;_ODL_ENG;_lti;_94173d3e79d145fd8ec2e83f15836ac8/handler_noauth/grade_handler',
                  'lti_message_type': u'basic-lti-launch-request',
        }
        store = LTIOAuthDataStore(consumers)
        import urllib

        urlparams = urllib.urlencode(params)
        import oauthlib.oauth1

        client = oauthlib.oauth1.Client('__consumer_key__', client_secret='__lti_secret__',
                                        signature_method=oauthlib.oauth1.SIGNATURE_HMAC,
                                        signature_type=oauthlib.oauth1.SIGNATURE_TYPE_QUERY)
        signature = client.sign("{}{}".format(url, urlparams))
        print signature[0]
        signed_url = signature[0]
        new_url = signed_url[len('http://localhost'):]
        ret = self.app.get(new_url)
        self.assertFalse(self.has_exception())
        ret = self.app.get("/post_grade/1.0")
        self.assertFalse(self.has_exception())
        self.assertEqual(ret.data, "grade=True")
        ret = self.app.get("/post_grade/2.0")
        self.assertFalse(self.has_exception())
        self.assertEqual(ret.data, "grade=False")

    @httpretty.activate
    def test_access_to_oauth_resource_post_grade_fix_url(self):
        uri = 'https://localhost:8000/dev_stack'

        def request_callback(request, uri, headers):
            return (200, headers, "success")

        httpretty.register_uri(httpretty.POST, uri, body=request_callback)

        self.reset_exception()
        consumers = self.consumers
        url = 'http://localhost/initial?'
        method = 'GET'
        headers = dict()
        params = {'resource_link_id': u'edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8',
                  'user_id': u'008437924c9852377e8994829aaac7a1',
                  'roles': u'Instructor',
                  'lis_result_sourcedid': u'MITx/ODL_ENG/2014_T1:edge.edx.org-i4x-MITx-ODL_ENG-lti-94173d3e79d145fd8ec2e83f15836ac8:008437924c9852377e8994829aaac7a1',
                  'context_id': u'MITx/ODL_ENG/2014_T1',
                  'lti_version': u'LTI-1p0',
                  'launch_presentation_return_url': u'',
                  'lis_outcome_service_url': uri,
                  'lti_message_type': u'basic-lti-launch-request',
        }
        store = LTIOAuthDataStore(consumers)
        import urllib

        urlparams = urllib.urlencode(params)
        import oauthlib.oauth1

        client = oauthlib.oauth1.Client('__consumer_key__', client_secret='__lti_secret__',
                                        signature_method=oauthlib.oauth1.SIGNATURE_HMAC,
                                        signature_type=oauthlib.oauth1.SIGNATURE_TYPE_QUERY)
        signature = client.sign("{}{}".format(url, urlparams))
        print signature[0]
        signed_url = signature[0]
        new_url = signed_url[len('http://localhost'):]
        ret = self.app.get(new_url)
        self.assertFalse(self.has_exception())
        ret = self.app.get("/post_grade/1.0")
        self.assertFalse(self.has_exception())
        self.assertEqual(ret.data, "grade=True")
        ret = self.app.get("/post_grade/2.0")
        self.assertFalse(self.has_exception())
        self.assertEqual(ret.data, "grade=False")


# if __name__ == '__main__':
#     unittest.main()
