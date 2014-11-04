#!/usr/bin/python
# coding: utf-8

# Copyright (C) 2013-2014 Pivotal Software, Inc.
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the under the Apache License,
# Version 2.0 (the "License”); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os, subprocess, sys, json, copy, getpass
import docker as dockerpy
import dockerDriver
import ConfigParser
from utils import ssh
from utils import cmdutil
import phdDesigner
from utils import directoryScan
from utils import configFile
import crypt
import time

NAMESPACE = "dcloud"
VERSION = "0.2"

COMMAND_CREATE = "create"
COMMAND_LIST = "list"
COMMAND_HOSTSFILE = "hostsfile"
COMMAND_DESTROY = "destroy"
COMMAND_SNAPSHOT = "snapshot"
COMMAND_DELETESNAPSHOT = "deletesnapshot"
COMMAND_ARCHIVE = "archive"
COMMAND_SHAREKEYS = "sharekeys"
COMMAND_CREATEPHD = "createphd"
COMMAND_IMPORTPHD = "importphd"
COMMAND_AMBARIBASE = "ambaribase"



REPO_DNS_BASE = "{0}/dns-base:{1}".format(NAMESPACE, VERSION)
#REPO_DNS_BASE = "{0}/dns-base".format(NAMESPACE)


class RunResult:
    dns = ""
    hosts = ""

_WORK_DIR = "/tmp/dcloud_work"

def usage():
    print "Usage:"
    print "  " + COMMAND_CREATE + ":    Create dcloud cluster. dcloud "
    print "  " + COMMAND_LIST + ":      List dcloud clusters"
    print "  " + COMMAND_HOSTSFILE + ": Outputs hosts file format to a specified file. Users can redirect it to /etc/hosts"
    print "  " + COMMAND_DESTROY + ":   Destroy a dcloud cluster"
    print "  " + COMMAND_SNAPSHOT + ":  Snapshot a dcloud cluster. This is to 'docker commit' to all Docker containers in a specified cluster"
    print "  " + COMMAND_DELETESNAPSHOT + ":  Delete a cluster snapshot."
    # print "  " + COMMAND_ARCHIVE + ":   Make a tar ball of cluster nodes"
    print "  " + COMMAND_SHAREKEYS + ":  Share SSH Keys among nodes in dcloud Cluster"
    print "  " + COMMAND_CREATEPHD + ":    Create PHD cluster "
    print "  " + COMMAND_IMPORTPHD + ":    Import Software for PHD cluster "
    print "  " + COMMAND_AMBARIBASE + ":    Build Base Cluster for Ambari Install "



def usageCreate():
    print "usage:  dcloud create [-id <cluster_id>] <dcluster_config file>"
    print "  -id option overrides the clusterId specified in the config file"
    print "  e.g. dcloud create example/cluster_from_images.json"

def usageCreatePHD():
    print "usage: dcloud createphd [-id <cluster_id>] <dcluster_config file> <#Nodes>"
    print "  -id option overrides the clusterId specified in the config file"
    print "  e.g. dcloud create example/cluster_from_images.json"
    print " # Nodes <= Node Count. "
    
def usageAmbariBase():
    print "usage: dcloud ambaribase [-id <cluster_id>] <dcluster_config file> <#Nodes>"
    print "  -id option overrides the clusterId specified in the config file"
    print "  e.g. dcloud create example/cluster_from_images.json"
    print " # Nodes <= Node Count. "


def _parseHostname(exp):
    '''
    node1.mydomain.com --> ["node1.mydomain.com"]
    node[1..3].mydomain.com --> ["node1.mydomain.com", "node2.mydomain.com", "node3.mydomain.com"]
    '''
    if "[" not in exp and "]" not in exp:
        return [exp]
    
    expStart = int(exp.index("["))
    dotdotStart = exp.index("..")
    expEnd = int(exp.index("]"))
    startNumber = int(exp[expStart+1:dotdotStart])
    endNumber = int(exp[dotdotStart+2:expEnd])
    result = []
    for i in range(startNumber, endNumber + 1):
        result.append(exp[:expStart] + str(i) + exp[expEnd+1:])
    return result
    
