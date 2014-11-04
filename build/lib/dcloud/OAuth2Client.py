#!/usr/bin/env python

import sys, urllib, urllib2, base64, json, time
#
############################
#         constants        #
############################
DEFAULT_CLIENT_ID = "icm_client"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
DEFAULT_CONTEXT = "gphdmgr"
DEFAULT_TOKEN_ENDPOINT = "sec/oauth/token"
DEFAULT_CLIENTS_FILE = "/tmp/oauth2-clients.conf"

###########################################################################################################
# Stateful client that obtains OAuth2 access token upon initialization and uses it for making REST calls. #       
###########################################################################################################
class OAuth2Client():
    
    def __init__(self, host = DEFAULT_HOST, port = DEFAULT_PORT, context = DEFAULT_CONTEXT, tokenEndpoint = DEFAULT_TOKEN_ENDPOINT, clientId = DEFAULT_CLIENT_ID, clientsFile = DEFAULT_CLIENTS_FILE, secure = True, verbose = False):
        """ Constructs new instance of the client, if security is on, reads client secret from the file and obtains access token from the remote server"""
        self.__clientId = clientId
        self.__contextURL = "http://%s:%d/%s/" % (host, port, context)
        self.__tokenURL   = self.__contextURL + tokenEndpoint       
        self.__accessToken = None
        self.__secure = secure 
        self.__verbose = verbose
        if secure:
            self.__clientSecret = self.__readClientSecret(clientId, clientsFile)
            self.__acquireAccessToken()

    ######################################################################################################
    ### ----- HELPER METHODS ----- #######################################################################
    ######################################################################################################

    def __readClientSecret(self, clientId, clientsFile):
        """ reads client secret for a given client from a given JSON file """
        try:
            clients = json.load(open(clientsFile))
        except Exception, e:
            raise Exception, "Failed to read client data from file %s. Reason: %s" % (clientsFile, str(e)), sys.exc_info()[2] 
        secret = None                    
        for client in clients:
            if (client.has_key("client_id") and client["client_id"] == clientId):
                if not client.has_key("client_secret"):
                    raise Exception, "Failed to find client_secret for client %s in file %s" % (clientId, clientsFile)
                secret = client["client_secret"]
                break        
        if secret is None:
            raise Exception, "Failed to find details for client %s in file %s" % (clientId, clientsFile)
        return secret 
            
    def __acquireAccessToken(self):        
        """ acquires OAuth2 access token from the remote system using client_credentials flow """
        # Prepare request using client credentials passed via basic auth
        data = urllib.urlencode({ 'grant_type' : 'client_credentials' })
        request = urllib2.Request(self.__tokenURL, data)
        request.add_header('Authorization', b'Basic ' + base64.b64encode(self.__clientId + b':' + self.__clientSecret))
        # call the token endpoint 
        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError, e:
            message = ''
            # if network / connection problem
            if hasattr(e, 'reason'):
                message = e.reason                
            # if http problem
            if hasattr(e, 'code'):
                message = "code=%s response=%s" % (e.code, e.read())
            raise Exception, "Failed to obtain access token from %s. Reason: %s" % (self.__tokenURL, str(message))            
        # read and parse token response
        try:
            responseStr = response.read()
            token = json.loads(responseStr)            
        except Exception, err:
            raise Exception, "Failed to obtain access token from %s. Reason: %s" % (self.__tokenURL, str(err)), sys.exc_info()[2]  
        # determine if response contains a token        
        if not token is None and token.has_key("access_token"):
            self.__accessToken = token["access_token"]
        else:
            raise Exception, "Failed to obtain access token from %s. Reason: no token value found in server response." % self.__tokenURL

    def __isTokenInvalid(self, responseStr):
        """ checks if the token has expired or is invalid, returns true if so, false otherwise """
        # {"error":"invalid_token","error_description":"Access token expired: 6d776c82-e45b-4684-8243-f3fbfb9969c9"}
        # {"error":"invalid_token","error_description":"Invalid access token: ff46815f-fd68-406d-b64c-5662650da4d5"}
        try:
            responseJSON = json.loads(responseStr)
            if responseJSON.has_key("error") and responseJSON["error"] == "invalid_token": 
                return True
        except Exception, err:
            print >> sys.stderr, "WARN: Failed to parse server response %s. Reason: %s" % (responseStr, str(err))
        return False
    
    def __getResponse(self, path, data = None):
        """ issues HTTP call for a given path using previously obtained OAuth2 token """
        if self.__secure and self.__accessToken is None:
            raise Exception, "Secure mode is on, but access token is not available."
        method = "GET" if data is None else "POST"
        maxAttempts = 2
        attempt = 1
        retryAllowed = True
        while retryAllowed:
            # be conservative, do not allow to retry unless explicitly allowed from within
            retryAllowed = False
            # construct server path            
            url = self.__contextURL + path
            request = urllib2.Request(url, data)
            request.add_header('User-agent', 'ICM Client')
            # add content type if there is data
            if data is not None:
                request.add_header("Content-type", "application/json")
            # add token if in secure mode
            if self.__secure:
                request.add_header("Authorization", "Bearer %s" % self.__accessToken)
            # get HTTP response.
            if self.__verbose:
                #payload printing is not advised as it can reveal sensitive data
                #payload = "" if data is None else " with payload = %s" % data.encode('utf-8')
                print "[DEBUG]: calling %s %s" % (method, url)
            try:                
                response = urllib2.urlopen(request)
            except urllib2.URLError, e:
                message = str(e)                              
                # if http problem
                if hasattr(e, 'code'):
                    responseStr = e.read()
                    if e.code == 401 and self.__isTokenInvalid(responseStr) and attempt < maxAttempts:
                        # if token is no longer valid and retry allowed, get a new one and retry if successful
                        self.__acquireAccessToken()
                        retryAllowed = True
                        attempt += 1
                        continue
                    else: 
                        message = "code=%s response=%s" % (e.code, responseStr)  
                # if network / connection problem
                elif hasattr(e, 'reason'):
                    message = e.reason             
                raise Exception, "Failed to %s %s. Reason: %s" % (method, url, message), sys.exc_info()[2]
        return response
    
    def __readResponseParseJSON(self, method, path, response):
        """ reads response from the server and parses it into a dictionary if the response is JSON """
        # read the response
        try:
            responseStr = response.read()
        except Exception, err:
            raise Exception, "Failed to %s %s. Reason: problem reading server response : %s" % (method, self.__contextURL + path, str(err)), sys.exc_info()[2]
        if self.__verbose:
            msg = "" if responseStr is None else responseStr.encode('utf-8')
            print "[DEBUG]: response = %s" % msg
        # response might or might not be JSON
        try:
            parsed = json.loads(responseStr)
        except Exception, err:
            parsed = responseStr
        return parsed

    ######################################################################################################
    ### ----- PUBLIC METHODS ----- #######################################################################
    ######################################################################################################

    def setVerbose(self, verbose = False):
        """sets verbosity level for debug output of requests and responses"""
        self.__verbose = verbose
        
    def callRemote(self, method, path, body = {}):
        """ issues HTTP call with OAuth2 token token and parses the JSON response """
        if method == "GET":
            response = self.__getResponse(path, None)
        elif method == "POST":
            # if json is already serialized, pass it raw, else serialize
            data = body if isinstance(body, basestring) else json.dumps(body).strip().encode()
            response = self.__getResponse(path, data)
        else:
            raise Exception, "HTTP method %s is not supported" % method        
        return self.__readResponseParseJSON(method, path, response)
