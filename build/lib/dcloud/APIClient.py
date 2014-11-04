#!/usr/bin/env python

import os, sys
from OAuth2Client import *

FAILED_HOST_LIST = "failedHostList"

# COURTESY of the GPHDMGR API TEAM
###########################################################################################################
# PHDMGR API client that exposes REST APIs as methods and uses OAuth2 client to connect to PHDMGR         #       
###########################################################################################################
class APIClient(OAuth2Client):
    
    def __init__(self, host = DEFAULT_HOST, port = DEFAULT_PORT, context = DEFAULT_CONTEXT, tokenEndpoint = DEFAULT_TOKEN_ENDPOINT, clientId = DEFAULT_CLIENT_ID, clientsFile = DEFAULT_CLIENTS_FILE, secure = True, verbose = False):        
        """ Constructs new instance of the client using OAuth2Client for underlying REST calls """
        OAuth2Client.__init__(self, host, port, context, tokenEndpoint, clientId, clientsFile, secure, verbose)

    ######################################################################################################
    ### ----- HELPER METHODS ----- #######################################################################
    ######################################################################################################
    
    def __executeCall(self, method, path, body = {}, checkScanHostsResponse=False):
        # call server and get either parsed JSON or just a string
        response = self.callRemote(method, path, body)
        # first, check if there is a newer errorResponse field in JSON
        if response is not None and hasattr(response, 'has_key') and response.has_key("errorResponse") and response["errorResponse"] is not None:
            errorResponse = response["errorResponse"]
            if errorResponse.has_key("returnCode") and errorResponse.has_key("message") and errorResponse["message"] is not None:
                message = self.__formatApiError(errorResponse)
                raise Exception, "Server error: %s" % message
        # check older rcType code for error        
        if response is not None and hasattr(response, 'has_key') and response.has_key("rcType") and response["rcType"] == "FAILURE":            
            message = self.__formatScanhostsError(response) if checkScanHostsResponse else None
            # message returned can still be None, so can;t combined the 2 checks into 1
            if message is None:
                message = response["msg"]
                message = "unspecified" if message is None else message            
            raise Exception, "Server error: %s" % message
        return response
    
    def __formatApiError(self, errorResponse):
        databuffer = "\n"
        if errorResponse["returnCode"] is not None:
            databuffer = databuffer + "Return Code : %s\n" % (errorResponse["returnCode"])
        if errorResponse["message"] is not None:
            databuffer = databuffer + "Message : %s\n" % (errorResponse["message"])
        if errorResponse["resolution"] is not None:
            databuffer = databuffer + "Resolution : %s\n" % (errorResponse["resolution"])
        if errorResponse["details"] is not None:
            databuffer = databuffer + "Details :\n"
            for host in errorResponse["details"].keys():
                databuffer = databuffer +  "%s :\n" % (host)
                for entry in errorResponse["details"][host]:
                    if entry is not None and entry.has_key("OPERATION_CODE") and entry.get("OPERATION_CODE") is not None:
                        databuffer = databuffer + "\tOperation Code : %s\n" % (entry.get("OPERATION_CODE"))
                    if entry is not None and entry.has_key("OPERATION_ERROR") and entry.get("OPERATION_ERROR") is not None:
                        databuffer = databuffer + "\tOperation Error : %s\n" % (entry.get("OPERATION_ERROR"))
                    if entry is not None and entry.has_key("LOG_FILE") and entry.get("LOG_FILE") is not None:
                        databuffer = databuffer + "\tLog File : %s\n" % (entry.get("LOG_FILE"))
                    if entry is not None and entry.has_key("RESOLUTION") and entry.get("RESOLUTION") is not None:
                        databuffer = databuffer + "\tResolution : %s\n" % (entry.get("RESOLUTION"))
                    databuffer = databuffer + "\n"
        return databuffer
    
    #API returns errorResponse in JSON format. Re-format the json to easily readable format on console
    def __formatScanhostsError(self, errorResponse):
        message = None
        if type(errorResponse) is not list:
            if hasattr(errorResponse, 'has_key') and errorResponse.has_key(FAILED_HOST_LIST) and len(errorResponse[FAILED_HOST_LIST]) > 0:
                message = "\n[RESULT] The following hosts do not meet PHD prerequisites: [ "
                for host in errorResponse[FAILED_HOST_LIST].keys():
                    message = message + host + " "
                message = message + "] Details... \n"
                for host in errorResponse[FAILED_HOST_LIST].keys():
                    infolist = errorResponse[FAILED_HOST_LIST][host]
                    message = message + "Host: %s \nStatus: [FAILED]\n" % host
                    if len(infolist) != 0:
                        for info in infolist:
                            if ( ('[ERROR]' in info) | ('[WARNING]' in info) ):
                                message = message + "\t%s\n" % info
        return message

    def __printSuccessMessage(self, response, prefix = ""):
        if response is not None and hasattr(response, "has_key") and response.has_key("rcType") and response["rcType"] == "SUCCESS" and response.has_key("msg") and response["msg"] is not None:
            print prefix + response['msg']

    ######################################################################################################
    ### ----- BUSINESS METHODS : SYNCHRONOUS ----- #######################################################
    ######################################################################################################
    
    def selfUpgrade(self):
        return self.__executeCall("POST", "v1/selfupgrade")
    
    def importPackage(self, package, version):
        return self.__executeCall("POST", "v1/configurations/%s?version=%s" % (package, version))
    
    def importStack(self, stackConfig):
        return self.__executeCall("POST", "v1/stacks", stackConfig)

    def getRpmVersion(self, stack_name, service_name):
        return self.__executeCall("GET", "v1/stacks/%s/%s" % (stack_name, service_name))

    def backFill(self, clusterStackInfo):
        return self.__executeCall("POST", "v1/backfill", clusterStackInfo)

    def getClusterTemplateJson(self, inputData):
        return self.__executeCall("GET", "v1/configurations/default/%s" % inputData["gphdStackVer"])

    def getUpgradeClusterConfigurationJson(self, inputData):
        return self.__executeCall("GET", "v1/configurations/upgradeConfig/%s/%s" % (inputData["clustername"],inputData["gphdStackVer"]))

    def getClusterConfigurationJson(self, clusterID):
        return self.__executeCall("GET", "v1/clusters/%s/configuration?type=new" % clusterID)
        
    def getClusterList(self):
        return self.__executeCall("GET", "v1/clusters")

    def getClusterID(self, clusterName):
        clusterList = self.getClusterList()
        if len(clusterList) > 0 :
            for cluster in clusterList:
                name = cluster["name"].encode('utf-8')
                if name == clusterName:
                    return cluster["id"]
        return -1
              
    # get existing cluster info
    def getClusterInfo(self, inputData):
        # for some reason empty dict is preferable to return rather than exception
        try:
            return self.__executeCall("GET", "v1/clusters/%s/rolemap" % inputData["clustername"])
        except Exception, err:
            print >> sys.stderr, "\n[ERROR] Failed to fetch cluster configuration. Reason: %s" % str(err)
            return {}

    def getClusterStatus(self, inputData):
        response = self.__executeCall("GET", "v1/clusters/%s" % inputData["clusterId"])
        return response["status"]

    def getClusterHosts(self, inputData):
        hostList = [] 
        clusterInfo = self.getClusterInfo(inputData)
        if clusterInfo and clusterInfo.has_key("hostList"):
            for host in clusterInfo["hostList"]:
                hostList.append(host.encode('utf-8')) 
        return hostList

    def getInstallStatus(self, clusterID):
        return self.__executeCall("GET", "v1/clusters/%s/status/install" % clusterID)
    
    def getUninstallStatus(self, clusterID):
        return self.__executeCall("GET", "v1/clusters/%s/status/uninstall" % clusterID)
      
    def initAlerts(self):
        return self.__executeCall("POST", "v1/alerts?initialize=true")

    def initializePlugins(self):
        response = self.__executeCall("POST", "v1/plugins/initialize")
        self.__printSuccessMessage(response)

    def initializeSecurity(self, securityConfigJson):
        response = self.__executeCall("POST", "v1/security/initialize", securityConfigJson)
        self.__printSuccessMessage(response)
         
    def addSlaves(self, clusterDescriptorJSON, inputData):
        response = self.__executeCall("POST", "v1/clusters/%s/actions/expand?" % inputData["clusterId"], clusterDescriptorJSON)
        self.__printSuccessMessage(response, "SUCCESS: ")

    def removeSlaves(self, clusterDescriptorJSON, inputData):
        response = self.__executeCall("POST", "v1/clusters/%s/actions/reduce?" % inputData["clusterId"], clusterDescriptorJSON)
        self.__printSuccessMessage(response, "SUCCESS: ")

    def restoreNamenodeDirectories(self, client, inputData):
        data = {'clustername': inputData["clustername"]}
        response = self.__executeCall("POST", "v1/admin/services/restorenamenodedirectories", data)
        print response

    def scanHosts(self, inputData):
        output={}
        output["hostList"] = inputData["hosts"]
        output["javaHome"] = inputData["javaHome"]
        output["verbose"] = inputData["verbose"]        
        return self.__executeCall("POST", "v1/admin/services/scanhosts", output)

    def prepareHosts(self, inputData):
        output={}
        output["hostList"] = inputData["hosts"]
        output["jdkPath"] = inputData["jdkPath"]
        output["verbose"] = inputData["verbose"]
        output["ntp"] = inputData["setupNTP"]
        output["ntpServer"] = inputData["ntpServer"]
        output["disableSELinux"] = inputData["disableSELinux"]
        output["disableIPTables"] = inputData["disableIPTables"]
        output["sysConfigDir"] = inputData["sysConfigDir"]
        output["skipPasswordlessSSH"] = inputData["skipPasswordlessSSH"]
    
        if not output["skipPasswordlessSSH"]:
            output["rootPassword"]=inputData["rootPassword"]
            output["gpadminPassword"]=inputData["gpadminPassword"]
        else:
            output["rootPassword"]=""
            output["gpadminPassword"]=""
            
        return self.__executeCall("POST", "v1/admin/services/preparehosts", output)

    ######################################################################################################
    ### ----- BUSINESS METHODS : ASYNCHRONOUS ----- ######################################################
    ######################################################################################################
    
    # asynchronous method - should not propagate exception
    def deployConfiguration(self, clusterConfigJSON, inputData):
        try:
            responseStrJson = self.__executeCall("POST", "v1/clusters", clusterConfigJSON, checkScanHostsResponse=True)
            inputData["clusterId"] = responseStrJson["clusterId"].encode('utf-8')
        except Exception, err:
            print >> sys.stderr, "\n[ERROR] Failed to deploy the cluster. Reason: %s\n" % str(err)
            os._exit(-1) 
            
    # asynchronous method - should not propagate exception
    def updateCluster(self, clusterConfigJSON, inputData):
        try:
            self.__executeCall("POST", "v1/clusters/%s/actions/update" % inputData["clustername"], clusterConfigJSON, checkScanHostsResponse=True)            
        except Exception, err:
            print >> sys.stderr, "\n[ERROR] Failed to update the cluster. Reason: %s\n" % str(err)
            os._exit(-1) 
    
    # asynchronous method - should not propagate exception    
    def upgradeCluster(self, inputData, clusterId, stackName, operationUserOptionJSON):
        try:
            self.__executeCall("POST", "v1/clusters/%s/actions/upgradeStack/%s" % (clusterId, stackName), operationUserOptionJSON)            
        except Exception, err:
            print >> sys.stderr, "\n[ERROR] Failed to update the cluster. Reason: %s\n" % str(err)
            os._exit(-1) 

    # asynchronous method - should not propagate exception
    def uninstallCluster(self, inputData):
        try:
            self.__executeCall("POST", "v1/clusters/%s" % inputData["clusterId"], {'keepHistory': inputData['keephistory']})
        except Exception, err:
            print >> sys.stderr, "\n[ERROR] Failed to uninstall the cluster. Reason: %s\n" % str(err)
            os._exit(-1) 
    
    # asynchronous method - should not propagate exception
    def startCluster(self, clusterDescriptorJSON, inputData):
        try:
            self.__executeCall("POST", "v1/clusters/%s/%s" % (inputData["clusterId"], inputData["url"]), clusterDescriptorJSON)
        except Exception, err:
            print >> sys.stderr, "\n[ERROR] Failed to start the cluster. Reason: %s\n" % str(err)
            os._exit(-1) 
            
    # asynchronous method - should not propagate exception
    def stopCluster(self, clusterDescriptorJSON, inputData):
        try:
            self.__executeCall("POST", "v1/clusters/%s/%s" % (inputData["clusterId"], inputData["url"]), clusterDescriptorJSON)
        except Exception, err:
            print >> sys.stderr, "\n[ERROR] Failed to stop the cluster. Reason: %s\n" % str(err)
            os._exit(-1) 
             
############# END OF FILE #######################