def _flattenHostname(conf):    
    copiedNodes = copy.deepcopy(conf["nodes"])
    conf["nodes"] = []
    for node in copiedNodes:
        hostnames = _parseHostname(node["hostname"])
        for hostname in hostnames:
            newnode = copy.deepcopy(node)
            newnode["hostname"] = hostname
            conf["nodes"].append(newnode)

    return conf

def _flattenDockerfile(conf):
    for node in conf["nodes"]:
        if "Dockerfile" in node:
            tempImageName = conf["id"] + "/" + node["hostname"].replace("[", "_").replace("]", "_")
            cmdutil.execute(["docker", "build", "-t", tempImageName, node["Dockerfile"]])
            #print "docker", "build", "-t", tempImageName, node["Dockerfile"]
            node["imageName"] = tempImageName
    return conf


def create(clusterConfigFilePath, overrideClusterId):
    '''
    return:
    {
       "dns": "172.17.0.2",
       "hosts": "172.17.0.2 master\n172.17.0.3 slave1\n172.17.04 slave2"
    }
    '''
    
    dnsServerAddress = None
    hosts = ""
    
    with open(clusterConfigFilePath, "r") as conffile:
        conf = conffile.read()
    
    try:
        clusterConfig = json.loads(conf)
    except ValueError as e:
        print "Given cluster config json file " + clusterConfigFilePath + " is invalid "
        print e.message
        return 1
        
    # docker build if Dockerfile is specified
    clusterConfig = _flattenDockerfile(clusterConfig)

    clusterConfig = _flattenHostname(clusterConfig)
    
    if overrideClusterId != None:
        clusterConfig["id"] = overrideClusterId


    # Append DNS
    dnsNode = {
        "hostname" : "dclouddns",
        "imageName" : REPO_DNS_BASE,
        "cmd" : "service sshd start && tail -f /var/log/yum.log"
    }
    clusterConfig["nodes"].insert(0, dnsNode)

    for i in range(len(clusterConfig["nodes"])):
        # The first iteration is for DNS
        node = clusterConfig["nodes"][i]

        container_name = _generateContainerName(clusterConfig["id"], node["hostname"])

        cmd = ["docker", "run"
		    , "-d" # daemon
      		, "--privileged"]

        # DNS
        cmd.append("--dns")
        if i == 0:
            cmd.append("127.0.0.1") # localhost 
        else:
            cmd.append(dnsServerAddress)

        if "dns" in clusterConfig:
            for dnsIp in clusterConfig["dns"]:
                cmd.append("--dns")
                cmd.append(dnsIp)

        if "domain" in clusterConfig:
            cmd.append("--dns-search")
            cmd.append(clusterConfig["domain"])

        fqdn = node["hostname"] + "." + clusterConfig["domain"]

        cmd.append("--name")
        #cmd.append(container_name)
        cmd.append(fqdn)


        cmd.append("-h")
        cmd.append(fqdn)

        if "volumes" in node:
            for volumn in node["volumes"]:
                cmd.append("-v")
                cmd.append(volumn)

        cmd.append(node["imageName"])
        cmd.append("bash")
        cmd.append("-c")
        cmd.append(node["cmd"])
        print "executing: " + ' '.join(cmd)
        subprocess.call(cmd)

        ip = dockerDriver.getContainerIpAddress(container_name)
        if i == 0:
            dnsServerAddress = ip
        hosts += ip + " " + fqdn + " " + node["hostname"] + "\n"

    print "dnsServerAddress: " + dnsServerAddress
    if(not ssh.connection_check(dnsServerAddress, "root", "changeme")):
        print "**** ERROR ****"
        print "ssh connection to root@" + dnsServerAddress + " could not be established"
        return 1

    ssh.exec_command2(dnsServerAddress, "root", "changeme", "echo '" + hosts + "' > /etc/dcloud/dnsmasq/hosts")
    ssh.exec_command2(dnsServerAddress, "root", "changeme", "service dnsmasq restart")

    print "hosts:"
    print hosts
    result = RunResult()
    result.dns = dnsServerAddress
    result.hosts = hosts
    return 0

