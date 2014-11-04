__author__ = 'root'
import dockerDriver
from utils import ssh
from utils import configFile
import os
import tarfile
import requests
from APIClient import APIClient
import json
import docker as dockerpy


clusterLayouts = {"clusterSize":
    [
        {0:{"nn":[0,0],"rm":[0],"hs":[0],"dn":[0],"nm":[0],"zk":[0],"cl":[0],"hqm":[0,0],"hqs":[0],"spk":[0]}},
        {1:{"nn":[1,1],"rm":[1],"hs":[1],"dn":[1],"nm":[1],"zk":[1],"cl":[1],"hqm":[1,1],"hqs":[1]},"spk":[1]},
        {2:{"nn":[1,2],"rm":[2],"hs":[2],"dn":[2],"nm":[2],"zk":[1],"cl":[2],"hqm":[1,2],"hqs":[0],"spk":[2]}},
        {3:{"nn":[1,2],"rm":[2],"hs":[2],"dn":[2,3],"nm":[2,3],"zk":[1,2,3],"cl":[2],"hqm":[1,2],"hqs":[2,3],"spk":[2]}},
        {4:{"nn":[1,2],"rm":[2],"hs":[2],"dn":[3,4],"nm":[3,4],"zk":[1,2,3],"cl":[3],"hqm":[1,2],"hqs":[3,4],"spk":[3]}},
        {5:{"nn":[1,2],"rm":[2],"hs":[2],"dn":[3,4,5],"nm":[3,4,5],"zk":[1,2,3],"cl":[3],"hqm":[1,2],"hqs":[3,4,5],"spk":[3]}},
        {6:{"nn":[1,2],"rm":[2],"hs":[2],"dn":[3,4,5,6],"nm":[3,4,5,6],"zk":[1,2,3],"cl":[3],"hqm":[1,2],"hqs":[3,4,5,6],"spk":[3]}},
        {7:{"nn":[1,2],"rm":[3],"hs":[3],"dn":[4,5,6,7],"nm":[4,5,6,7],"zk":[1,2,3],"cl":[4],"hqm":[1,2],"hqs":[4,5,6,7],"spk":[4]}},
        {8:{"nn":[1,2],"rm":[3],"hs":[3],"dn":[4,5,6,7,8],"nm":[4,5,6,7,8],"zk":[1,2,3],"cl":[4],"hqm":[1,2],"hqs":[4,5,6,7,8],"spk":[4]}},
        {9:{"nn":[1,2],"rm":[3],"hs":[3],"dn":[4,5,6,7,8,9],"nm":[4,5,6,7,8,9],"zk":[1,2,3],"cl":[4],"hqm":[1,2],"hqs":[4,5,6,7,8,9],"spk":[4]}}
    ]
}


