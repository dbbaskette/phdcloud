__author__ = 'root'

import ConfigParser

def getParam(filename,section,parameter):
    Config = ConfigParser.ConfigParser()
    cfgFile = Config.read(filename)
    return Config.get(section,parameter)





 # Config = ConfigParser.ConfigParser()
 #    cfgFile = open(_WORK_DIR+"/.dcloud.ini","w")
 #    Config.add_section("PHD")
 #    Config.set("PHD","PCC",sys.argv[2]+"/"+directoryScan.getFilename(sys.argv[2],"PCC"))
 #    Config.set("PHD","PHD",sys.argv[2]+"/"+directoryScan.getFilename(sys.argv[2],"PHD"))
 #    Config.write(cfgFile)
 #    cfgFile.close()