def createPHD(clusterConfigFilePath, overrideClusterId,nodeCnt):
    '''
    return:
    {
       "dns": "172.17.0.2",
       "hosts": "172.17.0.2 master\n172.17.0.3 slave1\n172.17.04 slave2"
    }
    '''
    print "Cluster Build Start Time: "+str(time.asctime(time.localtime(time.time())))
   
    
    
    dnsServerAddress = None
    hosts = ""
    hadoopHosts=[]
    rootPassword = "changeme"

    encPassword = crypt.crypt(rootPassword,"salt")



    with open(clusterConfigFilePath, "r") as conffile:
        conf = conffile.read()

    try:
        clusterConfig = json.loads(conf)
        clusterConfig["nodes"][0]["hostname"] = str(clusterConfig["nodes"][0]["hostname"]).replace("6",nodeCnt)

    except ValueError as e:
        print "Given cluster config json file " + clusterConfigFilePath + " is invalid "
        print e.message
        return 1

    # docker build if Dockerfile is specified
    clusterConfig = _flattenDockerfile(clusterConfig)

    clusterConfig = _flattenHostname(clusterConfig)

    if overrideClusterId != None:
        clusterConfig["id"] = overrideClusterId

    # Append DNS
    dnsNode = {
        "hostname" : "dclouddns",
        "imageName" : REPO_DNS_BASE,
        "cmd" : "service sshd start && tail -f /var/log/yum.log"
    }


    clusterConfig["nodes"].insert(0, dnsNode)
    clusterConfig = _flattenHostname(clusterConfig)

    basePath = os.path.split(__file__)[0]
    pccPath = configFile.getParam( _WORK_DIR+"/.dcloud.ini","PHD","pcc")
    pccPath = os.path.split(pccPath)[0]
    volumes = ['/mnt/pcc','/mnt/config']

    volumeBinds = {
        pccPath : {'bind' : '/mnt/pcc', "ro" : False},
        str(basePath)+"/template" : {'bind' : '/mnt/config', "ro" : False}
        }
    
 
    #pullImages(dnsNode["imageName"],phd,dockerFilePath)
    print "Setting Images for Use"
    pullImages(dnsNode["imageName"])

    for i in range(len(clusterConfig["nodes"])):
        dnsList=[]

        node = clusterConfig["nodes"][i]
        containerName = _generateContainerName(clusterConfig["id"], node["hostname"])
        #containerName = str(clusterConfig["id"])+"."+str(node["hostname"])
        domainName = clusterConfig["domain"]
        fqdn = node["hostname"] + "." + clusterConfig["domain"]

        cmdString = "bash -c '"+node["cmd"]+"'"
        dockerClient=dockerpy.Client()
        #containerId = dockerClient.create_container(node["imageName"],command=cmdString,hostname=node["hostname"],domainname=domainName,detach=True,name=containerName,volumes=volumes)["Id"]
        #containerId = dockerClient.create_container(node["imageName"],command=cmdString,hostname=node["hostname"]+"."+domainName,domainname=domainName,detach=True,name=containerName,volumes=volumes)["Id"]
        containerId = dockerClient.create_container(node["imageName"],command=cmdString,hostname=node["hostname"]+"."+domainName,detach=True,name=containerName,volumes=volumes)["Id"]

        if i == 0:
            dnsList.append("127.0.0.1")
        else:
            dnsList.append(dnsServerAddress)

        if "dns" in clusterConfig:
            for dnsIp in clusterConfig["dns"]:
                dnsList.append(dnsIp)

        dockerClient.start(containerId,dns=dnsList,dns_search=domainName,privileged=True,binds=volumeBinds)

        containerInfo = dockerClient.inspect_container(containerId)
        containerIP = containerInfo['NetworkSettings']['IPAddress']
        if i == 0:
            dnsServerAddress = containerIP

        hosts += containerIP + " " + fqdn + " " + node["hostname"] + "\n"

        if (node["hostname"] != "dclouddns"):
            hadoopHosts.append({"hostname":node["hostname"],"ip":containerIP,"fqdn":fqdn,"id":containerId})


    print "DNS Server Address: " + dnsServerAddress
    if(not ssh.connection_check(dnsServerAddress, "root", "changeme")):
        print "**** ERROR ****"
        print "ssh connection to root@" + dnsServerAddress + " could not be established"
        return 1

    ssh.exec_command2(dnsServerAddress, "root", "changeme", "echo '" + hosts + "' > /etc/dcloud/dnsmasq/hosts")
    ssh.exec_command2(dnsServerAddress, "root", "changeme", "service dnsmasq restart")

    print "Pivotal Hadoop Hosts:"
    print "-----------------------------------------"
    lines = hosts.split('\n')
    print "Management Host: " + lines[0]
    print "Hadoop Nodes:"
    lineCnt = 0
    for line in lines:
        if lineCnt > 0 :
            print line
        lineCnt+=1


    result = RunResult()
    result.dns = dnsServerAddress
    result.hosts = hosts

    #print "gpadmin user created on "+host["hostname"]
    #print "gpadmin users created"
    #print "Sharing Root SSH Keys Across Cluster"
    #shareSSHKeys(clusterConfig["id"],"root",rootPassword)
    #print "Sharing Root SSH Keys Completed"


    mgmtContainerHostname = dockerDriver.getContainerId(clusterConfig["nodes"][1]["hostname"])
    mgmtIPaddress = hadoopHosts[0]["ip"]

    phdDesigner.sparkInstall(configFile,"root","changeme",hadoopHosts,clusterConfig["id"] ,nodeCnt)
    phdDesigner.servicePlacementV2(nodeCnt,hadoopHosts,clusterConfig["domain"],clusterConfig["id"])
    phdDesigner.icmInstall(mgmtIPaddress,_WORK_DIR+"/.dcloud.ini","root","changeme",hadoopHosts,clusterConfig["id"])

    print "Sharing gpadmin keys across Cluster"
    shareSSHKeys(clusterConfig["id"],"gpadmin",rootPassword)
    print  "Sharing gpadmin keys COmpleted"

    phdDesigner.initializeHAWQ("gpadmin","changeme",hadoopHosts,clusterConfig["id"],nodeCnt)
    print "Cluster Build End Time: "+str(time.asctime(time.localtime(time.time())))
    print "Update Docker Host /etc/hosts for hostname based access"
    hostsfile(clusterConfig["id"],"/etc/hosts")
    return 0