def servicePlacementV2(nodeCnt,hadoopHosts,domainName,clusterId):
    print "Revision 2 of Service Placement.  This version leverages standard templates"
    basePath = os.path.split(__file__)[0]
    clusterConfigFile = open(str(basePath)+"/template/clusterConfig.2.3","r").readlines()
    clusterConfigFileNew = open(str(basePath)+"/template/clusterConfig.xml","w")
    for line in clusterConfigFile:
        if ("<clusterName>" in line):
            line=line.replace("test",clusterId)
        elif ("<securityEnabled>" in line):
            line=line.replace("true","false")
        elif ("<client>" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["cl"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line=line.replace("host.yourdomain.com",hostName)
        elif ("<namenode>" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["nn"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line=line.replace("host.yourdomain.com",hostName)
        elif ("<datanode>" in line):
            hostName=""
            for hostNum in clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["dn"]:
                hostName =  hostName + hadoopHosts[hostNum]["hostname"]+"."+domainName + ","
            line=line.replace("host.yourdomain.com",hostName[:-1])
        elif ("<standbynamenode>" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["nn"][1]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line=line.replace("host.yourdomain.com",hostName)
        elif ("<yarn-resourcemanager>" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["rm"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line=line.replace("host.yourdomain.com",hostName)
        elif ("<yarn-nodemanager>" in line):
            hostName=""
            for hostNum in clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["nm"]:
                hostName =  hostName + hadoopHosts[hostNum]["hostname"]+"."+domainName + ","
            line=line.replace("host.yourdomain.com",hostName[:-1])
        elif ("<mapreduce-historyserver>" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["hs"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line=line.replace("host.yourdomain.com",hostName)
        elif ("<zookeeper-server>" in line):
            hostName=""
            for hostNum in clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["zk"]:
                hostName =  hostName + hadoopHosts[hostNum]["hostname"]+"."+domainName + ","
            line=line.replace("host.yourdomain.com",hostName[:-1])
        elif("<hawq-master>" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["hqm"][0]
            #hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName  FIX FOR HAWQ
            #hostName =  hadoopHosts[hostNum]["hostname"]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName


            line=line.replace("host.yourdomain.com",hostName)
        elif("<hawq-standbymaster>" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["hqm"][1]
            #hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName  FIX FOR HAWQ
            #hostName =  hadoopHosts[hostNum]["hostname"]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName


            line=line.replace("host.yourdomain.com",hostName)
        elif("<hawq-segment>" in line):
            hostName=""
            for hostNum in clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["dn"]:
                hostName =  hostName + hadoopHosts[hostNum]["hostname"]+"."+domainName + ","
                #hostName =  hostName + hadoopHosts[hostNum]["hostname"]+ ","
            line=line.replace("host.yourdomain.com",hostName[:-1])
        elif("<nameservices>" in line):
            line=line.replace("test","PHDNameSvc")
        elif ("<services>" in line):
            line=line.replace("hdfs,yarn,zookeeper,hbase,hive,hawq,pig,mahout,pxf","hdfs,yarn,zookeeper,hawq")
        #temp catchall
        elif ("host.yourdomain.com" in line):
            line=line.replace("host.yourdomain.com",hostName)


        #print line
        clusterConfigFileNew.write(line+"\n")

    clusterConfigFileNew.close()



def servicePlacement(nodeCnt,hadoopHosts,domainName,clusterId):


    # READ clusterConfig file in then replace variables and write it out.
    basePath = os.path.split(__file__)[0]
    clusterConfigFile = open(str(basePath)+"/template/clusterConfig.orig","r").readlines()
    clusterConfigFileNew = open(str(basePath)+"/template/clusterConfig.xml","w")
    for line in clusterConfigFile:
        if ("${namenode1}" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["nn"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line = line.replace("${namenode1}",hostName)
        elif ("${namenode2}" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["nn"][1]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line = line.replace("${namenode2}",hostName)
        elif ("${resourcemanager}" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["rm"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line = line.replace("${resourcemanager}",hostName)
        elif ("${historyserver}" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["hs"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line = line.replace("${historyserver}",hostName)
        elif ("${client}" in line):
            hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["cl"][0]
            hostName =  hadoopHosts[hostNum]["hostname"]+"."+domainName
            line = line.replace("${client}",hostName)
        elif ("${datanodes}" in line):
            hostName=""
            for hostNum in clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["dn"]:
                hostName =  hostName + hadoopHosts[hostNum]["hostname"]+"."+domainName + ","
            line = line.replace("${datanodes}",hostName[:-1])
        elif ("${nodemanagers}" in line):
            hostName=""
            for hostNum in clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["nm"]:
                hostName =  hostName + hadoopHosts[hostNum]["hostname"]+"."+domainName + ","
            line = line.replace("${nodemanagers}",hostName[:-1])
        elif ("${zookeepers}" in line):
            hostName=""
            for hostNum in clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["zk"]:
                hostName =  hostName + hadoopHosts[hostNum]["hostname"]+"."+domainName + ","
            line = line.replace("${zookeepers}",hostName[:-1])
        elif ("${clustername}" in line):
            line = line.replace("${clustername}",clusterId)
        # TEMP HARDCODE
        elif ("${services}" in line):
            line = line.replace("${services}","hdfs,yarn,zookeeper,hawq")



        clusterConfigFileNew.write(line)


def initializeHAWQ(username,password,hadoopHosts,clusterId,nodeCnt):
    print "Initializing HAWQ..."
    #print username
    #
    # print password
    masterNode = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["hqm"][0]
    standbyNode = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["hqm"][1]
    hawqMaster =  hadoopHosts[masterNode]["fqdn"]
    hawqStandbyMaster =  hadoopHosts[standbyNode]["fqdn"]
    for host in hadoopHosts:
        ssh.exec_command2(host["ip"],"root","changeme","sysctl -p")

    print "HAWQ Master: "+hawqMaster
    print "HAWQ StandbyMaster: "+hawqStandbyMaster

    ssh.exec_command2(hadoopHosts[masterNode]["ip"],username,password,"source /usr/local/hawq/greenplum_path.sh")
    ssh.exec_command2(hadoopHosts[masterNode]["ip"],username,password,"/etc/init.d/hawq init")


def preAmbariSetup(username,password,hadoopHosts,clusterId,nodeCnt):
    print "Configuring system for Ambari Install"
    print "Installing Ambari Agent"

    for host in hadoopHosts:
        if "hadoop0" not in host["hostname"]:
            print "Installing Ambari Agent on " + str(host['fqdn']) + " and Configuring for Server"
            ssh.exec_command2(host['fqdn'],username,password,"rpm -ivh /mnt/ambari/*agent*")
            #ssh.exec_command2(host['fqdn'],username,password,"rpm -ivh /mnt/ambari/*log4j*")
            
            

            ssh.exec_command2(host['fqdn'],username,password,"sed -i s/^hostname=.*/hostname="+hadoopHosts[0]['fqdn']+"/ /etc/ambari-agent/conf/ambari-agent.ini")
            ssh.exec_command2(host['fqdn'],username,password,"service ambari-agent start")
            
            
        else:
            ssh.exec_command2(host['fqdn'],username,password,"yum -y install postgresql-server")
            ssh.exec_command2(host['fqdn'],username,password,"rpm -ivh /mnt/ambari/*server*")



    #ssh.exec_command2(hadoopHosts[masterNode]["ip"],username,password,"source /usr/local/hawq/greenplum_path.sh")




def sparkInstall(cfgFile,username,password,hadoopHosts,clusterId,nodeCnt):
    print "Installing Spark"
    #print hadoopHosts
    hostNum = clusterLayouts["clusterSize"][int(nodeCnt)][int(nodeCnt)]["spk"][0]
    hostName =  hadoopHosts[hostNum]["fqdn"]
    # Get Spark file

def icmInstall(mgmtServer,cfgFile,username,password,hadoopHosts,clusterId):


    print "ICM Install on "+ str(mgmtServer)
    #print cfgFile
    pccPath = configFile.getParam(cfgFile,"PHD","pcc")
    #filename = ssh.putFile(mgmtServer,pccPath,username,password)
    fileName = os.path.split(pccPath)[1]
    print "PCC Filename: "+fileName


    ssh.exec_command2(mgmtServer,username,password,"yum -y install tar")
    print "Untarring: "+"tar xvfz /mnt/pcc/"+fileName
    ssh.exec_command2(mgmtServer,username,password,"cd /tmp;tar xvfz /mnt/pcc/"+fileName)
    print "Installing PCC..."
    #ssh.exec_command2(mgmtServer,username,password,"echo \"echo not running.\" > /etc/init.d/iptables")
    #print ssh.exec_command2(mgmtServer,username,password,"/tmp/"+filename[:-7]+"/install")
    ssh.exec_command2(mgmtServer,username,password,"/tmp/PCC*/install")

    print "Install Complete"
    print "Transfer Configuration: "



    # #tar File, send across, untar
    # basePath = os.path.split(__file__)[0]
    # tar = tarfile.open("/tmp/clusterConfig.tar","w")
    # fileList = []
    # for root, subFolders, files in os.walk(str(basePath)+"/template/"):
    #     for file in files:
    #         fullPath =  os.path.join(root,file)
    #         relativePath = ((root.replace(str(basePath),""))+"/"+file)[1:]
    #         tar.add(fullPath,relativePath)
    # tar.close()
    #
    #
    #
    # ssh.putFile(mgmtServer,"/tmp/clusterConfig.tar",username,password)
    # ssh.exec_command2(mgmtServer,username,password,"cd /tmp;tar xvf /tmp/clusterConfig.tar")

    # ICM Setup

    phdPath = configFile.getParam(cfgFile,"PHD","phd")
    #fileName = ssh.putFile(mgmtServer,phdPath,username,password)
    fileName = os.path.split(phdPath)[1]

    print "PHD Filename: "+fileName

    hawqPath = configFile.getParam(cfgFile,"PHD","pads")
    hawqFileName = os.path.split(hawqPath)[1]

    print "HAWQ Filename: "+ hawqFileName

    print "tar xvfz /tmp/"+fileName
    ssh.exec_command2(mgmtServer,username,password,"cd /tmp;tar xvfz /mnt/pcc/"+fileName)
    print "untar complete"


    print "tar xvfz /tmp/"+hawqFileName
    ssh.exec_command2(mgmtServer,username,password,"cd /tmp;tar xvfz /mnt/pcc/"+hawqFileName)
    print "untar complete"

    #ssh.exec_command2(mgmtServer,username,password,"echo \"changeme\" | passwd --stdin gpadmin")
    print "changed GPADMIN password"




    print "Start Import of /mnt/pcc/"+fileName[:-7]


 # import stack details
    stackConfig = {
        "stack_name": "PHD-2.1.0.0",
        "stack_properties": {
            "rpm_rel": "46",
            "hive_package_version": "0.12.0_gphd_3_1_0_0-175",
            "hadoop_rpm_version": "2.2.0_gphd_3_1_0_0-175",
            "rpm_label": "gphd",
            "hbase_package_version": "0.96.0_gphd_3_1_0_0-175",
            "zookeeper_package_version": "3.4.5_gphd_3_1_0_0-175",
            "rpm_version": "2_0_2_0",
            "pig_package_version": "0.12.0_gphd_3_1_0_0-175",
            "mahout_package_version": "0.7_gphd_3_1_0_0-175"
        },
    "stack_type": "phd"
    }


   # apiClient.importStack(stackConfig)

    ssh.exec_command2(mgmtServer,"gpadmin","changeme","icm_client import -s /tmp/"+fileName[:-7])

    print "Import Complete"
    print "Start Import of /mnt/pcc/"+hawqFileName[:-7]

    ssh.exec_command2(mgmtServer,"gpadmin","changeme","icm_client import -s /tmp/"+hawqFileName[:-7])

    print "Starting Cluster Deploy..."

    # RUN PREPAREHOSTS VIA API
    inputData={}
    hostList = []
    hostCnt = 0
    for host in hadoopHosts:
        if hostCnt > 0:
            hostList.append(host["hostname"])
        hostCnt+=1
    inputData["hosts"] = hostList
    inputData["jdkPath"] = ""
    inputData["verbose"] = True
    inputData["setupNTP"] = False
    inputData["ntpServer"] = ""
    inputData["disableSELinux"] = False
    inputData["disableIPTables"] = False
    inputData["sysConfigDir"] = ""
    inputData["skipPasswordlessSSH"] = False
    inputData["rootPassword"]= password
    inputData["gpadminPassword"]= password
    inputData["gphdStackVer"]="PHD-2.1.0.0"
    inputData["clusterId"] = clusterId

    # Get OAuth file

    ssh.getFile(mgmtServer,"/etc/gphd/gphdmgr/conf/oauth2-clients.conf","/tmp/oauth2-clients.conf",username,password)

    apiClient = APIClient (mgmtServer)

    apiClient.prepareHosts(inputData)


    # Thread the deploy and then look through install status.
    #clusterConfigJSON = json.dumps(open(str(basePath)+"/template/clusterConfig.xml","r").readlines())
    #print APIClient.deployConfiguration(apiClient,clusterConfigJSON,inputData)


    #print apiClient.getClusterTemplateJson(inputData)
    ssh.exec_command2(mgmtServer,"gpadmin","changeme","icm_client deploy -s -p -c /mnt/config")
    print "Cluster Deploy Complete:  PCC is available at https://"+mgmtServer+":5443"
    print "Starting Cluster..."
    ssh.exec_command2(mgmtServer,"gpadmin","changeme","icm_client start -l phdcluster")
    print "Cluster Started"
    #print apiClient.getClusterStatus(inputData)