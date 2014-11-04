from distutils.core import setup

setup(
    name='phdcloud',
    version='0.1',
    url='',
    license='',
    author="Dan Baskette (Borrowed Heavily from Jun Aoki's dcloud)",
    author_email='dbaskette@pivotal.io',
    description='Laptop PHD Cluster Deployment',
    scripts=["scripts/dcloud"],
    packages=['test', 'build.lib.dcloud', 'build.lib.dcloud.utils', 'dcloud', 'dcloud.utils'],
    package_data={"dcloud":["ssh_base/Dockerfile", "dockerFiles/ambaribase/*","dockerFiles/phdcluster/*","ambaribase/*" , "phdcluster/*","dns_base/Dockerfile","template/clusterConfig.*","template/gpxf/*","template/hawq/*","template/hbase/*","template/hdfs/*","template/hive/*","template/pig/*","template/yarn/*","template/zookeeper/*"]},
    data_files=[("/etc/bash_completion.d", ["scripts/autocompletion/dcloud"])],
    install_requires=["paramiko"]
)