def ambariBase(clusterConfigFilePath, overrideClusterId,nodeCnt):
   
    print "Ambari Cluster Build Start Time: "+str(time.asctime(time.localtime(time.time())))
   
    dnsServerAddress = None
    hosts = ""
    hadoopHosts=[]
    rootPassword = "changeme"
    encPassword = crypt.crypt(rootPassword,"salt")


    with open(clusterConfigFilePath, "r") as conffile:
        conf = conffile.read()

    try:
        clusterConfig = json.loads(conf)
        clusterConfig["nodes"][0]["hostname"] = str(clusterConfig["nodes"][0]["hostname"]).replace("6",nodeCnt)

    except ValueError as e:
        print "Given cluster config json file " + clusterConfigFilePath + " is invalid "
        print e.message
        return 1

    # docker build if Dockerfile is specified
    clusterConfig = _flattenDockerfile(clusterConfig)
    clusterConfig = _flattenHostname(clusterConfig)

    if overrideClusterId != None:
        clusterConfig["id"] = overrideClusterId

    # Append DNS
    dnsNode = {
        "hostname" : "dclouddns",
        "imageName" : REPO_DNS_BASE,
        "cmd" : "service sshd start && tail -f /var/log/yum.log"
    }


    clusterConfig["nodes"].insert(0, dnsNode)
    clusterConfig = _flattenHostname(clusterConfig)

    ambariPath = "/root/software"
    volumes = ['/mnt/ambari']

    volumeBinds = {
        ambariPath : {'bind' : '/mnt/ambari', "ro" : False}
        }
    
 
    print "Setting Images for Use"
    pullImages(dnsNode["imageName"])

    for i in range(len(clusterConfig["nodes"])):
        dnsList=[]

        node = clusterConfig["nodes"][i]
        containerName = _generateContainerName(clusterConfig["id"], node["hostname"])
        #containerName = str(clusterConfig["id"])+"."+str(node["hostname"])
        domainName = clusterConfig["domain"]
        fqdn = node["hostname"] + "." + clusterConfig["domain"]

        cmdString = "bash -c '"+node["cmd"]+"'"
        dockerClient=dockerpy.Client()
        #containerId = dockerClient.create_container(node["imageName"],command=cmdString,hostname=node["hostname"],domainname=domainName,detach=True,name=containerName,volumes=volumes)["Id"]
        #containerId = dockerClient.create_container(node["imageName"],command=cmdString,hostname=node["hostname"]+"."+domainName,domainname=domainName,detach=True,name=containerName,volumes=volumes)["Id"]
        containerId = dockerClient.create_container(node["imageName"],command=cmdString,hostname=node["hostname"]+"."+domainName,detach=True,name=containerName,volumes=volumes)["Id"]
        print containerId
        if i == 0:
            dnsList.append("127.0.0.1")
        else:
            dnsList.append(dnsServerAddress)

        if "dns" in clusterConfig:
            for dnsIp in clusterConfig["dns"]:
                dnsList.append(dnsIp)

        dockerClient.start(containerId,dns=dnsList,dns_search=domainName,privileged=True,binds=volumeBinds)

        containerInfo = dockerClient.inspect_container(containerId)
        containerIP = containerInfo['NetworkSettings']['IPAddress']
        if i == 0:
            dnsServerAddress = containerIP

        hosts += containerIP + " " + fqdn + " " + node["hostname"] + "\n"

        if (node["hostname"] != "dclouddns"):
            hadoopHosts.append({"hostname":node["hostname"],"ip":containerIP,"fqdn":fqdn,"id":containerId})

    print "DNS Server Address: " + dnsServerAddress
    if(not ssh.connection_check(dnsServerAddress, "root", "changeme")):
        print "**** ERROR ****"
        print "ssh connection to root@" + dnsServerAddress + " could not be established"
        return 1

    ssh.exec_command2(dnsServerAddress, "root", "changeme", "echo '" + hosts + "' > /etc/dcloud/dnsmasq/hosts")
    ssh.exec_command2(dnsServerAddress, "root", "changeme", "service dnsmasq restart")

    print "Cluster Hosts:"
    print "-----------------------------------------"
    lines = hosts.split('\n')
    print "Management Host: " + lines[1]
    print "Hadoop Nodes:"
    lineCnt = 0
    for line in lines:
        if lineCnt > 1 :
            print line
        lineCnt+=1


    result = RunResult()
    result.dns = dnsServerAddress
    result.hosts = hosts


     
    #print "gpadmin user created on "+host["hostname"]
    #print "gpadmin users created"
    #print "Sharing Root SSH Keys Across Cluster"
    #shareSSHKeys(clusterConfig["id"],"root",rootPassword)
    #print "Sharing Root SSH Keys Completed"


    mgmtContainerHostname = dockerDriver.getContainerId(clusterConfig["nodes"][1]["hostname"])
    mgmtIPaddress = hadoopHosts[0]["ip"]

    print "Sharing root keys across Cluster"
    shareSSHKeys(clusterConfig["id"],"root",rootPassword)
    print  "Sharing root keys Completed"

    
  
    print "Cluster Build End Time: "+str(time.asctime(time.localtime(time.time())))
    print "Update Docker Host /etc/hosts for hostname based access"
    hostsfile(clusterConfig["id"],"/etc/hosts")
    if (os.path.isfile("/root/.ssh/known_hosts")):
        os.remove("/root/.ssh/known_hosts")
    phdDesigner.preAmbariSetup("root","changeme",hadoopHosts,clusterConfig["id"] ,nodeCnt)

    return 0


def destroy(dClusterId):
    psResult = dockerDriver.ps()
    for item in psResult:
        dclusterName, _nodeName = _parseContainerName(item.name)
        if dclusterName == dClusterId:
            subprocess.call(["docker", "kill", item.containerId])
            dockerDriver.rm(item.containerId, True)

def listClusterInfo(dClusterId=None):
    psResult = dockerDriver.ps()
    if dClusterId is None:
        clusterIds = []
        for container in psResult:
            clusterName, _ = _parseContainerName(container.name)
            if clusterName is not None and clusterName not in clusterIds:
                clusterIds.append(clusterName)
        print "cluster Ids"
        print "\n".join(clusterIds)
        return

    for container in psResult:
        clusterName, _ = _parseContainerName(container.name)
        if clusterName == dClusterId:
            ip = dockerDriver.getContainerIpAddress(container.name)
            print ip
            
def hostsfile(dclusterId, outputfile):
    hosts = ""
    psResult = dockerDriver.ps()
    for container in psResult:
        clusterName, _ = _parseContainerName(container.name)
        if clusterName == dclusterId:
            container = dockerDriver.getContainer(container.name)
            hosts += container.ip + " " + container.fqdn + " " + container.hostname + "\n"
    with open(outputfile, "w") as text_file:
        text_file.write(hosts)
    print hosts


    print 0

DCLOUD_MANAGED_CONTAINER_PREFIX = "phdcloud_managed--"
DCLOUD_MANAGED_CONTAINER_DIVIDER = "--.--"

def _parseContainerName(containerName):
    '''
    "dcloud_managed--example_cluster--.--node2" --> "example_cluster" and "node2"
    "conatiner1" --->  None and None
    '''
    if(DCLOUD_MANAGED_CONTAINER_PREFIX in containerName and DCLOUD_MANAGED_CONTAINER_DIVIDER in containerName):
        return containerName[len(DCLOUD_MANAGED_CONTAINER_PREFIX):containerName.index(DCLOUD_MANAGED_CONTAINER_DIVIDER)], containerName[containerName.index(DCLOUD_MANAGED_CONTAINER_DIVIDER)+len(DCLOUD_MANAGED_CONTAINER_DIVIDER):]
    else:
        return None, None

def _generateContainerName(clusterName, hostname):
    return DCLOUD_MANAGED_CONTAINER_PREFIX + clusterName + DCLOUD_MANAGED_CONTAINER_DIVIDER + hostname
            
def snapshot(dClusterId, tag=None):

    dockerClient=dockerpy.Client()
    currentCluster = dockerClient.containers()
    for container in currentCluster:
        clusterId, nodeName = _parseContainerName(container["Id"])
        dockerClient.commit(container["Id"],clusterId + "/" + nodeName)

    # for container in psResult:
    #     clusterId, nodeName = _parseContainerName(container.name)
    #     if clusterId == dClusterId:
    #         if tag is None:
    #             subprocess.call(["docker", "commit", container.name, clusterId + "/" + nodeName])
    #         else:
    #             subprocess.call(["docker", "commit", container.name, clusterId + "/" + nodeName + ":" + tag])

def deletesnapshot(dClusterId, tag=None):
    images = dockerDriver.images()
    for image in images:
        if image.repository.startswith(dClusterId) and tag is None:
            cmdutil.execute(["docker", "rmi", image.repository + ":" + image.tag])
        elif image.repository.startswith(dClusterId + "/") and tag == image.tag:
            cmdutil.execute(["docker", "rmi", image.repository + ":" + image.tag])


def getContainers(dClusterId):
    psResult = dockerDriver.ps()
    result = []
    for container in psResult:
        clusterId, nodeName = _parseContainerName(container.name)
        if clusterId == dClusterId:
            result.append(container)
            
    return result



def pullImages(dnsImage):
    dockerClient= dockerpy.Client(base_url='unix://var/run/docker.sock',
                  version='1.3',
                  timeout=10)
    basePath = os.path.split(__file__)[0]
    print "PULLING/BUILDING Needed Images"
    found = False
    while (not found):
        try:
            print "Checking Image Repository for Local Image for DNS Server"
            dockerClient.inspect_image(dnsImage)
            print "Found Local Image"
            found=True
        except Exception:
            print "No Local Version Found....pulling from Docker Hub"
            dockerClient.pull(dnsImage)
            
    print "Building Images required for PHDCLOUD"
    dockerFile = os.path.join(basePath,"dockerFiles/phdcluster")    
    dockerClient.build(path=dockerFile,tag="dbbaskette/phdcloud")    
    print "Built PHDCloud"
    print "Building AmbariBase"
    dockerFile = os.path.join(basePath,"dockerFiles/ambariBase")
    print dockerFile
    dockerClient.build(path=dockerFile,tag="dbbaskette/ambaribase")
    print "BUILT@!"




def archive(dClusterId, repo=None):
    '''
    Export docker containers and make a tar.gz
    '''
    if repo is None:
        repo = dClusterId
        
    ARCHIVE_DIR = _WORK_DIR + "/" + dClusterId
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

    # docker export
    containers = getContainers(dClusterId)
    for container in containers:
        _, nodeName = _parseContainerName(container.name)

        print "Exporting " + container.name + "..."
        with open(ARCHIVE_DIR + "/" + repo + "-" + nodeName + ".tar", "w") as file1:
            p = subprocess.Popen(["docker", "export", container.name], stdout=file1)
            p.wait()
            file1.flush()

    # tar.gz
    archive_file = dClusterId + ".tar.gz"
    print "Making " + archive_file + "..."
    subprocess.Popen(["tar", "-zcvf", archive_file, dClusterId], cwd=_WORK_DIR).wait()
    print "Making " + archive_file + ".md5..."
    with open(archive_file + ".md5", "w") as file1:
        subprocess.Popen(["md5sum", archive_file, dClusterId], cwd=_WORK_DIR, stdout=file1).wait()
        file1.flush()

def shareSSHKeys(dClusterId,username,password):
    # Get hostnames of all clusternodes and then run keygen on each and copyid on each
    c = dockerpy.Client()
    clusterHosts={}
    containers = c.containers()
    for container in containers:
        clusterName = str(container['Names']).split("--")[1]
        containerId = container['Id']
        c.inspect_container(containerId)
        hostName = (str(container['Names']).split("--")[3])[:-2]
        if (clusterName == dClusterId) & (hostName != "dclouddns" ):
            ipAddress = c.inspect_container(containerId)["NetworkSettings"]["IPAddress"]
            clusterHosts[hostName]=ipAddress
    for host in clusterHosts:
        for clusterNode in clusterHosts:
            key = ssh.getKey(clusterHosts[clusterNode],username,password)
            if host != clusterNode:
                ssh.copyKey(key,clusterHosts[clusterNode],username,password)

    #####
    #  CHANGE ABOVE TO JUST SHARE KEY FROM MGMT NODE


def parseCreateParams(argv):

    argLength = len(argv)
    if argLength != 1 and argLength !=3:
        raise ParseException()

    if argLength == 1:
        clusterId = None
        file1 = argv[0]
    else:
        if argv[0] != "-id":
            raise ParseException()

        clusterId = argv[1]
        file1 = argv[2]

    return file1, clusterId

    




def parseCreatePHDParams(argv):

    argLength = len(argv)
    #print "ARGUMENTS: "+str(argLength)
    if argLength != 1 and argLength !=3:
        raise ParseException()

    if argLength == 1:
        clusterId = None
        #file1 = argv[0]
        nodeCnt = argv[0]
        print "NODES: "+ str(nodeCnt)

    else:
        if argv[0] != "-id":
            raise ParseException()

        clusterId = argv[1]
        #file1 = argv[2]
        nodeCnt = argv[2]

    basePath = os.path.split(__file__)[0]
    return str(basePath)+"/phdcluster/clusterConfig.json", clusterId,nodeCnt

def parseAmbariBaseParams(argv):

    argLength = len(argv)
    #print "ARGUMENTS: "+str(argLength)
    if argLength != 1 and argLength !=3:
        raise ParseException()

    if argLength == 1:
        clusterId = None
        #file1 = argv[0]
        nodeCnt = argv[0]
        print "NODES: "+ str(nodeCnt)

    else:
        if argv[0] != "-id":
            raise ParseException()

        clusterId = argv[1]
        #file1 = argv[2]
        nodeCnt = argv[2]

    basePath = os.path.split(__file__)[0]
    return str(basePath)+"/ambaribase/clusterConfig.json", clusterId,nodeCnt

def main():
    if(len(sys.argv) <= 1):
        usage()
        return 0

    if not os.path.exists(_WORK_DIR):
        os.makedirs(_WORK_DIR)
        
    if getpass.getuser() != "root":
        print "Currently only root user is supported. It is an outstanding issue. https://jira.greenplum.com/browse/HDQA-85"
        return 1
        
    if not dockerDriver.installed():
        print "docker command is not available. Follow the installation document http://docs.docker.io/installation and install docker"
        return 1

    command = sys.argv[1]
    if command == COMMAND_DESTROY:
        if len(sys.argv) != 3:
            print "usage: destroy <dClusterId>"
            return 1

        destroy(sys.argv[2])

    elif command == COMMAND_CREATE:
        try:
            conffile, overrideClusterId = parseCreateParams(sys.argv[2:])
        except ParseException:
            usageCreate()
            return 1
        return create(conffile, overrideClusterId)

    elif command == COMMAND_CREATEPHD:
        try:
            conffile, overrideClusterId,nodeCnt = parseCreatePHDParams(sys.argv[2:])
        except ParseException:
            usageCreatePHD()
            return 1
        return createPHD(conffile, overrideClusterId,nodeCnt)
    
    elif command == COMMAND_AMBARIBASE:
        try:
            conffile, overrideClusterId,nodeCnt = parseAmbariBaseParams(sys.argv[2:])
        except ParseException:
            usageAmbariBase()
            return 1
        return ambariBase(conffile, overrideClusterId,nodeCnt)
        
    elif command == COMMAND_SNAPSHOT:
        if len(sys.argv) == 3:
            snapshot(sys.argv[2])
        elif len(sys.argv) == 4:
            snapshot(sys.argv[2], sys.argv[3])
        else:
            print "usage: snapshot <dClusterId> [<tag>]"
            print "This will make docker images of the specified cluster."
            print "Image name becomes"
            print "REPOSITORY               TAG"
            print "<dClusterId>/<hostname>  <tag>"
            return 1

    elif command == COMMAND_DELETESNAPSHOT:
        if len(sys.argv) == 3:
            deletesnapshot(sys.argv[2])
        elif len(sys.argv) == 4:
            deletesnapshot(sys.argv[2], sys.argv[3])
        else:
            print "usage: deletesnapshot <dClusterId> [<tag>]"
            return 1

        
    elif command == COMMAND_ARCHIVE:
        if len(sys.argv) == 3:
            archive(sys.argv[2])
        elif len(sys.argv) == 4:
            archive(sys.argv[2], sys.argv[3])

        else:
            print "usage: archive <dClusterId> [<repo>]"
            return 1

    elif command == COMMAND_LIST:
        if len(sys.argv) > 2:
            listClusterInfo(sys.argv[2])
        else:
            listClusterInfo()

    elif command == COMMAND_SHAREKEYS:
        if len(sys.argv) == 3:
            shareSSHKeys(sys.argv[2])
        else:
            print "usage: <dClusterId>"

    elif command == COMMAND_IMPORTPHD:
        if len(sys.argv) == 3:
            Config = ConfigParser.ConfigParser()
            cfgFile = open(_WORK_DIR+"/.dcloud.ini","w")
            Config.add_section("PHD")
            Config.set("PHD","PCC",sys.argv[2]+"/"+directoryScan.getFilename(sys.argv[2],"PCC"))
            Config.set("PHD","PHD",sys.argv[2]+"/"+directoryScan.getFilename(sys.argv[2],"PHD"))
            Config.set("PHD","PADS",sys.argv[2]+"/"+directoryScan.getFilename(sys.argv[2],"PADS"))

            Config.write(cfgFile)
            cfgFile.close()


        else:
            print "usage: <path to gz files>"

    elif command == COMMAND_HOSTSFILE:
        if len(sys.argv) != 4:
            print "usage: hostsfile <dClusterId> <file>"
            return 1
        
        hostsfile(sys.argv[2], sys.argv[3])

    else:
        usage()
        return 1

if __name__ == '__main__' :
    sys.exit(main())

class ParseException(Exception):
    pass